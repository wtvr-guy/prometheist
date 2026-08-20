from pathlib import Path

from jit_agent.synthetic_benchmark import run_benchmark


def test_synthetic_life_benchmark_sets_a_retrieval_regression_floor():
    path = Path(__file__).resolve().parents[1] / "benchmarks" / "jordan_vale_v1.json"
    result = run_benchmark(path)

    # v0.2 is intentionally lexical/cue based rather than a finished
    # associative memory system.  These floors prevent regressions while
    # preserving difficult failures for v0.3 to solve.
    assert result.question_success_rate >= 0.75, result.failures
    assert result.evidence_recall >= 0.80, result.failures
    assert result.unknown_abstention_rate == 1.0, result.failures
