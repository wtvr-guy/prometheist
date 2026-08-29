from pathlib import Path
import runpy

from jit_agent import db


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "compare_evidence_composers.py"


def _namespace(name: str):
    return runpy.run_path(str(BENCHMARK), run_name=name)


def test_coverage_composer_recovers_old_tied_memory_without_larger_final_packet():
    namespace = _namespace("evidence_composer_equal_term_integration")
    conn = db.get_connection()
    try:
        case = namespace["_equal_term_old_memory"](
            conn,
            distractors=12,
            pool_limit=32,
            packet_limit=6,
        )
    finally:
        conn.close()

    assert case["current_top_k"]["success"] is False
    assert case["coverage_aware"]["success"] is True


def test_coverage_composer_preserves_distributed_weak_clues():
    namespace = _namespace("evidence_composer_weak_clues_integration")
    conn = db.get_connection()
    try:
        case = namespace["_weak_clues"](
            conn,
            distractors=18,
            pool_limit=32,
            packet_limit=6,
        )
    finally:
        conn.close()

    assert case["current_top_k"]["success"] is False
    assert case["coverage_aware"]["success"] is True


def test_coverage_composer_retains_unique_prior_evidence_across_attention_shift():
    namespace = _namespace("evidence_composer_retention_integration")
    conn = db.get_connection()
    try:
        case = namespace["_retention_across_rounds"](
            conn,
            distractors=12,
            pool_limit=32,
            packet_limit=6,
        )
    finally:
        conn.close()

    assert case["current_top_k"]["success"] is False
    assert case["coverage_aware"]["success"] is True


def test_coverage_composer_preserves_unsupported_query_abstention():
    namespace = _namespace("evidence_composer_abstention_integration")
    conn = db.get_connection()
    try:
        case = namespace["_unsupported_query"](
            conn,
            pool_limit=32,
            packet_limit=6,
        )
    finally:
        conn.close()

    assert case["current_top_k"]["success"] is True
    assert case["coverage_aware"]["success"] is True
    assert case["coverage_aware"]["event_ids"] == []
