from __future__ import annotations

import httpx

from jit_agent.attention_observation import HostResourceMetrics
from jit_agent.native_policy import native_resource_safety_policy
from jit_agent.ollama_runtime import OllamaClaimHostResourceProbe, OllamaRuntimeProbe


_MIB = 1024 * 1024


def _client(payload: dict, *, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ps"
        return httpx.Response(status_code, json=payload, request=request)

    return httpx.Client(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )


class FixedHostProbe:
    def capture(self) -> HostResourceMetrics:
        return HostResourceMetrics(
            platform="test",
            logical_cpu_count=8,
            cpu_utilization_percent=10,
            load_1m=0,
            memory_total_mib=16_118,
            memory_available_mib=3_877,
        )


def test_running_model_is_detected_without_loading_it():
    probe = OllamaRuntimeProbe(
        model="qwen3:4b",
        client=_client(
            {
                "models": [
                    {
                        "name": "qwen3:4b",
                        "model": "qwen3:4b",
                        "size": 3_000 * _MIB,
                        "size_vram": 0,
                        "expires_at": "2026-08-27T08:30:00-07:00",
                    }
                ]
            }
        ),
    )

    state = probe.capture()

    assert state.probe_ok is True
    assert state.resident is True
    assert state.reported_name == "qwen3:4b"
    assert state.system_memory_mib == 3_000
    assert state.reusable_memory_credit_mib(native_resource_safety_policy()) == 2_560


def test_running_model_credit_excludes_reported_vram_and_stays_bounded():
    probe = OllamaRuntimeProbe(
        model="qwen3:4b",
        client=_client(
            {
                "models": [
                    {
                        "name": "qwen3:4b",
                        "size": 3_000 * _MIB,
                        "size_vram": 2_000 * _MIB,
                    }
                ]
            }
        ),
    )

    state = probe.capture()

    assert state.system_memory_mib == 1_000
    assert state.reusable_memory_credit_mib(native_resource_safety_policy()) == 1_000


def test_nonresident_or_failed_runtime_probe_earns_zero_credit():
    cold = OllamaRuntimeProbe(
        model="qwen3:4b",
        client=_client({"models": [{"name": "other:latest", "size": 1}]}),
    ).capture()
    failed = OllamaRuntimeProbe(
        model="qwen3:4b",
        client=_client({}, status_code=503),
    ).capture()

    assert cold.probe_ok is True
    assert cold.resident is False
    assert cold.reusable_memory_credit_mib(native_resource_safety_policy()) == 0
    assert failed.probe_ok is False
    assert failed.resident is False
    assert failed.reusable_memory_credit_mib(native_resource_safety_policy()) == 0


def test_claim_probe_credits_only_reusable_resident_system_memory():
    policy = native_resource_safety_policy()
    runtime_probe = OllamaRuntimeProbe(
        model="qwen3:4b",
        client=_client(
            {
                "models": [
                    {
                        "name": "qwen3:4b",
                        "size": 3_000 * _MIB,
                        "size_vram": 0,
                    }
                ]
            }
        ),
    )
    probe = OllamaClaimHostResourceProbe(
        base_probe=FixedHostProbe(),
        runtime_probe=runtime_probe,
        policy=policy,
    )

    effective = probe.capture()

    assert probe.last_physical_metrics is not None
    assert probe.last_physical_metrics.memory_available_mib == 3_877
    assert probe.last_runtime_state is not None
    assert probe.last_runtime_state.resident is True
    assert probe.last_memory_credit_mib == 2_560
    assert effective.memory_available_mib == 6_437
