from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "compare_evidence_composers_v2.py"


def _namespace():
    return runpy.run_path(str(BENCHMARK), run_name="composer_v2_benchmark_test")


def _result(*, stress: bool):
    return _namespace()["run_benchmark"](stress=stress)


def _observable_failures(result):
    return [
        case["scenario_id"]
        for case in result["cases"]
        if case["observable"] and not case["relevance_coverage_v2"]["success"]
    ]


def test_v2_combined_observable_quick_corpus_has_no_known_regression():
    assert _observable_failures(_result(stress=False)) == []


def test_v2_combined_observable_stress_corpus_has_no_known_regression():
    assert _observable_failures(_result(stress=True)) == []


def test_v2_preserves_both_previous_failure_regimes():
    result = _result(stress=False)
    cases = {case["scenario_id"]: case for case in result["cases"]}

    assert cases["duplicate_pressure_old_target"]["relevance_coverage_v2"]["success"] is True
    assert cases["distributed_weak_clues"]["relevance_coverage_v2"]["success"] is True
    assert cases["numeric_payload_attack"]["relevance_coverage_v2"]["success"] is True
    assert cases["random_token_novelty_attack"]["relevance_coverage_v2"]["success"] is True
    assert cases["stale_retained_attack"]["relevance_coverage_v2"]["success"] is True
    assert cases["independent_corroboration"]["relevance_coverage_v2"]["success"] is True
    assert cases["coverage_positive_control"]["relevance_coverage_v2"]["success"] is True


def test_unobservable_corroboration_is_reported_as_diagnostic_not_hidden():
    result = _result(stress=False)
    case = next(
        case
        for case in result["cases"]
        if case["scenario_id"] == "unobservable_corroboration_diagnostic"
    )

    assert case["observable"] is False
    assert result["summary"]["diagnostic_case_count"] == 1
