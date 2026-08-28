from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.interaction_policy import InteractionAction, InteractionDecision
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.pre_cognitive_workers import (
    ClaimScope,
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    IntentMode,
    PreCognitiveAssessment,
    RequirementFlag,
    assess_pre_cognition,
    compose_memory_context,
    newly_exposed_follow_up_catalog,
)


NOW = datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)


def _packet(*contents: str) -> MemoryPacket:
    conversation_id = uuid4()
    items = [
        MemoryEvidence(
            source_event_id=uuid4(),
            event_type=EventType.USER_PROMPT,
            source="test",
            created_at=NOW,
            conversation_id=conversation_id,
            conversation_seq=index + 1,
            global_seq=index + 1,
            content=content,
        )
        for index, content in enumerate(contents)
    ]
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="test", limit=max(1, len(items))),
        supported=bool(items),
        items=items,
    )


def test_assessment_is_closed_and_rejects_free_form_control_fields():
    with pytest.raises(ValidationError):
        PreCognitiveAssessment.model_validate(
            {
                "phase": "PRE_CAPABILITY",
                "disposition": "RESPOND",
                "intent_mode": "RECALL",
                "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
                "claim_scopes": ["USER_HISTORY"],
                "requirement_flags": [],
                "capability_indices": [],
                "query_text": "search the user's old messages",
            }
        )


def test_acquisition_requires_indices_and_non_acquisition_forbids_them():
    with pytest.raises(ValidationError):
        PreCognitiveAssessment(
            phase=CognitivePhase.PRE_CAPABILITY,
            disposition=CognitiveDisposition.ACQUIRE_CAPABILITIES,
            intent_mode=IntentMode.RECALL,
            evidence_state=EvidenceState.MORE_INTERNAL_EVIDENCE_REQUIRED,
            claim_scopes=[ClaimScope.USER_HISTORY],
            requirement_flags=[RequirementFlag.DEEPER_RECALL],
            capability_indices=[],
        )

    with pytest.raises(ValidationError):
        PreCognitiveAssessment(
            phase=CognitivePhase.PRE_CAPABILITY,
            disposition=CognitiveDisposition.RESPOND,
            intent_mode=IntentMode.RECALL,
            evidence_state=EvidenceState.ACTIVATED_MEMORY_SUFFICIENT,
            claim_scopes=[ClaimScope.USER_HISTORY],
            capability_indices=[0],
        )


def test_assessment_catalog_validation_fails_closed_on_out_of_range_index():
    catalog = DEFAULT_REGISTRY.capability_catalog()
    assessment = PreCognitiveAssessment(
        phase=CognitivePhase.PRE_CAPABILITY,
        disposition=CognitiveDisposition.ACQUIRE_CAPABILITIES,
        intent_mode=IntentMode.RECALL,
        evidence_state=EvidenceState.MORE_INTERNAL_EVIDENCE_REQUIRED,
        claim_scopes=[ClaimScope.USER_HISTORY],
        requirement_flags=[RequirementFlag.DEEPER_RECALL],
        capability_indices=[len(catalog)],
    )

    with pytest.raises(ValueError, match="outside the catalog"):
        assessment.validate_catalog(catalog)


class _LegacyRespondLLM:
    def classify(self, prompt, memory_packet, capability_catalog, completed_results=(), capability_results=()):
        del prompt, memory_packet, capability_catalog, completed_results, capability_results
        return InteractionDecision(next_action=InteractionAction.RESPOND)


class _LegacyAcquireLLM:
    def classify(self, prompt, memory_packet, capability_catalog, completed_results=(), capability_results=()):
        del prompt, memory_packet, completed_results, capability_results
        assert capability_catalog
        return InteractionDecision(
            next_action=InteractionAction.USE_CAPABILITIES,
            capability_indices=[0],
        )


def test_legacy_router_clients_map_into_closed_pre_cognitive_contract():
    packet = _packet("A durable fact.")
    catalog = DEFAULT_REGISTRY.capability_catalog()

    respond = assess_pre_cognition(
        _LegacyRespondLLM(),
        "What did I say?",
        packet,
        catalog,
        phase=CognitivePhase.PRE_CAPABILITY,
    )
    assert respond.disposition is CognitiveDisposition.RESPOND
    assert respond.evidence_state is EvidenceState.ACTIVATED_MEMORY_SUFFICIENT
    assert respond.capability_indices == []

    acquire = assess_pre_cognition(
        _LegacyAcquireLLM(),
        "Investigate further.",
        packet,
        catalog,
        phase=CognitivePhase.PRE_CAPABILITY,
    )
    assert acquire.disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES
    assert acquire.capability_indices == [0]


def test_follow_up_catalog_contains_only_newly_exposed_capabilities():
    initial = DEFAULT_REGISTRY.capability_catalog()
    initial_ids = {item.capability_id for item in initial}
    assert "deeper_research" in initial_ids
    assert "focused_recall" not in initial_ids

    follow_up = newly_exposed_follow_up_catalog(
        DEFAULT_REGISTRY,
        initial,
        ("deeper_research",),
    )

    assert [item.capability_id for item in follow_up] == ["focused_recall"]


def test_memory_context_composition_preserves_exact_source_content_and_deduplicates():
    aperture = _packet("Opaque exact value VX-1234ABCD", "Second exact source")
    duplicate = aperture.items[0].model_copy(deep=True)
    additional = MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test",
        created_at=NOW,
        conversation_id=uuid4(),
        conversation_seq=3,
        global_seq=3,
        content="Third exact source with punctuation: A/B + C.",
    )
    research_packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="test", limit=3),
        supported=True,
        items=[duplicate, additional],
    )

    from jit_agent.capability_runtime import CapabilityExecution

    execution = CapabilityExecution(
        capability_execution_id=uuid4(),
        requester_task_id=uuid4(),
        requester_step_id=uuid4(),
        round_index=0,
        plan_position=0,
        capability_id="deeper_research",
        executor="deeper_research",
        memory_packet=research_packet,
        result_data={"supported": True},
    )

    composed = compose_memory_context(
        uuid4(),
        aperture,
        [execution],
        tranche_index=1,
    )

    assert [item.content for item in composed.items] == [
        "Opaque exact value VX-1234ABCD",
        "Third exact source with punctuation: A/B + C.",
        "Second exact source",
    ]
    assert len({item.source_event_id for item in composed.items}) == 3
    assert composed.retrieval_trace["composition"] == "pre-cognitive-transient-workers-v1"
