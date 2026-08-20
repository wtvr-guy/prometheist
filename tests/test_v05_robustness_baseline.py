from pathlib import Path

from jit_agent.derived_associative_benchmark import run_derived_benchmark


ROOT = Path(__file__).resolve().parent.parent
MORGAN = ROOT / "benchmarks" / "morgan_reyes_v05_robustness.json"


def test_v05_robustness_baseline_freezes_v04_behavior():
    """Freeze the v0.4 mechanism before changing retrieval policy in v0.5.

    This is intentionally not a v0.5 acceptance target. It records the exact
    behavior of the existing v0.4 derivation/recall mechanism against the new
    adversarial corpus so subsequent changes can be measured against a stable
    baseline rather than an anecdotal before/after comparison.
    """
    result = run_derived_benchmark(MORGAN)

    assert result.question_count == 7
    assert result.successful_questions == 5
    assert result.question_success_rate == 5 / 7
    assert result.evidence_recall == 4 / 5
    assert result.unknown_abstention_rate == 0.5
    assert len(result.failures) == 2
    assert result.failures[0].startswith("mq04:")
    assert result.failures[1].startswith("mq06:")
