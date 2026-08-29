from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
BENCH = runpy.run_path(
    str(ROOT / "benchmarks" / "compare_cognition_models.py"),
    run_name="test_mem_adapt_007_contract",
)


def test_mem_adapt_007_defaults_to_nonthinking_ministral_instruct_candidate():
    assert BENCH["DEFAULT_MODEL"] == "ministral-3:8b-instruct-2512-q4_K_M"
    assert BENCH["CONTROL_MODEL"] == "qwen3:4b-instruct-2507-q4_K_M"
    assert BENCH["PACKET_LIMIT"] == 6


def test_mem_adapt_007_experimental_gate_is_larger_for_ministral(monkeypatch):
    monkeypatch.delenv("MEM_ADAPT_007_COLD_MEMORY_MIB", raising=False)

    qwen = BENCH["_experimental_resource_policy"](BENCH["CONTROL_MODEL"])
    ministral = BENCH["_experimental_resource_policy"](BENCH["DEFAULT_MODEL"])

    assert qwen.default_llm_process_memory_mib == 3_072
    assert ministral.default_llm_process_memory_mib == 7_168
    assert ministral.llm_concurrency_limit == 1
    assert qwen.llm_concurrency_limit == 1


def test_mem_adapt_007_resource_override_is_experiment_only(monkeypatch):
    monkeypatch.setenv("MEM_ADAPT_007_COLD_MEMORY_MIB", "7552")

    policy = BENCH["_experimental_resource_policy"](BENCH["DEFAULT_MODEL"])

    assert policy.default_llm_process_memory_mib == 7_552
    assert policy.policy_version.endswith(":MEM-ADAPT-007")


def test_value_correctness_distinguishes_format_only_failures():
    value_complete = BENCH["_answer_value_complete"]

    assert value_complete(
        "deployment phase alpha approved | beta | gamma | delta | epsilon | zeta",
        "alpha | beta | gamma | delta | epsilon | zeta",
    )
    assert value_complete(
        "current registry item A1 | item B2 | item C3 | item D4 | item E5 | item F6",
        "A1 | B2 | C3 | D4 | E5 | F6",
    )
    assert not value_complete(
        "<v1> | <v2> | <v3> | <v4> | <v5> | <v6>",
        "10 | 20 | 30 | 40 | 50 | 60",
    )
    assert not value_complete(
        "vault phrase recorded routine duplicate-39",
        "COPPER-LANTERN-47",
    )
