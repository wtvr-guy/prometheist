"""Environment-calibrated resource policy for the current native v0.7 target.

The generic ResourceSafetyPolicy remains deliberately conservative for unknown
hosts. Production native execution uses this explicit, versioned calibration so
measured target-host assumptions are never confused with universal defaults.
"""
from __future__ import annotations

from jit_agent.attention_observation import ResourceSafetyPolicy


NATIVE_RESOURCE_POLICY_VERSION = "v0.7-native-calibration-v1"


def native_resource_safety_policy() -> ResourceSafetyPolicy:
    """Return the frozen native policy currently under empirical calibration."""

    return ResourceSafetyPolicy(
        policy_version=NATIVE_RESOURCE_POLICY_VERSION,
        cpu_system_headroom_percent=10,
        memory_system_headroom_percent=10,
        memory_system_headroom_min_mib=1024,
        uncertainty_headroom_percent=5,
        default_llm_process_memory_mib=3072,
        default_process_memory_mib=512,
        default_process_cpu_units=1,
        llm_concurrency_limit=1,
    )
