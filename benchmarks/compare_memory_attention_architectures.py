"""Adversarial comparison of frozen v0.7 and adaptive memory attention.

The benchmark isolates the deliberate memory-analysis architecture. Every case
uses the same canonical event ledger, current percept, leakage boundary, initial
attention aperture, and evidence floor. The frozen side may use any *applicable*
v0.7 research profile; the adaptive side receives only a closed uncertainty
class, canonical focus anchors, and deterministic telemetry.

The corpus is intentionally hostile rather than representative. It probes:

* whether the automatic aperture already makes deliberate retrieval unnecessary;
* packet truncation despite a sufficiently wide aperture candidate window;
* single- and multi-anchor association depth;
* association fan-out/budget starvation;
* anchor lock-in and deterministic reorientation;
* direct-candidate ceilings shared by both architectures.

This script is destructive by design and therefore refuses any database whose
name does not contain ``test`` or ``benchmark``.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app@localhost:5432/jit_agent_test",
)

import psycopg
from psycopg.types.json import Json

from jit_agent import db, event_store, jit_memory
from jit_agent.adaptive_memory_attention import MemoryUncertainty, RetrievalTelemetry
from jit_agent.adaptive_memory_retrieval import request_adaptive_memory
from jit_agent.association_projection import ASSOCIATION_PROJECTION_VERSION
from jit_agent.models import EventType, MemoryPacket


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema.sql"
RESULTS_DIR = ROOT / "benchmarks" / "results"


@dataclass(frozen=True, slots=True)
class RetrievalObservation:
    method: str
    success: bool
    required_event_ids: tuple[str, ...]
    returned_event_ids: tuple[str, ...]
    elapsed_ms: float
    candidate_limit: int | None
    association_limit: int | None
    association_hops: int | None
    association_decay: float | None
    association_trace_edges: int
    focus_mode: str | None = None
    scope: str | None = None
    association_effort: str | None = None


@dataclass(frozen=True, slots=True)
class Corpus:
    conversation_id: uuid.UUID
    prompt_event_id: uuid.UUID
    correlation_id: uuid.UUID
    before_global_seq: int
    query_text: str
    anchor_event_ids: tuple[uuid.UUID, ...]
    required_event_ids: tuple[uuid.UUID, ...]


def _require_disposable_database(conn: psycopg.Connection) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        name = str(cur.fetchone()[0])
    lowered = name.casefold()
    if "test" not in lowered and "benchmark" not in lowered:
        raise RuntimeError(
            f"Refusing destructive benchmark against database {name!r}; "
            "TEST_DATABASE_URL must select a dedicated test/benchmark database."
        )
    return name


def _prepare_database(conn: psycopg.Connection) -> str:
    name = _require_disposable_database(conn)
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return name


def _reset_database(conn: psycopg.Connection) -> None:
    _require_disposable_database(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                attention_interactions,
                attention_worker_results,
                attention_worker_checkpoints,
                attention_worker_claims,
                attention_worker_claim_observations,
                attention_worker_steps,
                attention_resource_reservations,
                attention_preemption_events,
                attention_scheduling_epochs,
                attention_resource_observations,
                attention_assignments,
                attention_task_transitions,
                attention_scheduler_state,
                attention_tasks,
                attention_execution_resources,
                memory_association_entries,
                memory_projection_entries,
                memory_projection_runs,
                event_integrity,
                events,
                conversations
            RESTART IDENTITY CASCADE
            """
        )
        cur.execute("ALTER SEQUENCE attention_task_created_seq RESTART WITH 1")
    conn.commit()


def _record(
    conn: psycopg.Connection,
    conversation_id: uuid.UUID,
    text: str,
    *,
    source: str = "benchmark-user",
):
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source=source,
        payload={"text": text},
        payload_text=text,
    )


def _new_conversation(conn: psycopg.Connection) -> uuid.UUID:
    conversation_id = uuid.uuid4()
    event_store.start_conversation(conn, conversation_id)
    return conversation_id


def _insert_association(
    conn: psycopg.Connection,
    *,
    association_id: str,
    source_kind: str,
    source: str,
    target_kind: str,
    target: str,
    provenance_event_ids: tuple[str, ...],
    required_cue_terms: tuple[str, ...] = (),
    strength: float = 1.0,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_association_entries (
                association_id, projection_version, source_kind, source,
                target_kind, target, relationship, strength,
                provenance_event_ids, required_cue_terms
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (association_id) DO NOTHING
            """,
            (
                association_id,
                ASSOCIATION_PROJECTION_VERSION,
                source_kind,
                source,
                target_kind,
                target,
                "BENCHMARK_LINK",
                strength,
                Json(list(provenance_event_ids)),
                Json(list(required_cue_terms)),
            ),
        )
    conn.commit()


def _trace_edge_count(packet: MemoryPacket) -> int:
    trace = packet.retrieval_trace
    kernel_trace = trace.get("kernel_trace")
    if kernel_trace is None and isinstance(trace.get("activation_kernel"), dict):
        kernel_trace = trace["activation_kernel"].get("kernel_trace")
    if not isinstance(kernel_trace, dict):
        return 0
    edge_ids: set[str] = set()
    for item in kernel_trace.get("items", []):
        if not isinstance(item, dict):
            continue
        for hop in item.get("association_hops", []):
            if isinstance(hop, dict) and hop.get("association_id"):
                edge_ids.add(str(hop["association_id"]))
    return len(edge_ids)


def _observe(
    method: str,
    packet: MemoryPacket,
    required_event_ids: tuple[uuid.UUID, ...],
    elapsed_ms: float,
) -> RetrievalObservation:
    returned = tuple(str(item.source_event_id) for item in packet.items)
    required = tuple(str(value) for value in required_event_ids)
    success = set(required).issubset(returned)
    trace = packet.retrieval_trace
    adaptive = trace.get("adaptive_policy")
    if not isinstance(adaptive, dict):
        adaptive = {}
    return RetrievalObservation(
        method=method,
        success=success,
        required_event_ids=required,
        returned_event_ids=returned,
        elapsed_ms=round(elapsed_ms, 3),
        candidate_limit=(
            int(trace["candidate_limit"])
            if isinstance(trace.get("candidate_limit"), int)
            else int(adaptive["candidate_limit"])
            if isinstance(adaptive.get("candidate_limit"), int)
            else None
        ),
        association_limit=(
            int(trace["association_limit"])
            if isinstance(trace.get("association_limit"), int)
            else int(adaptive["association_limit"])
            if isinstance(adaptive.get("association_limit"), int)
            else None
        ),
        association_hops=(
            int(trace["association_hops"])
            if isinstance(trace.get("association_hops"), int)
            else int(adaptive["max_hops"])
            if isinstance(adaptive.get("max_hops"), int)
            else 0 if trace.get("retrieval_role") == "ATTENTION_ACTIVATION" else None
        ),
        association_decay=(
            float(trace["association_decay"])
            if isinstance(trace.get("association_decay"), (int, float))
            else float(adaptive["decay"])
            if isinstance(adaptive.get("decay"), (int, float))
            else None
        ),
        association_trace_edges=_trace_edge_count(packet),
        focus_mode=str(adaptive.get("focus_mode")) if adaptive.get("focus_mode") else None,
        scope=str(adaptive.get("scope")) if adaptive.get("scope") else None,
        association_effort=(
            str(adaptive.get("association_effort"))
            if adaptive.get("association_effort")
            else None
        ),
    )


def _run_aperture(
    conn: psycopg.Connection,
    corpus: Corpus,
    *,
    packet_limit: int = 6,
) -> RetrievalObservation:
    need = jit_memory.build_memory_need(
        corpus.query_text,
        active_event_ids=list(corpus.anchor_event_ids),
        limit=packet_limit,
    )
    started = perf_counter()
    packet = jit_memory.request_attention_activation(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component="benchmark:aperture",
        need=need,
        before_global_seq=corpus.before_global_seq,
        memory_request_id=uuid.uuid4(),
    )
    return _observe(
        "attention_aperture",
        packet,
        corpus.required_event_ids,
        (perf_counter() - started) * 1000.0,
    )


def _run_frozen(
    conn: psycopg.Connection,
    corpus: Corpus,
    profile: jit_memory.MemoryRecallProfile,
    *,
    limit: int = 10,
) -> RetrievalObservation | None:
    anchors = list(corpus.anchor_event_ids)
    if profile is jit_memory.MemoryRecallProfile.CROSS_REFERENCE and not 2 <= len(anchors) <= 4:
        return None
    if profile is jit_memory.MemoryRecallProfile.FOCUSED_RECALL and len(anchors) != 1:
        return None
    if profile is jit_memory.MemoryRecallProfile.DEEPER_RESEARCH and not anchors:
        return None
    need = jit_memory.build_memory_need(
        corpus.query_text,
        focus_event_ids=anchors if profile is not jit_memory.MemoryRecallProfile.STANDARD else [],
        limit=limit,
    )
    started = perf_counter()
    packet = jit_memory.request_memory(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component=f"benchmark:frozen:{profile.value}",
        need=need,
        before_global_seq=corpus.before_global_seq,
        memory_request_id=uuid.uuid4(),
        recall_profile=profile,
    )
    return _observe(
        f"frozen:{profile.value}",
        packet,
        corpus.required_event_ids,
        (perf_counter() - started) * 1000.0,
    )


def _run_adaptive(
    conn: psycopg.Connection,
    corpus: Corpus,
    *,
    uncertainty: MemoryUncertainty,
    telemetry: RetrievalTelemetry,
    limit: int = 10,
    method_suffix: str = "",
) -> RetrievalObservation:
    need = jit_memory.build_memory_need(
        corpus.query_text,
        focus_event_ids=list(corpus.anchor_event_ids),
        limit=limit,
    )
    started = perf_counter()
    packet = request_adaptive_memory(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component="benchmark:adaptive",
        need=need,
        uncertainty=uncertainty,
        telemetry=telemetry,
        before_global_seq=corpus.before_global_seq,
        memory_request_id=uuid.uuid4(),
    )
    return _observe(
        f"adaptive{method_suffix}",
        packet,
        corpus.required_event_ids,
        (perf_counter() - started) * 1000.0,
    )


def _finalize_corpus(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    query_text: str,
    anchors: tuple[uuid.UUID, ...],
    required: tuple[uuid.UUID, ...],
) -> Corpus:
    prompt = _record(conn, conversation_id, query_text)
    jit_memory._ensure_projection_fresh(conn, before_global_seq=prompt.global_seq)
    return Corpus(
        conversation_id=conversation_id,
        prompt_event_id=prompt.event_id,
        correlation_id=prompt.correlation_id,
        before_global_seq=prompt.global_seq,
        query_text=query_text,
        anchor_event_ids=anchors,
        required_event_ids=required,
    )


def _packet_truncation_case(conn: psycopg.Connection) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(conn, conversation_id, "violet ledger marker target-seven")
    for index in range(6):
        _record(conn, conversation_id, f"violet ledger marker distractor-{index}")
    anchor = _record(conn, conversation_id, "active benchmark anchor for packet truncation")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="violet ledger marker",
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.MISSING_CONTEXT,
        telemetry=RetrievalTelemetry(candidate_scores=(0.55, 0.45)),
    )
    return {
        "scenario_id": "aperture_packet_truncation",
        "purpose": "Target is candidate-visible but ranked just outside the six-item aperture packet.",
        "aperture_already_sufficient": aperture.success,
        "observations": [
            asdict(item) for item in (aperture, deeper, adaptive) if item is not None
        ],
    }


def _candidate_case(conn: psycopg.Connection, distractor_count: int) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "amber cedar orbit exact phrase identifies CANDIDATE-TARGET",
    )
    for index in range(distractor_count):
        _record(conn, conversation_id, f"orbit amber cedar distractor-{index}")
    anchor = _record(conn, conversation_id, "active opaque candidate-sweep anchor")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="amber cedar orbit",
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    observations = [_run_aperture(conn, corpus)]
    for profile in (
        jit_memory.MemoryRecallProfile.STANDARD,
        jit_memory.MemoryRecallProfile.DEEPER_RESEARCH,
        jit_memory.MemoryRecallProfile.FOCUSED_RECALL,
    ):
        item = _run_frozen(conn, corpus, profile)
        if item is not None:
            observations.append(item)
    observations.append(
        _run_adaptive(
            conn,
            corpus,
            uncertainty=MemoryUncertainty.MISSING_CONTEXT,
            telemetry=RetrievalTelemetry(candidate_scores=(0.55, 0.45)),
        )
    )
    return {
        "scenario_id": "direct_candidate_ceiling",
        "stress_value": distractor_count,
        "stress_unit": "newer_equal-term-distractors",
        "purpose": "Old exact-phrase target competes with newer equal-term candidates; phrase bonus helps only if the candidate window admits it.",
        "aperture_already_sufficient": observations[0].success,
        "observations": [asdict(item) for item in observations],
    }


def _chain_case(
    conn: psycopg.Connection,
    *,
    hops: int,
    anchor_count: int,
) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchors = tuple(
        _record(conn, conversation_id, f"active opaque chain anchor-{index}")
        for index in range(anchor_count)
    )
    target = _record(conn, conversation_id, "opaque terminal evidence DEPTH-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="relationship among hidden chain evidence",
        anchors=tuple(item.event_id for item in anchors),
        required=(target.event_id,),
    )

    for anchor_index, anchor in enumerate(anchors):
        source_id = anchor.event_id
        for hop_index in range(hops):
            is_last = hop_index + 1 == hops
            if is_last:
                target_id = target.event_id
            else:
                intermediate = _record(
                    conn,
                    conversation_id,
                    f"opaque chain-{anchor_index}-node-{hop_index}",
                )
                # Intermediates were appended after the prompt, so they would
                # cross the leakage boundary. This case therefore constructs all
                # chain events before finalization below in _build_chain_case.
                raise RuntimeError("unreachable chain builder state")
            source_id = target_id

    raise RuntimeError("_chain_case must be constructed through _build_chain_case")


def _build_chain_case(
    conn: psycopg.Connection,
    *,
    hops: int,
    anchor_count: int,
) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchors = tuple(
        _record(conn, conversation_id, f"active opaque chain anchor-{index}")
        for index in range(anchor_count)
    )
    paths: list[list[uuid.UUID]] = []
    for anchor_index in range(anchor_count):
        path: list[uuid.UUID] = [anchors[anchor_index].event_id]
        for hop_index in range(max(0, hops - 1)):
            node = _record(
                conn,
                conversation_id,
                f"opaque chain-{anchor_index}-node-{hop_index}",
            )
            path.append(node.event_id)
        paths.append(path)
    target = _record(conn, conversation_id, "opaque terminal evidence DEPTH-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="relationship among hidden chain evidence",
        anchors=tuple(item.event_id for item in anchors),
        required=(target.event_id,),
    )
    for anchor_index, path in enumerate(paths):
        nodes = [*path, target.event_id]
        for edge_index in range(len(nodes) - 1):
            _insert_association(
                conn,
                association_id=(
                    f"depth-{anchor_count}-{hops}-{anchor_index}-{edge_index:02d}"
                ),
                source_kind="EVENT",
                source=str(nodes[edge_index]),
                target_kind="EVENT",
                target=str(nodes[edge_index + 1]),
                provenance_event_ids=(
                    str(nodes[edge_index]),
                    str(nodes[edge_index + 1]),
                ),
            )

    aperture = _run_aperture(conn, corpus)
    observations: list[RetrievalObservation] = [aperture]
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    if deeper is not None:
        observations.append(deeper)
    if anchor_count == 1:
        focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
        if focused is not None:
            observations.append(focused)
    else:
        cross = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.CROSS_REFERENCE)
        if cross is not None:
            observations.append(cross)
    observations.append(
        _run_adaptive(
            conn,
            corpus,
            uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
            telemetry=RetrievalTelemetry(candidate_scores=(0.90, 0.10)),
        )
    )
    return {
        "scenario_id": (
            "single_anchor_depth" if anchor_count == 1 else "multi_anchor_depth"
        ),
        "stress_value": hops,
        "stress_unit": "association-hops",
        "anchor_count": anchor_count,
        "purpose": "Target is reachable only through an exact-length opaque association chain.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in observations],
    }


def _fanout_case(conn: psycopg.Connection, distractor_edges: int) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchor = _record(conn, conversation_id, "active opaque fanout anchor")
    distractors = [
        _record(conn, conversation_id, f"opaque fanout distractor-{index}")
        for index in range(distractor_edges)
    ]
    target = _record(conn, conversation_id, "opaque fanout required evidence FANOUT-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="hidden fanout relationship evidence",
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    for index, distractor in enumerate(distractors):
        _insert_association(
            conn,
            association_id=f"a-fanout-{index:05d}",
            source_kind="EVENT",
            source=str(anchor.event_id),
            target_kind="EVENT",
            target=str(distractor.event_id),
            provenance_event_ids=(str(anchor.event_id), str(distractor.event_id)),
        )
    _insert_association(
        conn,
        association_id="z-fanout-required-target",
        source_kind="EVENT",
        source=str(anchor.event_id),
        target_kind="EVENT",
        target=str(target.event_id),
        provenance_event_ids=(str(anchor.event_id), str(target.event_id)),
    )

    aperture = _run_aperture(conn, corpus)
    observations: list[RetrievalObservation] = [aperture]
    for profile in (
        jit_memory.MemoryRecallProfile.DEEPER_RESEARCH,
        jit_memory.MemoryRecallProfile.FOCUSED_RECALL,
    ):
        item = _run_frozen(conn, corpus, profile)
        if item is not None:
            observations.append(item)
    observations.append(
        _run_adaptive(
            conn,
            corpus,
            uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
            telemetry=RetrievalTelemetry(candidate_scores=(0.90, 0.10)),
        )
    )
    return {
        "scenario_id": "association_fanout_ceiling",
        "stress_value": distractor_edges,
        "stress_unit": "earlier-sorted-outgoing-edges",
        "purpose": "Required edge sorts after a high-fanout distractor frontier and disappears when the association budget is exhausted.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in observations],
    }


def _anchor_trap_case(conn: psycopg.Connection, distractor_edges: int) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchor = _record(conn, conversation_id, "active misleading opaque anchor")
    distractors = [
        _record(conn, conversation_id, f"misleading opaque branch-{index}")
        for index in range(distractor_edges)
    ]
    target = _record(conn, conversation_id, "correct opaque evidence REORIENT-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="escape from misleading memory focus",
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    for index, distractor in enumerate(distractors):
        _insert_association(
            conn,
            association_id=f"a-trap-{index:05d}",
            source_kind="EVENT",
            source=str(anchor.event_id),
            target_kind="EVENT",
            target=str(distractor.event_id),
            provenance_event_ids=(str(anchor.event_id), str(distractor.event_id)),
        )
    _insert_association(
        conn,
        association_id="z-trap-correct-term-route",
        source_kind="TERM",
        source="escape",
        target_kind="EVENT",
        target=str(target.event_id),
        provenance_event_ids=(str(target.event_id),),
    )

    aperture = _run_aperture(conn, corpus)
    focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
    adaptive_rounds = [
        _run_adaptive(
            conn,
            corpus,
            uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
            telemetry=RetrievalTelemetry(
                candidate_scores=(0.90, 0.10),
                anchored_rounds=round_index,
                support_gain=(0.0 if round_index else None),
            ),
            method_suffix=f":round-{round_index + 1}",
        )
        for round_index in range(3)
    ]
    observations = [aperture]
    if focused is not None:
        observations.append(focused)
    observations.extend(adaptive_rounds)
    return {
        "scenario_id": "anchor_lock_in_and_reorientation",
        "stress_value": distractor_edges,
        "stress_unit": "misleading-anchor-edges",
        "purpose": "Anchored graph work is budget-starved by a misleading focus; after repeated zero-gain passes adaptive attention must drop the anchor and recover a cue-term route.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in observations],
    }


def _limits(cases: list[dict[str, object]], method: str) -> dict[str, object]:
    points: list[tuple[int, bool]] = []
    for case in cases:
        if "stress_value" not in case:
            continue
        observation = next(
            (
                item for item in case["observations"]
                if item["method"] == method
            ),
            None,
        )
        if observation is not None:
            points.append((int(case["stress_value"]), bool(observation["success"])))
    successes = [value for value, passed in points if passed]
    failures = [value for value, passed in points if not passed]
    return {
        "largest_tested_success": max(successes) if successes else None,
        "smallest_tested_failure": min(failures) if failures else None,
        "tested_points": [
            {"stress_value": value, "success": passed}
            for value, passed in sorted(points)
        ],
    }


def _head_to_head(cases: list[dict[str, object]]) -> dict[str, int]:
    counts = {
        "aperture_already_sufficient": 0,
        "adaptive_only": 0,
        "frozen_only": 0,
        "both": 0,
        "neither": 0,
    }
    for case in cases:
        if bool(case.get("aperture_already_sufficient")):
            counts["aperture_already_sufficient"] += 1
            continue
        observations = case["observations"]
        adaptive_success = any(
            bool(item["success"])
            for item in observations
            if str(item["method"]).startswith("adaptive")
        )
        frozen_success = any(
            bool(item["success"])
            for item in observations
            if str(item["method"]).startswith("frozen:")
            and item["method"] != "frozen:STANDARD"
        )
        if adaptive_success and frozen_success:
            counts["both"] += 1
        elif adaptive_success:
            counts["adaptive_only"] += 1
        elif frozen_success:
            counts["frozen_only"] += 1
        else:
            counts["neither"] += 1
    return counts


def run_comparison(*, stress: bool) -> dict[str, object]:
    conn = db.get_connection()
    try:
        database_name = _prepare_database(conn)
        cases: list[dict[str, object]] = [_packet_truncation_case(conn)]

        candidate_points = (
            (140, 160, 240, 260, 340, 360, 490, 510, 590, 610, 740, 760)
            if stress
            else (160, 360, 610, 760)
        )
        for value in candidate_points:
            cases.append(_candidate_case(conn, value))

        depth_points = tuple(range(1, 7)) if stress else (2, 3, 4, 5, 6)
        for hops in depth_points:
            cases.append(_build_chain_case(conn, hops=hops, anchor_count=1))
            cases.append(_build_chain_case(conn, hops=hops, anchor_count=2))

        fanout_points = (
            (550, 650, 850, 950, 1150, 1250)
            if stress
            else (650, 950, 1250)
        )
        for value in fanout_points:
            cases.append(_fanout_case(conn, value))

        cases.append(_anchor_trap_case(conn, 1200))

        candidate_cases = [case for case in cases if case["scenario_id"] == "direct_candidate_ceiling"]
        single_depth_cases = [case for case in cases if case["scenario_id"] == "single_anchor_depth"]
        multi_depth_cases = [case for case in cases if case["scenario_id"] == "multi_anchor_depth"]
        fanout_cases = [case for case in cases if case["scenario_id"] == "association_fanout_ceiling"]

        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-001",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "comparison_rule": (
                "Automatic aperture is common substrate. Head-to-head counts only cases where "
                "that aperture did not already contain all required evidence. Frozen success "
                "means any applicable explicit v0.7 research profile succeeded."
            ),
            "head_to_head": _head_to_head(cases),
            "observed_limits": {
                "candidate_distractors": {
                    method: _limits(candidate_cases, method)
                    for method in (
                        "attention_aperture",
                        "frozen:STANDARD",
                        "frozen:DEEPER_RESEARCH",
                        "frozen:FOCUSED_RECALL",
                        "adaptive",
                    )
                },
                "single_anchor_depth": {
                    method: _limits(single_depth_cases, method)
                    for method in (
                        "frozen:DEEPER_RESEARCH",
                        "frozen:FOCUSED_RECALL",
                        "adaptive",
                    )
                },
                "multi_anchor_depth": {
                    method: _limits(multi_depth_cases, method)
                    for method in (
                        "frozen:DEEPER_RESEARCH",
                        "frozen:CROSS_REFERENCE",
                        "adaptive",
                    )
                },
                "association_fanout": {
                    method: _limits(fanout_cases, method)
                    for method in (
                        "frozen:DEEPER_RESEARCH",
                        "frozen:FOCUSED_RECALL",
                        "adaptive",
                    )
                },
            },
            "cases": cases,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stress",
        action="store_true",
        help="run boundary-adjacent sweeps and larger hostile corpora",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON result path; defaults under benchmarks/results",
    )
    args = parser.parse_args()

    result = run_comparison(stress=args.stress)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output = args.output
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"MEM-ADAPT-001_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "benchmark_id": result["benchmark_id"],
        "mode": result["mode"],
        "head_to_head": result["head_to_head"],
        "observed_limits": result["observed_limits"],
        "output": str(output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
