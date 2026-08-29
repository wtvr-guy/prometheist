from __future__ import annotations

import uuid

import pytest

from jit_agent import jit_memory
from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.models import MemoryNeed, MemoryPacket
from jit_agent.percept_response_runtime import (
    MemorySufficiencyDecision,
    PreCognitiveDisposition,
    _effective_adaptive_profile,
    _external_capability_catalog,
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
