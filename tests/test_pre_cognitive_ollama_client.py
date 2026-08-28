import json
import uuid

import pytest
from pydantic import ValidationError

from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.models import MemoryEvidence, MemoryNeed, MemoryPacket, EventType
from jit_agent.pre_cognitive_ollama_client import (
    PreCognitiveDurableResponseOllamaClient,
    canonicalize_pre_cognitive_payload,
    needs_supported_evidence_reconsideration,
    validate_native_assessment_consistency,
)
from jit_agent.pre_cognitive_workers import (
    ClaimScope,
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    IntentMode,
    PreCognitiveAssessment,
)


def _empty_packet() -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="Project Falcon", limit=5),
        supported=False,
        items=[],
    )


def _supported_packet() -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="Which Kestrel rule?", limit=5),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid.uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                created_at="2026-08-28T09:55:09-07:00",
                conversation_id=uuid.uuid4(),
                conversation_seq=1,
                global_seq=1,
                content=(
                    "For Project Kestrel, never use Docker; deploy PostgreSQL directly "
                    "on Windows. I track that constraint under profile VX-ABC12345."
                ),
                score=1.0,
                retrieval_reasons=["ACTIVE_WORKING_STATE"],
                provenance_event_ids=[],
            )
        ],
    )


class _DuplicateStructuredClient(PreCognitiveDurableResponseOllamaClient):
    def __init__(self) -> None:
        pass

    def _structured(self, role, system, user, schema, max_tokens):
        del role, system, user, schema, max_tokens
        return json.dumps(
            {
                "scheme_version": "pre-cognitive-transient-workers-v1",
                "phase": "PRE_CAPABILITY",
                "disposition": "ACQUIRE_CAPABILITIES",
                "intent_mode": "RECALL",
                "evidence_state": "MORE_INTERNAL_EVIDENCE_REQUIRED",
                "claim_scopes": ["USER_HISTORY", "USER_HISTORY", "USER_HISTORY"],
                "requirement_flags": ["DEEPER_RECALL", "DEEPER_RECALL"],
                "capability_indices": [0, 0],
            }
        )


class _ReconsideringStructuredClient(PreCognitiveDurableResponseOllamaClient):
    def __init__(self) -> None:
        self.calls = []

    def _structured(self, role, system, user, schema, max_tokens):
        del system, schema, max_tokens
        self.calls.append((role, user))
        if len(self.calls) == 1:
            return json.dumps(
                {
                    "scheme_version": "pre-cognitive-transient-workers-v1",
                    "phase": "PRE_CAPABILITY",
                    "disposition": "ABSTAIN",
                    "intent_mode": "RECALL",
                    "evidence_state": "INSUFFICIENT_AFTER_AVAILABLE_WORK",
                    "claim_scopes": [],
                    "requirement_flags": [],
                    "capability_indices": [],
                }
            )
        return json.dumps(
            {
                "scheme_version": "pre-cognitive-transient-workers-v1",
                "phase": "PRE_CAPABILITY",
                "disposition": "RESPOND",
                "intent_mode": "RECALL",
                "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
                "claim_scopes": ["USER_HISTORY"],
                "requirement_flags": [],
                "capability_indices": [],
            }
        )


class _PersistentAbstainClient(PreCognitiveDurableResponseOllamaClient):
    def __init__(self) -> None:
        self.calls = 0

    def _structured(self, role, system, user, schema, max_tokens):
        del role, system, user, schema, max_tokens
        self.calls += 1
        return json.dumps(
            {
                "scheme_version": "pre-cognitive-transient-workers-v1",
                "phase": "PRE_CAPABILITY",
                "disposition": "ABSTAIN",
                "intent_mode": "RECALL",
                "evidence_state": "INSUFFICIENT_AFTER_AVAILABLE_WORK",
                "claim_scopes": [],
                "requirement_flags": [],
                "capability_indices": [],
            }
        )


def test_native_pre_cognition_canonicalizes_exact_duplicate_set_members():
    catalog = DEFAULT_REGISTRY.capability_catalog()
    assessment = _DuplicateStructuredClient().assess_pre_cognition(
        "What launch code did I give Project Falcon?",
        _empty_packet(),
        catalog,
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert [value.value for value in assessment.claim_scopes] == ["USER_HISTORY"]
    assert [value.value for value in assessment.requirement_flags] == ["DEEPER_RECALL"]
    assert assessment.capability_indices == [0]


def test_canonicalization_preserves_first_seen_order():
    payload = canonicalize_pre_cognitive_payload(
        {
            "claim_scopes": ["USER_HISTORY", "CURRENT_INPUT", "USER_HISTORY"],
            "requirement_flags": ["EXACT_SOURCE", "DEEPER_RECALL", "EXACT_SOURCE"],
            "capability_indices": [1, 0, 1],
        }
    )
    assert payload == {
        "claim_scopes": ["USER_HISTORY", "CURRENT_INPUT"],
        "requirement_flags": ["EXACT_SOURCE", "DEEPER_RECALL"],
        "capability_indices": [1, 0],
    }


def test_canonicalization_does_not_weaken_closed_enum_validation():
    payload = canonicalize_pre_cognitive_payload(
        {
            "scheme_version": "pre-cognitive-transient-workers-v1",
            "phase": "PRE_CAPABILITY",
            "disposition": "RESPOND",
            "intent_mode": "RECALL",
            "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
            "claim_scopes": ["INVENTED_SCOPE", "INVENTED_SCOPE"],
            "requirement_flags": [],
            "capability_indices": [],
        }
    )
    with pytest.raises(ValidationError):
        PreCognitiveAssessment.model_validate(payload)


def test_terminal_insufficient_state_requires_abstain():
    contradictory = PreCognitiveAssessment(
        phase=CognitivePhase.PRE_CAPABILITY,
        disposition=CognitiveDisposition.RESPOND,
        intent_mode=IntentMode.RECALL,
        evidence_state=EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK,
        claim_scopes=[ClaimScope.USER_HISTORY],
        requirement_flags=[],
        capability_indices=[],
    )
    with pytest.raises(ValueError, match="requires terminal ABSTAIN"):
        validate_native_assessment_consistency(contradictory)


def test_supported_packet_abstain_requests_one_semantic_reconsideration():
    assessment = PreCognitiveAssessment(
        phase=CognitivePhase.PRE_CAPABILITY,
        disposition=CognitiveDisposition.ABSTAIN,
        intent_mode=IntentMode.RECALL,
        evidence_state=EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK,
        claim_scopes=[],
        requirement_flags=[],
        capability_indices=[],
    )
    assert needs_supported_evidence_reconsideration(assessment, _supported_packet())
    assert not needs_supported_evidence_reconsideration(assessment, _empty_packet())


def test_native_pre_cognition_can_reverse_abstain_after_exact_evidence_reread():
    client = _ReconsideringStructuredClient()
    assessment = client.assess_pre_cognition(
        "Which approach conflicts with my Kestrel rule and what profile did I give it?",
        _supported_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.RESPOND
    assert assessment.evidence_state is EvidenceState.ACTIVATED_MEMORY_SUFFICIENT
    assert assessment.claim_scopes == [ClaimScope.USER_HISTORY]
    assert len(client.calls) == 2
    assert "Terminal-abstention reconsideration" in client.calls[1][1]


def test_native_pre_cognition_accepts_second_valid_abstain():
    client = _PersistentAbstainClient()
    assessment = client.assess_pre_cognition(
        "What fact is not present in these memories?",
        _supported_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.ABSTAIN
    assert client.calls == 2
