from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "compare_evidence_composers_v2.py"


def _quick_result():
    namespace = runpy.run_path(str(BENCHMARK), run_name="composer_v2_benchmark_test")
    return namespace["run_benchmark"](stress=False)


def test_v2_combined_observable_corpus_has_no_known_regression():
    result = _quick_result()
    observable = [case for case in result["cases"] if case["observable"]]

    failures = [
        case["scenario_id"]
        for case in observable
        if not case["relevance_coverage_v2"]["success"]
    ]

    assert failures == []


def test_v2_preserves_both_previous_failure_regimes():
    result = _quick_result()
    cases = {case["scenario_id"]: case for case in result["cases"]}

    assert cases["duplicate_pressure_old_target"]["relevance_coverage_v2"]["success"] is True
    assert cases["distributed_weak_clues"]["relevance_coverage_v2"]["success"] is True
    assert cases["numeric_payload_attack"]["relevance_coverage_v2"]["success"] is True
    assert cases["random_token_novelty_attack"]["relevance_coverage_v2"]["success"] is True
    assert cases["stale_retained_attack"]["relevance_coverage_v2"]["success"] is True
    assert cases["independent_corroboration"]["relevance_coverage_v2"]["success"] is True
    assert cases["coverage_positive_control"]["relevance_coverage_v2"]["success"] is True


def test_unobservable_corroboration_is_reported_as_diagnostic_not_hidden():
    result = _quick_result()
    case = next(
        case
        for case in result["cases"]
        if case["scenario_id"] == "unobservable_corroboration_diagnostic"
    )

    assert case["observable"] is False
    assert result["summary"]["diagnostic_case_count"] == 1
