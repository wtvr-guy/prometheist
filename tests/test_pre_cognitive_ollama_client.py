import json
import uuid

import pytest
from pydantic import ValidationError

from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.models import MemoryNeed, MemoryPacket
from jit_agent.pre_cognitive_ollama_client import (
    PreCognitiveDurableResponseOllamaClient,
    canonicalize_pre_cognitive_payload,
)
from jit_agent.pre_cognitive_workers import (
    CognitivePhase,
    PreCognitiveAssessment,
)


def _empty_packet() -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="Project Falcon", limit=5),
        supported=False,
        items=[],
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
