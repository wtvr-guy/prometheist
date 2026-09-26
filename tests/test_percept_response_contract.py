from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from prometheist import jit_memory
from prometheist.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistry,
    RegisteredCapability,
)
from prometheist.models import MemoryNeed, MemoryPacket
from prometheist.percept_response_runtime import (
    MemorySufficiencyDecision,
    PreCognitiveDisposition,
    _compose_memory_package,
    _effective_adaptive_stage,
    _external_capability_catalog,
)
from prometheist.percept_response_worker import UserPromptWorkSelection


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


def test_empty_self_model_packet_cannot_be_accepted_as_sufficient(monkeypatch) -> None:
    packet = MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="Which option would I probably choose?"),
        supported=False,
        items=[],
    )

    class IncorrectlyPermissiveComposer:
        def assess_memory_sufficiency(
            self,
            percept,
            memory_packet,
            self_context=None,
            *,
            person_history_required=False,
        ):
            del percept, memory_packet, self_context
            assert person_history_required is True
            return MemorySufficiencyDecision(
                sufficient=True,
                memory_deficit=None,
            )

    monkeypatch.setattr(
        "jit_agent.percept_response_runtime._adaptive_recall",
        lambda *args, **kwargs: packet,
    )

    package = _compose_memory_package(
        None,
        IncorrectlyPermissiveComposer(),
        SimpleNamespace(user_text="Which option would I probably choose?"),
        packet,
        [],
        person_history_required=True,
    )

    assert package.sufficient is False
    assert package.adaptive_recall_rounds == 1
    assert "history-dependent request" in package.unresolved_memory_deficit


def test_legacy_memory_research_modes_are_not_pre_cognitive_capabilities() -> None:
    catalog = _external_capability_catalog(DEFAULT_REGISTRY)
    assert catalog == ()


def test_hidden_non_memory_service_is_not_exposed_as_pre_cognitive_work() -> None:
    registry = CapabilityRegistry(
        (
            RegisteredCapability(
                descriptor=CapabilityDescriptor(
                    capability_id="internal_maintenance",
                    kind=CapabilityKind.SERVICE,
                    description="Internal maintenance only.",
                ),
                routing_terms=("maintenance",),
                executor="maintenance",
                selectable_as_external_work=False,
            ),
        )
    )

    assert _external_capability_catalog(registry) == ()


def test_adaptive_recall_falls_back_to_broad_when_no_focus_candidate_exists() -> None:
    packet = MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="an unremembered fact"),
        supported=False,
        items=[],
    )
    stage, focus_ids = _effective_adaptive_stage(
        jit_memory.AdaptiveRecallStage.ASSOCIATIVE,
        packet,
    )
    assert stage is jit_memory.AdaptiveRecallStage.BROAD
    assert focus_ids == []
