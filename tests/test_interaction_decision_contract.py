import pytest
from pydantic import ValidationError

from jit_agent.interaction_policy import (
    CapabilityRequirement,
    InteractionAction,
    InteractionDecision,
)
from jit_agent.models import (
    HistoricalMemoryAnchorDecision,
    MemoryNeedDecision,
    MemoryRetrievalScope,
)


def test_interaction_decision_schema_contains_only_post_aperture_capability_enum():
    schema = InteractionDecision.model_json_schema()

    assert set(schema["properties"]) == {"required_capability"}
    assert {value.value for value in CapabilityRequirement} == {"NONE", "MEMORY_ANALYSIS"}
    decision = InteractionDecision(
        required_capability=CapabilityRequirement.MEMORY_ANALYSIS
    )
    assert decision.action is InteractionAction.REQUEST_CAPABILITY
    assert decision.capability_id == "memory_analysis"


def test_direct_interaction_decision_is_enum_only():
    decision = InteractionDecision(required_capability=CapabilityRequirement.NONE)

    assert decision.action is InteractionAction.RESPOND_DIRECTLY
    assert decision.capability_id is None
    assert decision.model_dump(mode="json") == {"required_capability": "NONE"}


@pytest.mark.parametrize("field", ["capability_query", "capability_input", "explanation"])
def test_interaction_decision_rejects_stray_natural_language_fields(field):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        InteractionDecision.model_validate(
            {
                "required_capability": "MEMORY_ANALYSIS",
                field: "free-form model text",
            }
        )


def test_memory_routing_schema_contains_only_scope_and_anchor_indices():
    schema = MemoryNeedDecision.model_json_schema()

    assert set(schema["properties"]) == {"scope", "anchor_indices"}
    decision = MemoryNeedDecision(
        scope=MemoryRetrievalScope.ACTIVE_AND_HISTORY,
        anchor_indices=[2, 7],
    )
    assert decision.model_dump(mode="json") == {
        "scope": "ACTIVE_AND_HISTORY",
        "anchor_indices": [2, 7],
    }


def test_no_working_state_schema_cannot_represent_scope():
    schema = HistoricalMemoryAnchorDecision.model_json_schema()

    assert set(schema["properties"]) == {"anchor_indices"}
    selection = HistoricalMemoryAnchorDecision(anchor_indices=[2, 7])
    assert selection.model_dump(mode="json") == {"anchor_indices": [2, 7]}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        HistoricalMemoryAnchorDecision.model_validate(
            {
                "scope": "ACTIVE_ONLY",
                "anchor_indices": [2],
            }
        )


def test_active_only_memory_routing_cannot_emit_anchor_text_or_indices():
    with pytest.raises(ValidationError, match="ACTIVE_ONLY must not select historical anchors"):
        MemoryNeedDecision(
            scope=MemoryRetrievalScope.ACTIVE_ONLY,
            anchor_indices=[1],
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MemoryNeedDecision.model_validate(
            {
                "scope": "ACTIVE_ONLY",
                "anchor_indices": [],
                "query_text": "generated query",
            }
        )


def test_historical_memory_routing_requires_bounded_unique_indices():
    with pytest.raises(ValidationError, match="requires at least one anchor index"):
        MemoryNeedDecision(scope=MemoryRetrievalScope.HISTORY_ONLY)
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        MemoryNeedDecision(
            scope=MemoryRetrievalScope.HISTORY_ONLY,
            anchor_indices=[2, 2],
        )
