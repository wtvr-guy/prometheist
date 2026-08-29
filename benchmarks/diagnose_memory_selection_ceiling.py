"""Instrument where equal-term old-memory retrieval actually loses the target.

MEM-ADAPT-001 showed a shared failure under newer equal-term distractors, but its
first sample point was already far beyond the practical failure. This diagnostic
separates three bounded stages:

1. direct candidate routing;
2. deterministic kernel admission/ranking;
3. surfaced packet truncation.

The script is destructive and refuses a database whose name does not contain
``test`` or ``benchmark``.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app@localhost:5432/jit_agent_test",
)

import psycopg

from jit_agent import db, event_store, jit_memory, postgres_memory_kernel
from jit_agent.memory_kernel import CueState, recall
from jit_agent.models import EventType


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema.sql"
RESULTS_DIR = ROOT / "benchmarks" / "results"


@dataclass(frozen=True, slots=True)
class StageObservation:
    distractor_count: int
    candidate_limit: int
    packet_limit: int
    raw_candidate_count: int
    target_raw_candidate_rank: int | None
    target_admitted_rank: int | None
    target_score_total: float | None
    target_selected_by_kernel: bool
    target_surfaces_in_packet: bool


def _require_disposable_database(conn: psycopg.Connection) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        name = str(cur.fetchone()[0])
    lowered = name.casefold()
    if "test" not in lowered and "benchmark" not in lowered:
        raise RuntimeError(
            f"Refusing destructive diagnostic against database {name!r}; "
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


def _build_case(conn: psycopg.Connection, distractor_count: int):
    _reset_database(conn)
    conversation_id = uuid.uuid4()
    event_store.start_conversation(conn, conversation_id)
    target = _record(
        conn,
        conversation_id,
        "amber cedar orbit exact phrase identifies CANDIDATE-TARGET",
    )
    for index in range(distractor_count):
        _record(conn, conversation_id, f"orbit amber cedar distractor-{index}")
    anchor = _record(conn, conversation_id, "active opaque candidate-sweep anchor")
    prompt = _record(conn, conversation_id, "amber cedar orbit")
    jit_memory._ensure_projection_fresh(conn, before_global_seq=prompt.global_seq)
    return conversation_id, target, anchor, prompt


def _cue_for(
    *,
    conversation_id: uuid.UUID,
    packet_limit: int,
    active_count: int,
) -> CueState:
    need = jit_memory.build_memory_need(
        "amber cedar orbit",
        conversation_id=conversation_id,
        limit=packet_limit,
    )
    return CueState(
        query_text=need.query_text,
        entities=tuple(need.entities),
        reference_time=need.reference_time,
        conversation_id=str(conversation_id),
        source_types=tuple(item.value for item in jit_memory._effective_source_types(need)),
        limit=min(20, packet_limit + active_count),
        minimum_score=jit_memory.MINIMUM_SCORE,
    )


def _position(values, target) -> int | None:
    try:
        return values.index(target) + 1
    except ValueError:
        return None


def _observe_stage(
    conn: psycopg.Connection,
    *,
    distractor_count: int,
    candidate_limit: int,
    packet_limit: int,
    target_event_id: uuid.UUID,
    conversation_id: uuid.UUID,
    before_global_seq: int,
    active_count: int,
) -> StageObservation:
    cue = _cue_for(
        conversation_id=conversation_id,
        packet_limit=packet_limit,
        active_count=active_count,
    )
    raw_ids = postgres_memory_kernel._candidate_event_ids(
        conn,
        cue,
        before_global_seq=before_global_seq,
        candidate_limit=candidate_limit,
    )
    target_raw_rank = _position(raw_ids, target_event_id)
    events = postgres_memory_kernel._load_events_by_ids(
        conn,
        raw_ids,
        before_global_seq=before_global_seq,
    )
    kernel_packet = recall(events, cue)
    admitted_ids = [uuid.UUID(item.event_id) for item in kernel_packet.trace.items]
    target_admitted_rank = _position(admitted_ids, target_event_id)
    target_trace = next(
        (item for item in kernel_packet.trace.items if item.event_id == str(target_event_id)),
        None,
    )
    selected_ids = {uuid.UUID(item.event_id) for item in kernel_packet.items}
    target_surfaces = (
        target_admitted_rank is not None and target_admitted_rank <= packet_limit
    )
    return StageObservation(
        distractor_count=distractor_count,
        candidate_limit=candidate_limit,
        packet_limit=packet_limit,
        raw_candidate_count=len(raw_ids),
        target_raw_candidate_rank=target_raw_rank,
        target_admitted_rank=target_admitted_rank,
        target_score_total=(
            round(float(target_trace.score.total), 6) if target_trace is not None else None
        ),
        target_selected_by_kernel=target_event_id in selected_ids,
        target_surfaces_in_packet=target_surfaces,
    )


def _first_failure(
    observations: list[StageObservation],
    *,
    candidate_limit: int,
    packet_limit: int,
    attribute: str,
) -> int | None:
    relevant = [
        item
        for item in observations
        if item.candidate_limit == candidate_limit and item.packet_limit == packet_limit
    ]
    for item in sorted(relevant, key=lambda value: value.distractor_count):
        if not bool(getattr(item, attribute)):
            return item.distractor_count
    return None


def run_diagnostic(*, stress: bool) -> dict[str, object]:
    conn = db.get_connection()
    try:
        database_name = _prepare_database(conn)
        distractor_points = (
            (
                0,
                1,
                2,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                11,
                12,
                20,
                40,
                80,
                100,
                120,
                140,
                160,
                240,
                320,
                440,
                560,
                620,
                700,
                760,
                820,
            )
            if stress
            else (0, 4, 5, 6, 7, 8, 9, 10, 11, 12, 20, 40, 80, 120)
        )
        candidate_limits = (150, 175, 250, 350, 500, 600, 750)
        packet_limits = (6, 10)
        observations: list[StageObservation] = []
        for distractor_count in distractor_points:
            conversation_id, target, _anchor, prompt = _build_case(conn, distractor_count)
            for candidate_limit in candidate_limits:
                for packet_limit in packet_limits:
                    observations.append(
                        _observe_stage(
                            conn,
                            distractor_count=distractor_count,
                            candidate_limit=candidate_limit,
                            packet_limit=packet_limit,
                            target_event_id=target.event_id,
                            conversation_id=conversation_id,
                            before_global_seq=prompt.global_seq,
                            active_count=1 if packet_limit == 6 else 0,
                        )
                    )

        boundaries: dict[str, object] = {}
        for candidate_limit in candidate_limits:
            for packet_limit in packet_limits:
                key = f"candidate_{candidate_limit}:packet_{packet_limit}"
                relevant = [
                    item
                    for item in observations
                    if item.candidate_limit == candidate_limit
                    and item.packet_limit == packet_limit
                ]
                route_failure = next(
                    (
                        item.distractor_count
                        for item in sorted(
                            relevant,
                            key=lambda value: value.distractor_count,
                        )
                        if item.target_raw_candidate_rank is None
                    ),
                    None,
                )
                boundaries[key] = {
                    "first_raw_candidate_failure": route_failure,
                    "first_kernel_selection_failure": _first_failure(
                        observations,
                        candidate_limit=candidate_limit,
                        packet_limit=packet_limit,
                        attribute="target_selected_by_kernel",
                    ),
                    "first_surface_failure": _first_failure(
                        observations,
                        candidate_limit=candidate_limit,
                        packet_limit=packet_limit,
                        attribute="target_surfaces_in_packet",
                    ),
                }

        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-001-DIAGNOSTIC",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "question": (
                "When an old memory ties newer memories on semantic score, does it "
                "disappear at candidate routing, kernel ranking, or bounded packet "
                "surfacing?"
            ),
            "tie_break_rule": "score desc, global_seq desc, event_id asc",
            "boundaries": boundaries,
            "observations": [asdict(item) for item in observations],
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_diagnostic(stress=args.stress)
    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"MEM-ADAPT-001-DIAGNOSTIC_{stamp}.json"
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "boundaries": result["boundaries"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
