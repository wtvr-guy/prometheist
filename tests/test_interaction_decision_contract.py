import pytest
from pydantic import ValidationError

from jit_agent.interaction_policy import InteractionAction, InteractionDecision


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "RESPOND_DIRECTLY", "capability_query": ""},
        {"action": "RESPOND_DIRECTLY", "capability_input": ""},
        {
            "action": "RESPOND_DIRECTLY",
            "capability_query": "   ",
            "capability_input": "\t\n",
        },
    ],
)
def test_direct_response_normalizes_blank_optional_capability_fields(payload):
    decision = InteractionDecision.model_validate(payload)

    assert decision.action is InteractionAction.RESPOND_DIRECTLY
    assert decision.capability_query is None
    assert decision.capability_input is None


def test_optional_capability_fields_are_trimmed_when_present():
    decision = InteractionDecision.model_validate(
        {
            "action": "REQUEST_CAPABILITY",
            "capability_query": "  internal_memory  ",
            "capability_input": "  remembered fact  ",
        }
    )

    assert decision.capability_query == "internal_memory"
    assert decision.capability_input == "remembered fact"


@pytest.mark.parametrize("query", [None, "", " ", "\t\n"])
def test_capability_request_still_requires_nonblank_query(query):
    with pytest.raises(ValidationError, match="REQUEST_CAPABILITY requires capability_query"):
        InteractionDecision.model_validate(
            {
                "action": "REQUEST_CAPABILITY",
                "capability_query": query,
            }
        )
