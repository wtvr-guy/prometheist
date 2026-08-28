import json
import uuid

import pytest
from pydantic import ValidationError

from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.pre_cognitive_ollama_client import (
    PreCognitiveDurableResponseOllamaClient,
    canonicalize_specialist_payload,
)
from jit_agent.pre_cognitive_specialists import (
    CapabilitySelectionDecision,
    EvidenceSufficiencyDecision,
)
from jit_agent.pre_cognitive_workers import (
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    IntentMode,
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
                    "on Windows because virtualization is disabled. I track that constraint "
                    "under profile VX-ABC12345."
                ),
                score=1.0,
                retrieval_reasons=["ACTIVE_WORKING_STATE"],
                provenance_event_ids=[],
            )
        ],
    )


class _ScriptedSpecialistClient(PreCognitiveDurableResponseOllamaClient):
    def __init__(
        self,
        *,
        sufficiency: str,
        capability_indices: list[int] | None = None,
    ):
        self.sufficiency = sufficiency
        self.capability_indices = capability_indices or []
        self.roles: list[str] = []

    def _structured(self, role, system, user, schema, max_tokens):
        del system, user, schema, max_tokens
        self.roles.append(role)
        if role.endswith("_EVIDENCE_SUFFICIENCY"):
            return json.dumps({"sufficiency": self.sufficiency})
        if role.endswith("_CAPABILITY_SELECTION"):
            return json.dumps(
                {"capability_indices": self.capability_indices + self.capability_indices}
            )
        raise AssertionError(f"unexpected specialist role: {role}")


def test_atomic_specialist_schemas_do_not_expose_aggregate_control_authority():
    assert set(EvidenceSufficiencyDecision.model_fields) == {"sufficiency"}
    assert set(CapabilitySelectionDecision.model_fields) == {"capability_indices"}


def test_capability_selection_canonicalization_preserves_order_and_closed_validation():
    payload = canonicalize_specialist_payload(
        {"capability_indices": [1, 0, 1]},
        "CapabilitySelectionDecision",
    )
    assert payload == {"capability_indices": [1, 0]}

    invalid = canonicalize_specialist_payload(
        {"capability_indices": [-1, -1]},
        "CapabilitySelectionDecision",
    )
    with pytest.raises(ValidationError):
        CapabilitySelectionDecision.model_validate(invalid)


def test_sufficient_evidence_fast_path_runs_only_sufficiency_station():
    client = _ScriptedSpecialistClient(sufficiency="SUFFICIENT")
    assessment = client.assess_pre_cognition(
        "Which approach conflicts with my Kestrel rule and what profile did I give it?",
        _supported_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.RESPOND
    assert assessment.evidence_state is EvidenceState.ACTIVATED_MEMORY_SUFFICIENT
    assert assessment.intent_mode is IntentMode.OTHER
    assert assessment.claim_scopes == []
    assert assessment.requirement_flags == []
    assert assessment.capability_indices == []
    assert len(client.roles) == 1
    assert client.roles[0].endswith("_EVIDENCE_SUFFICIENCY")


def test_insufficient_empty_evidence_runs_capability_selector_after_sufficiency():
    client = _ScriptedSpecialistClient(
        sufficiency="INSUFFICIENT",
        capability_indices=[0],
    )
    assessment = client.assess_pre_cognition(
        "Find more internal evidence about Project Falcon.",
        _empty_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES
    assert assessment.evidence_state is EvidenceState.MORE_INTERNAL_EVIDENCE_REQUIRED
    assert assessment.capability_indices == [0]
    assert len(client.roles) == 2
    assert client.roles[0].endswith("_EVIDENCE_SUFFICIENCY")
    assert client.roles[1].endswith("_CAPABILITY_SELECTION")


def test_negative_over_existing_evidence_reaches_selector_without_second_vote():
    client = _ScriptedSpecialistClient(
        sufficiency="INSUFFICIENT",
        capability_indices=[0],
    )
    assessment = client.assess_pre_cognition(
        (
            "What profile did I attach to that Kestrel deployment rule, and what "
            "technical limitation was behind it?"
        ),
        _supported_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES
    assert assessment.evidence_state is EvidenceState.MORE_INTERNAL_EVIDENCE_REQUIRED
    assert assessment.capability_indices == [0]
    assert len(client.roles) == 2
    assert client.roles[0].endswith("_EVIDENCE_SUFFICIENCY")
    assert client.roles[1].endswith("_CAPABILITY_SELECTION")
    assert not any("CONFIRMATION" in role for role in client.roles)


def test_insufficient_existing_evidence_without_helpful_capability_is_acquisition_abstain():
    client = _ScriptedSpecialistClient(
        sufficiency="INSUFFICIENT",
        capability_indices=[],
    )
    assessment = client.assess_pre_cognition(
        "Tell me an unsupported historical fact about Project Kestrel.",
        _supported_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.ABSTAIN
    assert assessment.evidence_state is EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK
    assert assessment.capability_indices == []
    assert len(client.roles) == 2
    assert client.roles[0].endswith("_EVIDENCE_SUFFICIENCY")
    assert client.roles[1].endswith("_CAPABILITY_SELECTION")
    assert not any("CONFIRMATION" in role for role in client.roles)


def test_insufficient_empty_evidence_without_helpful_capability_deterministically_abstains():
    client = _ScriptedSpecialistClient(
        sufficiency="INSUFFICIENT",
        capability_indices=[],
    )
    assessment = client.assess_pre_cognition(
        "Tell me an unsupported historical fact.",
        _empty_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.ABSTAIN
    assert assessment.evidence_state is EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK
    assert assessment.capability_indices == []
    assert len(client.roles) == 2


def test_sufficient_current_input_uses_current_input_evidence_state():
    client = _ScriptedSpecialistClient(sufficiency="SUFFICIENT")
    assessment = client.assess_pre_cognition(
        "Return the literal word hello.",
        _empty_packet(),
        DEFAULT_REGISTRY.capability_catalog(),
        phase=CognitivePhase.PRE_CAPABILITY,
    )

    assert assessment.disposition is CognitiveDisposition.RESPOND
    assert assessment.evidence_state is EvidenceState.CURRENT_INPUT_SUFFICIENT
    assert len(client.roles) == 1