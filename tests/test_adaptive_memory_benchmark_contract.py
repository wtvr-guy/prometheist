from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "compare_memory_attention_architectures.py"


def test_adaptive_memory_comparison_benchmark_imports_without_running_main():
    namespace = runpy.run_path(str(BENCHMARK), run_name="adaptive_memory_benchmark_contract")
    assert callable(namespace["run_comparison"])
    assert callable(namespace["_head_to_head"])
    assert callable(namespace["_limits"])


def test_head_to_head_does_not_credit_downstream_when_aperture_already_succeeds():
    namespace = runpy.run_path(str(BENCHMARK), run_name="adaptive_memory_benchmark_contract_2")
    summarize = namespace["_head_to_head"]
    cases = [
        {
            "aperture_already_sufficient": True,
            "observations": [
                {"method": "attention_aperture", "success": True},
                {"method": "adaptive", "success": True},
                {"method": "frozen:DEEPER_RESEARCH", "success": False},
            ],
        },
        {
            "aperture_already_sufficient": False,
            "observations": [
                {"method": "attention_aperture", "success": False},
                {"method": "adaptive", "success": True},
                {"method": "frozen:DEEPER_RESEARCH", "success": False},
            ],
        },
    ]
    result = summarize(cases)
    assert result["aperture_already_sufficient"] == 1
    assert result["adaptive_only"] == 1
    assert result["frozen_only"] == 0
