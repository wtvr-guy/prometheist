"""Adversarial comparison of frozen v0.7 and adaptive memory attention.

The benchmark isolates deliberate memory analysis. Every case uses the same
canonical event ledger, current percept, leakage boundary, evidence floor, and
automatic attention aperture. The frozen side may use every applicable v0.7
research profile; the adaptive side receives only a closed uncertainty class,
canonical focus anchors, and deterministic telemetry.

This script is destructive by design and refuses any database whose name does
not contain ``test`` or ``benchmark``.
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


def _record(conn: psycopg.Connection, conversation_id: uuid.UUID, text: str):
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="benchmark-user",
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
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_association_entries (
                association_id, projection_version, source_kind, source,
                target_kind, target, relationship, strength,
                provenance_event_ids, required_cue_terms
            ) VALUES (%s, %s, %s, %s, %s, %s, 'BENCHMARK_LINK', 1.0, %s, %s)
            ON CONFLICT (association_id) DO NOTHING
            """,
            (
                association_id,
                ASSOCIATION_PROJECTION_VERSION,
                source_kind,
                source,
                target_kind,
                target,
                Json(list(provenance_event_ids)),
                Json(list(required_cue_terms)),
            ),
        )
    conn.commit()


def _kernel_traces(trace: dict[str, object]) -> list[dict[str, object]]:
    """Collect kernel traces from aperture, joint, and per-anchor frozen paths."""

    found: list[dict[str, object]] = []
    direct = trace.get("kernel_trace")
    if isinstance(direct, dict):
        found.append(direct)
    activation = trace.get("activation_kernel")
    if isinstance(activation, dict):
        nested = activation.get("kernel_trace")
        if isinstance(nested, dict):
            found.append(nested)
    attempts = trace.get("focus_attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            nested = attempt.get("kernel_trace")
            if isinstance(nested, dict):
                found.append(nested)
    return found


def _trace_edge_count(packet: MemoryPacket) -> int:
    edge_ids: set[str] = set()
    for kernel_trace in _kernel_traces(packet.retrieval_trace):
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
    trace = packet.retrieval_trace
    adaptive = trace.get("adaptive_policy")
    if not isinstance(adaptive, dict):
        adaptive = {}

    def _integer(primary: str, adaptive_key: str) -> int | None:
        value = trace.get(primary)
        if isinstance(value, int):
            return value
        value = adaptive.get(adaptive_key)
        return int(value) if isinstance(value, int) else None

    def _number(primary: str, adaptive_key: str) -> float | None:
        value = trace.get(primary)
        if isinstance(value, (int, float)):
            return float(value)
        value = adaptive.get(adaptive_key)
        return float(value) if isinstance(value, (int, float)) else None

    hops = _integer("association_hops", "max_hops")
    if hops is None and trace.get("retrieval_role") == "ATTENTION_ACTIVATION":
        hops = 0
    return RetrievalObservation(
        method=method,
        success=set(required).issubset(returned),
        required_event_ids=required,
        returned_event_ids=returned,
        elapsed_ms=round(elapsed_ms, 3),
        candidate_limit=_integer("candidate_limit", "candidate_limit"),
        association_limit=_integer("association_limit", "association_limit"),
        association_hops=hops,
        association_decay=_number("association_decay", "decay"),
        association_trace_edges=_trace_edge_count(packet),
        focus_mode=str(adaptive.get("focus_mode")) if adaptive.get("focus_mode") else None,
        scope=str(adaptive.get("scope")) if adaptive.get("scope") else None,
        association_effort=(
            str(adaptive.get("association_effort"))
            if adaptive.get("association_effort")
            else None
        ),
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
        correlation_id=prompt.correlation_id,
        before_global_seq=prompt.global_seq,
        query_text=query_text,
        anchor_event_ids=anchors,
        required_event_ids=required,
    )


def _run_aperture(
    conn: psycopg.Connection,
    corpus: Corpus,
    *,
    packet_limit: int = 6,
) -> RetrievalObservation:
    started = perf_counter()
    packet = jit_memory.request_attention_activation(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component="benchmark:aperture",
        need=jit_memory.build_memory_need(
            corpus.query_text,
            active_event_ids=list(corpus.anchor_event_ids),
            limit=packet_limit,
        ),
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
    started = perf_counter()
    packet = jit_memory.request_memory(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component=f"benchmark:frozen:{profile.value}",
        need=jit_memory.build_memory_need(
            corpus.query_text,
            focus_event_ids=(
                anchors if profile is not jit_memory.MemoryRecallProfile.STANDARD else []
            ),
            limit=limit,
        ),
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
    started = perf_counter()
    packet = request_adaptive_memory(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component="benchmark:adaptive",
        need=jit_memory.build_memory_need(
            corpus.query_text,
            focus_event_ids=list(corpus.anchor_event_ids),
            limit=limit,
        ),
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


def _packet_truncation_case(conn: psycopg.Connection) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(conn, conversation_id, "violet ledger marker target-seven")
    for index in range(6):
        _record(conn, conversation_id, f"violet ledger marker distractor-{index}")
    anchor = _record(conn, conversation_id, "active benchmark packet anchor")
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
        "purpose": "Required evidence is candidate-visible but just outside the surfaced aperture packet.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in (aperture, deeper, adaptive) if item],
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
        if item:
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
        "stress_unit": "newer-equal-term-distractors",
        "purpose": "An old exact-phrase target competes with newer equal-term candidates until bounded candidate routing starves it.",
        "aperture_already_sufficient": observations[0].success,
        "observations": [asdict(item) for item in observations],
    }


def _build_chain_case(
    conn: psycopg.Connection,
    *,
    hops: int,
    anchor_count: int,
) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchors = tuple(
        _record(conn, conversation_id, f"selected chain anchor-{index}")
        for index in range(anchor_count)
    )
    paths: list[list[uuid.UUID]] = []
    for anchor_index in range(anchor_count):
        path = [anchors[anchor_index].event_id]
        for hop_index in range(max(0, hops - 1)):
            node = _record(conn, conversation_id, f"opaque node {anchor_index} {hop_index}")
            path.append(node.event_id)
        paths.append(path)
    target = _record(conn, conversation_id, "terminal datum DEPTH-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="trace cobalt linkage",
        anchors=tuple(item.event_id for item in anchors),
        required=(target.event_id,),
    )
    for anchor_index, path in enumerate(paths):
        nodes = [*path, target.event_id]
        for edge_index in range(len(nodes) - 1):
            _insert_association(
                conn,
                association_id=f"depth-{anchor_count}-{hops}-{anchor_index}-{edge_index:02d}",
                source_kind="EVENT",
                source=str(nodes[edge_index]),
                target_kind="EVENT",
                target=str(nodes[edge_index + 1]),
                provenance_event_ids=(str(nodes[edge_index]), str(nodes[edge_index + 1])),
            )

    aperture = _run_aperture(conn, corpus)
    observations = [aperture]
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    if deeper:
        observations.append(deeper)
    specialized = _run_frozen(
        conn,
        corpus,
        (
            jit_memory.MemoryRecallProfile.FOCUSED_RECALL
            if anchor_count == 1
            else jit_memory.MemoryRecallProfile.CROSS_REFERENCE
        ),
    )
    if specialized:
        observations.append(specialized)
    observations.append(
        _run_adaptive(
            conn,
            corpus,
            uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
            telemetry=RetrievalTelemetry(candidate_scores=(0.90, 0.10)),
        )
    )
    return {
        "scenario_id": "single_anchor_depth" if anchor_count == 1 else "multi_anchor_depth",
        "stress_value": hops,
        "stress_unit": "association-hops",
        "anchor_count": anchor_count,
        "purpose": "Required evidence is reachable only through an exact-length opaque association chain.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in observations],
    }


def _fanout_case(conn: psycopg.Connection, distractor_edges: int) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchor = _record(conn, conversation_id, "selected fanout anchor")
    distractors = [
        _record(conn, conversation_id, f"opaque branch {index}")
        for index in range(distractor_edges)
    ]
    target = _record(conn, conversation_id, "terminal payload FANOUT-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="trace hidden relation",
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
    observations = [aperture]
    for profile in (
        jit_memory.MemoryRecallProfile.DEEPER_RESEARCH,
        jit_memory.MemoryRecallProfile.FOCUSED_RECALL,
    ):
        item = _run_frozen(conn, corpus, profile)
        if item:
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
        "purpose": "The required edge sorts behind a hostile fanout frontier and disappears when the association budget is exhausted.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in observations],
    }


def _anchor_trap_case(conn: psycopg.Connection, distractor_edges: int) -> dict[str, object]:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchor = _record(conn, conversation_id, "selected misleading anchor")
    distractors = [
        _record(conn, conversation_id, f"misleading branch {index}")
        for index in range(distractor_edges)
    ]
    target = _record(conn, conversation_id, "correct opaque datum REORIENT-TARGET")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="escape misleading focus",
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
    observations = [aperture]
    focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
    if focused:
        observations.append(focused)
    for round_index in range(3):
        observations.append(
            _run_adaptive(
                conn,
                corpus,
                uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
                telemetry=RetrievalTelemetry(
                    candidate_scores=(0.90, 0.10),
                    anchored_rounds=round_index,
                    support_gain=0.0 if round_index else None,
                ),
                method_suffix=f":round-{round_index + 1}",
            )
        )
    return {
        "scenario_id": "anchor_lock_in_and_reorientation",
        "stress_value": distractor_edges,
        "stress_unit": "misleading-anchor-edges",
        "purpose": "A misleading anchor exhausts graph budget; adaptive attention must eventually drop it and recover a cue-term route.",
        "aperture_already_sufficient": aperture.success,
        "observations": [asdict(item) for item in observations],
    }


def _limits(cases: list[dict[str, object]], method: str) -> dict[str, object]:
    points: list[tuple[int, bool]] = []
    for case in cases:
        if "stress_value" not in case:
            continue
        observation = next(
            (item for item in case["observations"] if item["method"] == method),
            None,
        )
        if observation:
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
            (120, 140, 160, 240, 280, 320, 360, 440, 460, 520, 560, 620, 660, 700)
            if stress
            else (140, 320, 560, 700)
        )
        for value in candidate_points:
            cases.append(_candidate_case(conn, value))

        depth_points = tuple(range(1, 7)) if stress else (2, 3, 4, 5, 6)
        for hops in depth_points:
            cases.append(_build_chain_case(conn, hops=hops, anchor_count=1))
            cases.append(_build_chain_case(conn, hops=hops, anchor_count=2))

        fanout_points = (
            (250, 350, 550, 650, 700, 800, 850, 950, 1150, 1250)
            if stress
            else (350, 650, 950, 1250)
        )
        for value in fanout_points:
            cases.append(_fanout_case(conn, value))

        cases.append(_anchor_trap_case(conn, 1200))

        def family(scenario_id: str) -> list[dict[str, object]]:
            return [case for case in cases if case["scenario_id"] == scenario_id]

        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-001",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "comparison_rule": (
                "Automatic aperture is common substrate. Head-to-head counts only cases where "
                "the aperture did not already contain all required evidence. Frozen success "
                "means any applicable explicit v0.7 research profile succeeded."
            ),
            "head_to_head": _head_to_head(cases),
            "observed_limits": {
                "candidate_distractors": {
                    method: _limits(family("direct_candidate_ceiling"), method)
                    for method in (
                        "attention_aperture",
                        "frozen:STANDARD",
                        "frozen:DEEPER_RESEARCH",
                        "frozen:FOCUSED_RECALL",
                        "adaptive",
                    )
                },
                "single_anchor_depth": {
                    method: _limits(family("single_anchor_depth"), method)
                    for method in (
                        "frozen:DEEPER_RESEARCH",
                        "frozen:FOCUSED_RECALL",
                        "adaptive",
                    )
                },
                "multi_anchor_depth": {
                    method: _limits(family("multi_anchor_depth"), method)
                    for method in (
                        "frozen:DEEPER_RESEARCH",
                        "frozen:CROSS_REFERENCE",
                        "adaptive",
                    )
                },
                "association_fanout": {
                    method: _limits(family("association_fanout_ceiling"), method)
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
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "head_to_head": result["head_to_head"],
                "observed_limits": result["observed_limits"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
