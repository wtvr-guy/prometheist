import uuid

import pytest
from pydantic import ValidationError

from jit_agent.final_response_directive import (
    FINAL_READINESS_VERSION,
    FinalReadinessDecision,
    FinalResponseAction,
)
from jit_agent.models import MemoryNeed, MemoryPacket
from jit_agent.pre_cognitive_response_runtime import _assess_final_readiness


class _StructuredReadinessClient:
    def __init__(self):
        self.schema = None

    def _structured_with_evidence(
        self,
        role,
        system,
        prompt,
        evidence,
        schema,
        max_tokens,
    ):
        del system, prompt, evidence, max_tokens
        assert role == "FINAL_READINESS"
        self.schema = schema
        return (
            '{"action":"RESPOND",'
            '"evidence_state":"ACTIVATED_MEMORY_SUFFICIENT"}'
        )


def _packet() -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="terminal readiness", limit=1),
        supported=False,
        items=[],
    )


def test_model_facing_final_readiness_schema_excludes_application_version():
    schema = FinalReadinessDecision.model_json_schema()

    assert set(schema["properties"]) == {"action", "evidence_state"}
    assert schema.get("additionalProperties") is False


def test_runtime_passes_only_semantic_fields_to_final_readiness_model():
    client = _StructuredReadinessClient()

    decision = _assess_final_readiness(client, "Can I answer?", _packet(), ())

    assert set(client.schema["properties"]) == {"action", "evidence_state"}
    assert decision.action is FinalResponseAction.RESPOND
    assert decision.version == FINAL_READINESS_VERSION


def test_application_supplies_final_readiness_version_when_model_omits_it():
    decision = FinalReadinessDecision.model_validate(
        {
            "action": "RESPOND",
            "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
        }
    )

    assert decision.action is FinalResponseAction.RESPOND
    assert decision.version == FINAL_READINESS_VERSION


def test_persisted_final_readiness_still_rejects_wrong_application_version():
    with pytest.raises(ValidationError, match="unsupported final readiness version"):
        FinalReadinessDecision.model_validate(
            {
                "version": "1.0.0",
                "action": "RESPOND",
                "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
            }
        )
