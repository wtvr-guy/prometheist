"""Environment-calibrated resource policy for the current native v0.7 target.

The generic ResourceSafetyPolicy remains deliberately conservative for unknown
hosts. Production native execution uses this explicit, versioned calibration so
measured target-host assumptions are never confused with universal defaults.

Cold local-LLM memory is model-specific. Reusing the Qwen3:4b calibration for a
larger model would under-reserve RAM before Ollama loads it, so known local model
targets receive explicit conservative cold-load budgets. Unknown models fall back
to a deliberately larger safety budget unless the operator supplies an explicit
``OLLAMA_COLD_MEMORY_MIB`` override.
"""
from __future__ import annotations

import os

from jit_agent.attention_observation import ResourceSafetyPolicy
from jit_agent.ollama_runtime import configured_ollama_model


NATIVE_RESOURCE_POLICY_VERSION = "v0.7-native-calibration-v2"
QWEN3_4B_INSTRUCT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
MINISTRAL_3_8B_INSTRUCT_MODEL = "ministral-3:8b-instruct-2512-q4_K_M"

_NATIVE_LLM_MEMORY_MIB_BY_MODEL = {
    QWEN3_4B_INSTRUCT_MODEL.casefold(): 3_072,
    MINISTRAL_3_8B_INSTRUCT_MODEL.casefold(): 7_168,
}
_UNKNOWN_MODEL_COLD_MEMORY_MIB = 8_192


def _canonical_model_name(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized:
        raise ValueError("Ollama model name must not be empty")
    leaf = normalized.rsplit("/", 1)[-1]
    if ":" not in leaf:
        normalized += ":latest"
    return normalized


def native_llm_process_memory_mib(model: str | None = None) -> int:
    """Return the conservative cold-load RAM reservation for one local LLM.

    ``OLLAMA_COLD_MEMORY_MIB`` is an explicit operator calibration override. It
    is intentionally not inferred from parameter count: quantization, KV cache,
    runtime overhead, and offload behavior all affect actual resident memory.
    """

    override = os.environ.get("OLLAMA_COLD_MEMORY_MIB")
    if override is not None:
        try:
            parsed = int(override)
        except ValueError as exc:
            raise ValueError("OLLAMA_COLD_MEMORY_MIB must be an integer MiB value") from exc
        if parsed < 512:
            raise ValueError("OLLAMA_COLD_MEMORY_MIB must be at least 512 MiB")
        return parsed

    configured = _canonical_model_name(model or configured_ollama_model())
    return _NATIVE_LLM_MEMORY_MIB_BY_MODEL.get(
        configured,
        _UNKNOWN_MODEL_COLD_MEMORY_MIB,
    )


def native_resource_safety_policy(
    *,
    model: str | None = None,
) -> ResourceSafetyPolicy:
    """Return the frozen native policy with model-aware local-LLM RAM gating."""

    return ResourceSafetyPolicy(
        policy_version=NATIVE_RESOURCE_POLICY_VERSION,
        cpu_system_headroom_percent=10,
        memory_system_headroom_percent=10,
        memory_system_headroom_min_mib=1024,
        uncertainty_headroom_percent=5,
        default_llm_process_memory_mib=native_llm_process_memory_mib(model),
        default_process_memory_mib=512,
        default_process_cpu_units=1,
        llm_concurrency_limit=1,
    )
