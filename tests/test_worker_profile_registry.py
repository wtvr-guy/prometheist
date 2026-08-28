from __future__ import annotations

import pytest

from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.worker_profile_registry import (
    PRIMARY_OLLAMA_MODEL_POOL,
    PersonaAccess,
    WorkerExecutionMode,
    default_worker_profile_registry,
)


def test_all_production_llm_workers_share_one_model_pool() -> None:
    registry = default_worker_profile_registry()
    profiles = registry.llm_profiles()

    assert profiles
    assert {profile.model_pool_id for profile in profiles} == {PRIMARY_OLLAMA_MODEL_POOL}
    assert all(profile.system_prompt for profile in profiles)
    assert all(profile.system_prompt_sha256 for profile in profiles)


def test_persona_is_response_only() -> None:
    registry = default_worker_profile_registry()
    persona_profiles = [
        profile
        for profile in registry.profiles()
        if profile.persona_access is PersonaAccess.REQUIRED
    ]

    assert [profile.worker_profile_id for profile in persona_profiles] == ["final_response"]
    assert all(
        profile.persona_access is PersonaAccess.FORBIDDEN
        for profile in registry.llm_profiles()
        if profile.worker_profile_id != "final_response"
    )


def test_llm_packet_projection_drops_unregistered_application_state() -> None:
    registry = default_worker_profile_registry()
    profile = registry.get("memory_research_candidate_selector")
    source = {
        "current_task": "Find the best memory candidate.",
        "candidate_memory": {"items": ["a", "b"]},
        "personality_prompt": "must never reach this worker",
        "capability_catalog": ["unneeded"],
        "full_transcript": "unneeded",
    }

    packet = profile.packet_contract.project_packet(source)

    assert packet == {
        "current_task": "Find the best memory candidate.",
        "candidate_memory": {"items": ["a", "b"]},
    }
    profile.packet_contract.validate_packet(packet)


def test_worker_packet_rejects_missing_or_extra_fields() -> None:
    profile = default_worker_profile_registry().get("response_policy_classifier")

    with pytest.raises(ValueError, match="missing required fields"):
        profile.packet_contract.validate_packet({})
    with pytest.raises(ValueError, match="unregistered fields"):
        profile.packet_contract.validate_packet(
            {"current_percept": "hello", "personality_prompt": "not allowed"}
        )


def test_final_response_packet_explicitly_requires_personality_and_terminal_control() -> None:
    profile = default_worker_profile_registry().get("final_response")

    assert profile.execution_mode is WorkerExecutionMode.LLM
    assert "personality_prompt" in profile.packet_contract.required_fields
    assert "final_response_directive" in profile.packet_contract.required_fields
    assert "capability_catalog" not in profile.packet_contract.allowed_fields
    assert "full_transcript" not in profile.packet_contract.allowed_fields


def test_every_capability_resolves_to_private_deterministic_root_worker() -> None:
    registry = default_worker_profile_registry()

    for descriptor in DEFAULT_REGISTRY.descriptors():
        root = registry.resolve_capability(descriptor.capability_id)
        assert root.execution_mode is WorkerExecutionMode.DETERMINISTIC
        assert root.persona_access is PersonaAccess.FORBIDDEN
        assert root.system_prompt is None


def test_composite_capabilities_delegate_to_narrow_llm_workers() -> None:
    registry = default_worker_profile_registry()

    expected = {
        "deeper_research": "memory_research_candidate_selector",
        "cross_reference": "cross_reference_candidate_selector",
        "focused_recall": "focused_recall_candidate_selector",
    }
    for capability_id, delegated_profile_id in expected.items():
        root = registry.resolve_capability(capability_id)
        delegates = registry.delegated_profiles(root.worker_profile_id)
        assert [profile.worker_profile_id for profile in delegates] == [delegated_profile_id]
        assert delegates[0].execution_mode is WorkerExecutionMode.LLM
        assert delegates[0].persona_access is PersonaAccess.FORBIDDEN


def test_registry_validates_all_capability_and_delegate_bindings() -> None:
    default_worker_profile_registry().validate_capability_bindings()
