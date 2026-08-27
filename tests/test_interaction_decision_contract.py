import pytest
from pydantic import ValidationError

from jit_agent.interaction_policy import InteractionAction, InteractionDecision
from jit_agent.models import (
    CrossReferenceCandidateSelection,
    FocusedMemoryCandidateSelection,
    MemoryCandidateSelection,
)


def test_interaction_decision_schema_contains_only_closed_action_and_indices():
    schema = InteractionDecision.model_json_schema()

    assert set(schema["properties"]) == {"next_action", "capability_indices"}
    decision = InteractionDecision(
        next_action=InteractionAction.USE_CAPABILITIES,
        capability_indices=[3, 1],
    )
    assert decision.model_dump(mode="json") == {
        "next_action": "USE_CAPABILITIES",
        "capability_indices": [3, 1],
    }


def test_respond_is_explicit_and_cannot_select_capabilities():
    decision = InteractionDecision(
        next_action=InteractionAction.RESPOND,
        capability_indices=[],
    )
    assert decision.model_dump(mode="json") == {
        "next_action": "RESPOND",
        "capability_indices": [],
    }
    with pytest.raises(ValidationError, match="RESPOND must not select capabilities"):
        InteractionDecision(
            next_action=InteractionAction.RESPOND,
            capability_indices=[0],
        )


def test_use_capabilities_requires_nonnegative_unique_indices_without_magic_ceiling():
    with pytest.raises(ValidationError, match="requires at least one capability index"):
        InteractionDecision(next_action=InteractionAction.USE_CAPABILITIES)
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        InteractionDecision(
            next_action=InteractionAction.USE_CAPABILITIES,
            capability_indices=[1, 1],
        )
    with pytest.raises(ValidationError):
        InteractionDecision(
            next_action=InteractionAction.USE_CAPABILITIES,
            capability_indices=[-1],
        )

    # There is intentionally no arbitrary global upper bound here. The exact
    # catalog supplied to a routing call is the authoritative finite domain and
    # CapabilityRegistry.resolve_catalog_indices validates membership fail-closed.
    decision = InteractionDecision(
        next_action=InteractionAction.USE_CAPABILITIES,
        capability_indices=[0, 1, 2, 3, 4, 64],
    )
    assert decision.capability_indices[-1] == 64


@pytest.mark.parametrize(
    "field",
    [
        "capability_name",
        "capability_query",
        "capability_input",
        "execution_order",
        "explanation",
    ],
)
def test_interaction_decision_rejects_stray_natural_language_or_ordering_fields(field):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        InteractionDecision.model_validate(
            {
                "next_action": "USE_CAPABILITIES",
                "capability_indices": [0],
                field: "free-form model text",
            }
        )


def test_deeper_research_selection_has_no_arbitrary_packet_index_ceiling():
    schema = MemoryCandidateSelection.model_json_schema()
    assert set(schema["properties"]) == {"candidate_indices"}
    selection = MemoryCandidateSelection(candidate_indices=[2, 7, 20])
    assert selection.model_dump(mode="json") == {"candidate_indices": [2, 7, 20]}
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        MemoryCandidateSelection(candidate_indices=[2, 2])
    with pytest.raises(ValidationError):
        MemoryCandidateSelection(candidate_indices=[-1])
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MemoryCandidateSelection.model_validate(
            {"candidate_indices": [0], "query_text": "generated query"}
        )


def test_cross_reference_requires_multiple_candidates_without_arbitrary_maximum():
    schema = CrossReferenceCandidateSelection.model_json_schema()
    assert set(schema["properties"]) == {"candidate_indices"}
    selection = CrossReferenceCandidateSelection(candidate_indices=[1, 4, 7, 20, 21])
    assert selection.model_dump(mode="json") == {"candidate_indices": [1, 4, 7, 20, 21]}
    with pytest.raises(ValidationError):
        CrossReferenceCandidateSelection(candidate_indices=[1])
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        CrossReferenceCandidateSelection(candidate_indices=[1, 1])
    with pytest.raises(ValidationError):
        CrossReferenceCandidateSelection(candidate_indices=[-1, 0])
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CrossReferenceCandidateSelection.model_validate(
            {"candidate_indices": [0, 1], "relationship": "generated text"}
        )


def test_focused_recall_selects_one_nonnegative_candidate_without_magic_ceiling():
    schema = FocusedMemoryCandidateSelection.model_json_schema()
    assert set(schema["properties"]) == {"candidate_index"}
    selection = FocusedMemoryCandidateSelection(candidate_index=20)
    assert selection.model_dump(mode="json") == {"candidate_index": 20}
    with pytest.raises(ValidationError):
        FocusedMemoryCandidateSelection(candidate_index=-1)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        FocusedMemoryCandidateSelection.model_validate(
            {"candidate_index": 0, "explanation": "free-form"}
        )
