from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
DIAGNOSTIC = ROOT / "benchmarks" / "diagnose_memory_selection_ceiling.py"
SEMANTIC = ROOT / "benchmarks" / "compare_memory_attention_semantics.py"


def test_selection_ceiling_diagnostic_imports_without_running_main():
    namespace = runpy.run_path(
        str(DIAGNOSTIC),
        run_name="adaptive_memory_selection_diagnostic_contract",
    )
    assert callable(namespace["run_diagnostic"])
    assert callable(namespace["_observe_stage"])
    assert callable(namespace["_first_failure"])


def test_semantic_comparison_imports_without_running_main():
    namespace = runpy.run_path(
        str(SEMANTIC),
        run_name="adaptive_memory_semantic_benchmark_contract",
    )
    assert callable(namespace["run_comparison"])
    assert callable(namespace["_correction_pair_case"])
    assert callable(namespace["_multi_anchor_reorientation_case"])
    assert callable(namespace["_abstention_case"])


def test_selection_boundary_distinguishes_packet_failure_from_route_failure():
    namespace = runpy.run_path(
        str(DIAGNOSTIC),
        run_name="adaptive_memory_selection_diagnostic_contract_2",
    )
    observation_type = namespace["StageObservation"]
    first_failure = namespace["_first_failure"]
    observations = [
        observation_type(
            distractor_count=5,
            candidate_limit=600,
            packet_limit=6,
            raw_candidate_count=7,
            target_raw_candidate_rank=6,
            target_admitted_rank=6,
            target_score_total=0.81,
            target_selected_by_kernel=True,
            target_surfaces_in_packet=True,
        ),
        observation_type(
            distractor_count=6,
            candidate_limit=600,
            packet_limit=6,
            raw_candidate_count=8,
            target_raw_candidate_rank=7,
            target_admitted_rank=7,
            target_score_total=0.81,
            target_selected_by_kernel=True,
            target_surfaces_in_packet=False,
        ),
    ]
    assert (
        first_failure(
            observations,
            candidate_limit=600,
            packet_limit=6,
            attribute="target_surfaces_in_packet",
        )
        == 6
    )
    assert (
        first_failure(
            observations,
            candidate_limit=600,
            packet_limit=6,
            attribute="target_selected_by_kernel",
        )
        is None
    )
