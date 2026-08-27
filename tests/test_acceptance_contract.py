import pytest

from tests.test_acceptance_conversation_continuity import _contains_answer_slots


@pytest.mark.parametrize(
    "answer,required,expected",
    [
        (
            "The approach is Docker Compose; it was ruled out because virtualization is disabled.",
            ("Docker Compose", "virtualization", "disabled"),
            True,
        ),
        (
            "Because virtualization is disabled, Docker Compose cannot be used.",
            ("Docker Compose", "virtualization", "disabled"),
            True,
        ),
        (
            "Docker Compose is the approach.",
            ("Docker Compose", "virtualization", "disabled"),
            False,
        ),
        (
            "Virtualization is disabled.",
            ("Docker Compose", "virtualization", "disabled"),
            False,
        ),
    ],
)
def test_continuity_oracle_checks_required_slots_without_grammar_rules(
    answer,
    required,
    expected,
):
    assert _contains_answer_slots(answer, *required) is expected


def test_continuity_oracle_is_case_insensitive_for_semantic_slots():
    assert _contains_answer_slots(
        "DOCKER COMPOSE is unavailable because VIRTUALIZATION is DISABLED.",
        "Docker Compose",
        "virtualization",
        "disabled",
    )
