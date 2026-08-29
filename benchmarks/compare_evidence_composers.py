"""MEM-ADAPT-003: current top-k versus coverage-aware evidence composition.

This experiment freezes adaptive retrieval mechanics and changes only the bounded
evidence composition step. Both composers receive the same ordered candidate pool.
The benchmark therefore tests whether a smarter consciousness boundary can retain
more useful canonical evidence without increasing the final packet size.

The script is destructive and refuses a database whose name does not contain
``test`` or ``benchmark``.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app@localhost:5432/jit_agent_test",
)

from jit_agent import db, jit_memory
from jit_agent.adaptive_memory_attention import MemoryUncertainty, RetrievalTelemetry
from jit_agent.adaptive_memory_retrieval import request_adaptive_memory
from jit_agent.evidence_composer import CompositionResult, compose_coverage_aware


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "benchmarks" / "results"
BASELINE = runpy.run_path(
    str(ROOT / "benchmarks" / "compare_memory_attention_architectures.py"),
    run_name="mem_adapt_003_baseline",
)

_reset_database = BASELINE["_reset_database"]
_prepare_database = BASELINE["_prepare_database"]
_new_conversation = BASELINE["_new_conversation"]
_record = BASELINE["_record"]
_finalize_corpus = BASELINE["_finalize_corpus"]


def _pool(
    conn,
    corpus,
    *,
    pool_limit: int,
    uncertainty: MemoryUncertainty,
    telemetry: RetrievalTelemetry,
):
    return request_adaptive_memory(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component="benchmark:evidence-composer",
        need=jit_memory.build_memory_need(
            corpus.query_text,
            focus_event_ids=list(corpus.anchor_event_ids),
            limit=pool_limit,
        ),
        uncertainty=uncertainty,
        telemetry=telemetry,
        before_global_seq=corpus.before_global_seq,
        memory_request_id=uuid.uuid4(),
    )


def _ids(items) -> tuple[uuid.UUID, ...]:
    return tuple(item.source_event_id for item in items)


def _success(items, required: tuple[uuid.UUID, ...]) -> bool:
    surfaced = set(_ids(items))
    return all(event_id in surfaced for event_id in required)


def _serialize_composition(result: CompositionResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for decision in result.decisions:
        row = asdict(decision)
        row["source_event_id"] = str(decision.source_event_id)
        row["token_novelty"] = str(decision.token_novelty)
        rows.append(row)
    return rows


def _evaluate(
    pool_packet,
    *,
    required: tuple[uuid.UUID, ...],
    packet_limit: int,
    retained=(),
) -> dict[str, object]:
    pool_items = list(pool_packet.items)
    current = pool_items[:packet_limit]
    composed = compose_coverage_aware(
        pool_items,
        retained=retained,
        limit=packet_limit,
    )
    ranks = {
        str(event_id): (
            next(
                (index for index, item in enumerate(pool_items, start=1) if item.source_event_id == event_id),
                None,
            )
        )
        for event_id in required
    }
    return {
        "candidate_pool_size": len(pool_items),
        "required_pool_ranks": ranks,
        "current_top_k": {
            "success": _success(current, required),
            "event_ids": [str(value) for value in _ids(current)],
        },
        "coverage_aware": {
            "success": _success(composed.items, required),
            "event_ids": [str(value) for value in _ids(composed.items)],
            "decisions": _serialize_composition(composed),
        },
    }


def _equal_term_old_memory(conn, *, distractors: int, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "amber cedar orbit exact phrase identifies CANDIDATE-TARGET",
    )
    for index in range(distractors):
        _record(conn, conversation_id, f"orbit amber cedar distractor-{index}")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="amber cedar orbit",
        anchors=(),
        required=(target.event_id,),
    )
    packet = _pool(
        conn,
        corpus,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.AMBIGUOUS_CANDIDATES,
        telemetry=RetrievalTelemetry(candidate_scores=(0.5, 0.5)),
    )
    return {
        "scenario_id": "equal_term_old_memory",
        "purpose": "Old tied evidence must survive a bounded packet despite newer near-duplicates.",
        "distractors": distractors,
        **_evaluate(
            packet,
            required=(target.event_id,),
            packet_limit=packet_limit,
        ),
    }


def _correction_pair(conn, *, distractors: int, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    original = _record(
        conn,
        conversation_id,
        "Atlas launch date was recorded as Tuesday status ORIGINAL CLAIM",
    )
    correction = _record(
        conn,
        conversation_id,
        "Atlas launch date was corrected from Tuesday to Thursday status CORRECTION",
    )
    for index in range(distractors):
        _record(conn, conversation_id, f"Atlas launch date planning distractor-{index}")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="Atlas launch date",
        anchors=(),
        required=(original.event_id, correction.event_id),
    )
    packet = _pool(
        conn,
        corpus,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.POSSIBLE_CONTRADICTION,
        telemetry=RetrievalTelemetry(candidate_scores=(0.52, 0.48)),
    )
    return {
        "scenario_id": "correction_pair_under_duplicate_pressure",
        "purpose": "Preserve both an older claim and its later correction for downstream supersession reasoning.",
        "distractors": distractors,
        **_evaluate(
            packet,
            required=(original.event_id, correction.event_id),
            packet_limit=packet_limit,
        ),
    }


def _weak_clues(conn, *, distractors: int, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    clues = (
        _record(conn, conversation_id, "project decision clue alpha mentions thermal ceiling"),
        _record(conn, conversation_id, "project decision clue beta records memory pressure"),
        _record(conn, conversation_id, "project decision clue gamma links scheduler headroom"),
    )
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            f"project decision exact looking distractor-{index}",
        )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="project decision exact looking",
        anchors=(),
        required=tuple(item.event_id for item in clues),
    )
    packet = _pool(
        conn,
        corpus,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.AMBIGUOUS_CANDIDATES,
        telemetry=RetrievalTelemetry(candidate_scores=(0.26, 0.25, 0.25, 0.24)),
    )
    return {
        "scenario_id": "distributed_weak_clues",
        "purpose": "Several weaker but complementary memories must survive stronger repetitive distractors.",
        "distractors": distractors,
        **_evaluate(
            packet,
            required=tuple(item.event_id for item in clues),
            packet_limit=packet_limit,
        ),
    }


def _near_duplicate_flood(conn, *, distractors: int, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "Orion deployment used blue canary ring because compliance required staged rollback",
    )
    for index in range(distractors):
        _record(conn, conversation_id, f"Orion deployment update duplicate-{index}")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="Orion deployment",
        anchors=(),
        required=(target.event_id,),
    )
    packet = _pool(
        conn,
        corpus,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.SPECIFIC_DETAIL_MISSING,
        telemetry=RetrievalTelemetry(candidate_scores=(0.7, 0.3)),
    )
    return {
        "scenario_id": "near_duplicate_flood",
        "purpose": "Repeated near-duplicate updates should not crowd out one information-dense older event.",
        "distractors": distractors,
        **_evaluate(
            packet,
            required=(target.event_id,),
            packet_limit=packet_limit,
        ),
    }


def _temporal_distribution(conn, *, distractors: int, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    required = []
    required.append(_record(conn, conversation_id, "Atlas design inception chose append only ledger"))
    for index in range(distractors // 2):
        _record(conn, conversation_id, f"Atlas design routine update-{index}")
    required.append(_record(conn, conversation_id, "Atlas design midcourse introduced working state"))
    for index in range(distractors - distractors // 2):
        _record(conn, conversation_id, f"Atlas design routine revision-{index}")
    required.append(_record(conn, conversation_id, "Atlas design final retained stateless workers"))
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="Atlas design",
        anchors=(),
        required=tuple(item.event_id for item in required),
    )
    packet = _pool(
        conn,
        corpus,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.MISSING_CONTEXT,
        telemetry=RetrievalTelemetry(candidate_scores=(0.4, 0.3, 0.3)),
    )
    return {
        "scenario_id": "temporally_distributed_evidence",
        "purpose": "A bounded packet should preserve distinct evidence from early, middle, and late project history.",
        "distractors": distractors,
        **_evaluate(
            packet,
            required=tuple(item.event_id for item in required),
            packet_limit=packet_limit,
        ),
    }


def _retention_across_rounds(conn, *, distractors: int, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "escape correction canonical fact RETAINED-TARGET",
    )
    first = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="escape correction",
        anchors=(),
        required=(target.event_id,),
    )
    first_pool = _pool(
        conn,
        first,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.SPECIFIC_DETAIL_MISSING,
        telemetry=RetrievalTelemetry(candidate_scores=(0.8, 0.2)),
    )
    retained = compose_coverage_aware(first_pool.items, limit=packet_limit).items

    for index in range(distractors):
        _record(conn, conversation_id, f"obsolete explanation reinforcement-{index}")
    second = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="obsolete explanation reinforcement",
        anchors=(),
        required=(target.event_id,),
    )
    second_pool = _pool(
        conn,
        second,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.MISSING_CONTEXT,
        telemetry=RetrievalTelemetry(candidate_scores=(0.6, 0.4)),
    )
    return {
        "scenario_id": "retained_evidence_across_attention_shift",
        "purpose": "A later attention shift must not silently erase uniquely useful evidence surfaced in an earlier pass.",
        "distractors": distractors,
        **_evaluate(
            second_pool,
            required=(target.event_id,),
            packet_limit=packet_limit,
            retained=retained,
        ),
    }


def _unsupported_query(conn, *, pool_limit: int, packet_limit: int):
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    _record(conn, conversation_id, "known ledger item about apples")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="nonexistent zircon submarine treaty",
        anchors=(),
        required=(),
    )
    packet = _pool(
        conn,
        corpus,
        pool_limit=pool_limit,
        uncertainty=MemoryUncertainty.MISSING_CONTEXT,
        telemetry=RetrievalTelemetry(candidate_scores=()),
    )
    current = list(packet.items[:packet_limit])
    composed = compose_coverage_aware(packet.items, limit=packet_limit)
    return {
        "scenario_id": "unsupported_query_abstention",
        "purpose": "Composition must not manufacture evidence when retrieval returns no historical support.",
        "candidate_pool_size": len(packet.items),
        "current_top_k": {
            "success": not current,
            "event_ids": [str(value) for value in _ids(current)],
        },
        "coverage_aware": {
            "success": not composed.items,
            "event_ids": [str(value) for value in _ids(composed.items)],
            "decisions": _serialize_composition(composed),
        },
    }


def _head_to_head(cases: list[dict[str, object]]) -> dict[str, int]:
    counts = {
        "coverage_aware_only": 0,
        "top_k_only": 0,
        "both": 0,
        "neither": 0,
    }
    for case in cases:
        coverage = bool(case["coverage_aware"]["success"])
        top_k = bool(case["current_top_k"]["success"])
        if coverage and top_k:
            counts["both"] += 1
        elif coverage:
            counts["coverage_aware_only"] += 1
        elif top_k:
            counts["top_k_only"] += 1
        else:
            counts["neither"] += 1
    return counts


def run_benchmark(*, stress: bool) -> dict[str, object]:
    conn = db.get_connection()
    try:
        database_name = _prepare_database(conn)
        pool_limit = 64 if stress else 32
        packet_limit = 6
        cases = [
            _equal_term_old_memory(
                conn,
                distractors=40 if stress else 12,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
            _correction_pair(
                conn,
                distractors=24 if stress else 10,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
            _weak_clues(
                conn,
                distractors=36 if stress else 18,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
            _near_duplicate_flood(
                conn,
                distractors=50 if stress else 18,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
            _temporal_distribution(
                conn,
                distractors=24 if stress else 10,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
            _retention_across_rounds(
                conn,
                distractors=40 if stress else 12,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
            _unsupported_query(
                conn,
                pool_limit=pool_limit,
                packet_limit=packet_limit,
            ),
        ]
        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-003",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candidate_pool_limit": pool_limit,
            "final_packet_limit": packet_limit,
            "evaluation_boundary": (
                "Adaptive retrieval is frozen. Current top-k and coverage-aware composition "
                "receive the identical ordered candidate pool and final packet budget."
            ),
            "head_to_head": _head_to_head(cases),
            "cases": cases,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark(stress=args.stress)
    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"MEM-ADAPT-003_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "head_to_head": result["head_to_head"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
