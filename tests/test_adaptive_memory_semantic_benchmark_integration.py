from pathlib import Path
import runpy

from jit_agent import db


ROOT = Path(__file__).resolve().parent.parent
DIAGNOSTIC = ROOT / "benchmarks" / "diagnose_memory_selection_ceiling.py"
SEMANTIC = ROOT / "benchmarks" / "compare_memory_attention_semantics.py"


def _observation(case, method):
    return next(item for item in case["observations"] if item["method"] == method)


def test_equal_term_target_can_survive_candidate_routing_but_fail_packet_surface():
    namespace = runpy.run_path(
        str(DIAGNOSTIC),
        run_name="adaptive_memory_selection_diagnostic_integration",
    )
    conn = db.get_connection()
    try:
        conversation_id, target, _anchor, prompt = namespace["_build_case"](conn, 6)
        observation = namespace["_observe_stage"](
            conn,
            distractor_count=6,
            candidate_limit=600,
            packet_limit=6,
            target_event_id=target.event_id,
            conversation_id=conversation_id,
            before_global_seq=prompt.global_seq,
            active_count=1,
        )
    finally:
        conn.close()

    assert observation.target_raw_candidate_rank == 7
    assert observation.target_admitted_rank == 7
    assert observation.target_selected_by_kernel is True
    assert observation.target_surfaces_in_packet is False


def test_zero_overlap_anchor_bridge_is_recoverable_by_both_deliberate_strategies():
    namespace = runpy.run_path(
        str(SEMANTIC),
        run_name="adaptive_memory_semantic_integration_bridge",
    )
    conn = db.get_connection()
    try:
        case = namespace["_zero_overlap_bridge_case"](conn)
    finally:
        conn.close()

    assert case["aperture_already_sufficient"] is False
    assert _observation(case, "frozen:DEEPER_RESEARCH")["success"] is True
    assert _observation(case, "adaptive")["success"] is True


def test_multi_anchor_five_hop_case_distinguishes_adaptive_from_cross_reference():
    namespace = runpy.run_path(
        str(SEMANTIC),
        run_name="adaptive_memory_semantic_integration_multi_anchor",
    )
    conn = db.get_connection()
    try:
        case = namespace["_multi_anchor_deep_case"](conn)
    finally:
        conn.close()

    assert case["aperture_already_sufficient"] is False
    assert _observation(case, "frozen:CROSS_REFERENCE")["success"] is False
    assert _observation(case, "adaptive")["success"] is True


def test_unsupported_query_returns_no_historical_evidence():
    namespace = runpy.run_path(
        str(SEMANTIC),
        run_name="adaptive_memory_semantic_integration_abstention",
    )
    conn = db.get_connection()
    try:
        case = namespace["_abstention_case"](conn)
    finally:
        conn.close()

    assert _observation(case, "frozen:STANDARD")["success"] is True
    assert _observation(case, "adaptive")["success"] is True
    assert _observation(case, "frozen:STANDARD")["returned_event_ids"] == ()
    assert _observation(case, "adaptive")["returned_event_ids"] == ()
