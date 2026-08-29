from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "redteam_evidence_composer.py"


def _namespace(name: str):
    return runpy.run_path(str(BENCHMARK), run_name=name)


def _case(result, scenario_id: str):
    return next(case for case in result["cases"] if case["scenario_id"] == scenario_id)


def test_redteam_exposes_numeric_payload_blindness_without_tuning_composer():
    result = _namespace("composer_redteam_numeric")["run_benchmark"](stress=False)
    case = _case(result, "numeric_fact_blindness")
    assert case["top_k"]["success"] is True
    assert case["coverage_aware"]["success"] is False


def test_redteam_exposes_stale_retention_poisoning():
    result = _namespace("composer_redteam_retention")["run_benchmark"](stress=False)
    case = _case(result, "stale_retention_poisoning")
    assert case["top_k"]["success"] is True
    assert case["coverage_aware"]["success"] is False
    assert case["retained_count"] == 1


def test_redteam_exposes_irrelevant_novelty_attack():
    result = _namespace("composer_redteam_novelty")["run_benchmark"](stress=False)
    case = _case(result, "random_token_novelty_attack")
    assert case["top_k"]["success"] is True
    assert case["coverage_aware"]["success"] is False


def test_redteam_keeps_positive_control_for_composer_strength():
    result = _namespace("composer_redteam_positive_control")["run_benchmark"](stress=False)
    case = _case(result, "composer_positive_control")
    assert case["top_k"]["success"] is False
    assert case["coverage_aware"]["success"] is True


def test_redteam_is_deterministic_except_generation_timestamp():
    namespace = _namespace("composer_redteam_determinism")
    first = namespace["run_benchmark"](stress=True)
    second = namespace["run_benchmark"](stress=True)
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_both_policies_remain_bounded_to_same_packet_size():
    result = _namespace("composer_redteam_bounds")["run_benchmark"](stress=True)
    limit = result["final_packet_limit"]
    for case in result["cases"]:
        assert len(case["top_k"]["event_ids"]) <= limit
        assert len(case["coverage_aware"]["event_ids"]) <= limit
