import pytest
from pydantic import ValidationError

from jit_agent.final_response_directive import (
    FINAL_READINESS_VERSION,
    FinalReadinessDecision,
    FinalResponseAction,
)


def test_model_facing_final_readiness_schema_excludes_application_version():
    schema = FinalReadinessDecision.model_json_schema()

    assert set(schema["properties"]) == {"action", "evidence_state"}
    assert schema.get("additionalProperties") is False


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
