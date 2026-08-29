import pytest

from jit_agent.native_policy import (
    MINISTRAL_3_8B_INSTRUCT_MODEL,
    NATIVE_RESOURCE_POLICY_VERSION,
    QWEN3_4B_INSTRUCT_MODEL,
    native_llm_process_memory_mib,
    native_resource_safety_policy,
)


def test_native_resource_policy_freezes_qwen4b_calibrated_gates(monkeypatch):
    monkeypatch.delenv("OLLAMA_COLD_MEMORY_MIB", raising=False)
    policy = native_resource_safety_policy(model=QWEN3_4B_INSTRUCT_MODEL)

    assert policy.policy_version == NATIVE_RESOURCE_POLICY_VERSION
    assert policy.cpu_system_headroom_percent == 10
    assert policy.memory_system_headroom_percent == 10
    assert policy.uncertainty_headroom_percent == 5
    assert policy.default_llm_process_memory_mib == 3_072
    assert policy.default_process_memory_mib == 512
    assert policy.llm_concurrency_limit == 1


def test_native_resource_policy_reserves_ministral8b_cold_load(monkeypatch):
    monkeypatch.delenv("OLLAMA_COLD_MEMORY_MIB", raising=False)

    policy = native_resource_safety_policy(model=MINISTRAL_3_8B_INSTRUCT_MODEL)

    assert policy.default_llm_process_memory_mib == 7_168
    assert policy.llm_concurrency_limit == 1


def test_unknown_native_model_uses_larger_fail_safe_budget(monkeypatch):
    monkeypatch.delenv("OLLAMA_COLD_MEMORY_MIB", raising=False)

    assert native_llm_process_memory_mib("unprofiled-local-model:latest") == 8_192


def test_operator_can_override_cold_model_memory_calibration(monkeypatch):
    monkeypatch.setenv("OLLAMA_COLD_MEMORY_MIB", "7552")

    assert native_llm_process_memory_mib(MINISTRAL_3_8B_INSTRUCT_MODEL) == 7_552


def test_invalid_cold_memory_override_fails_closed(monkeypatch):
    monkeypatch.setenv("OLLAMA_COLD_MEMORY_MIB", "not-a-number")
    with pytest.raises(ValueError, match="OLLAMA_COLD_MEMORY_MIB"):
        native_llm_process_memory_mib(MINISTRAL_3_8B_INSTRUCT_MODEL)

    monkeypatch.setenv("OLLAMA_COLD_MEMORY_MIB", "256")
    with pytest.raises(ValueError, match="at least 512"):
        native_llm_process_memory_mib(MINISTRAL_3_8B_INSTRUCT_MODEL)
