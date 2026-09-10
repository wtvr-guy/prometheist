from __future__ import annotations

import uuid

import pytest

from jit_agent import jit_memory, percept_response_runtime
from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.interaction_policy import Percept, PerceptKind, UserPromptPercept
from jit_agent.models import MemoryNeed, MemoryPacket
from jit_agent.percept_response_runtime import (
    MemorySufficiencyDecision,
    PreCognitiveDisposition,
    begin_percept,
    begin_user_prompt_percept,
    _effective_adaptive_profile,
    _external_capability_catalog,
    handle_percept_in_worker_processes,
    handle_user_prompt_percept_in_worker_processes,
)
from jit_agent.percept_response_worker import UserPromptWorkSelection


def test_user_prompt_work_selection_has_no_response_choice() -> None:
    selection = UserPromptWorkSelection(capability_indices=[])
    assert selection.capability_indices == []
    assert "response_required" not in UserPromptWorkSelection.model_fields


def test_persisted_user_prompt_disposition_records_required_response() -> None:
    decision = PreCognitiveDisposition(response_required=True, capability_indices=[])
    assert decision.response_required is True
    assert decision.capability_indices == []


def test_percept_contract_includes_non_user_classes_without_required_response() -> None:
    observation = Percept(
        kind=PerceptKind.SENSOR_OBSERVATION,
        payload_text="temperature rose by 5C",
        response_required=False,
    )
    assert observation.kind is PerceptKind.SENSOR_OBSERVATION
    assert observation.response_required is False


def test_user_prompt_percept_contract_is_explicitly_scoped_to_user_prompts() -> None:
    percept = UserPromptPercept(
        conversation_id=uuid.uuid4(),
        payload_text="hello",
    )
    assert percept.kind is PerceptKind.USER_PROMPT
    assert percept.response_required is True
    assert percept.user_text == "hello"


def test_user_prompt_entrypoints_remain_compatibility_wrapped() -> None:
    assert begin_percept is not begin_user_prompt_percept
    assert handle_percept_in_worker_processes is not handle_user_prompt_percept_in_worker_processes


def test_begin_percept_wraps_raw_input_as_user_prompt_percept(monkeypatch) -> None:
    conversation_id = uuid.uuid4()
    captured: dict[str, UserPromptPercept] = {}

    def fake_begin(conn, percept, **kwargs):
        del conn, kwargs
        captured["percept"] = percept
        return "wrapped"

    monkeypatch.setattr(percept_response_runtime, "begin_user_prompt_percept", fake_begin)

    result = percept_response_runtime.begin_percept(object(), "hello", conversation_id)

    assert result == "wrapped"
    assert captured["percept"] == UserPromptPercept(
        conversation_id=conversation_id,
        payload_text="hello",
    )


def test_handle_percept_wraps_raw_input_as_user_prompt_percept(monkeypatch) -> None:
    conversation_id = uuid.uuid4()
    captured: dict[str, UserPromptPercept] = {}

    def fake_handle(conn, percept, **kwargs):
        del conn, kwargs
        captured["percept"] = percept
        return "handled"

    monkeypatch.setattr(
        percept_response_runtime,
        "handle_user_prompt_percept_in_worker_processes",
        fake_handle,
    )

    result = percept_response_runtime.handle_percept_in_worker_processes(
        object(),
        "hello",
        conversation_id,
    )

    assert result == "handled"
    assert captured["percept"] == UserPromptPercept(
        conversation_id=conversation_id,
        payload_text="hello",
    )


def test_pre_cognitive_disposition_rejects_duplicate_indices() -> None:
    with pytest.raises(ValueError):
        PreCognitiveDisposition(response_required=True, capability_indices=[0, 0])


def test_composer_sufficient_contract_has_no_deficit() -> None:
    decision = MemorySufficiencyDecision(sufficient=True, memory_deficit=None)
    assert decision.sufficient is True
    assert decision.memory_deficit is None


def test_composer_insufficient_contract_requires_semantic_deficit() -> None:
    with pytest.raises(ValueError):
        MemorySufficiencyDecision(sufficient=False, memory_deficit=None)


def test_legacy_memory_research_modes_are_not_pre_cognitive_capabilities() -> None:
    catalog = _external_capability_catalog(DEFAULT_REGISTRY)
    assert catalog == ()


def test_adaptive_recall_falls_back_to_standard_when_no_focus_candidate_exists() -> None:
    packet = MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="an unremembered fact"),
        supported=False,
        items=[],
    )
    profile, focus_ids = _effective_adaptive_profile(
        jit_memory.MemoryRecallProfile.DEEPER_RESEARCH,
        packet,
    )
    assert profile is jit_memory.MemoryRecallProfile.STANDARD
    assert focus_ids == []
