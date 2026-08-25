import pytest

from tests.test_acceptance_conversation_continuity import (
    _affirms_docker_compose_conflicts,
    _affirms_docker_compose_was_ruled_out,
    _affirms_virtualization_was_disabled,
)


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Docker Compose conflicts with the rule.", True),
        ("The approach that conflicts is Docker Compose.", True),
        ("The rule prohibits Docker Compose.", True),
        ("The rule rules out Docker Compose.", True),
        ("Native Windows conflicts; Docker Compose does not conflict.", False),
        ("Docker Compose is not ruled out.", False),
        ("Docker Compose wasn't ruled out.", False),
        ("Docker Compose was not really ruled out.", False),
        ("Native Windows conflicts, not Docker Compose.", False),
        ("Neither Docker Compose nor native Windows conflicts.", False),
        ("No rule prohibits Docker Compose.", False),
        ("Docker Compose is compatible with the rule.", False),
    ],
)
def test_conflict_assertion_preserves_polarity(answer, expected):
    assert _affirms_docker_compose_conflicts(answer) is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("We ruled out Docker Compose.", True),
        ("Docker Compose was ruled out.", True),
        ("We ruled Docker Compose out.", True),
        ("The ruled-out approach was Docker Compose.", True),
        ("We did not rule out Docker Compose.", False),
        ("Docker Compose was not ruled out.", False),
        ("Docker Compose wasn't ruled out.", False),
        ("Docker Compose was not actually ruled out.", False),
        ("We ruled out native Windows, not Docker Compose.", False),
        ("Neither Docker Compose nor native Windows was ruled out.", False),
    ],
)
def test_ruled_out_assertion_preserves_polarity(answer, expected):
    assert _affirms_docker_compose_was_ruled_out(answer) is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Virtualization is disabled.", True),
        ("It was disabled at the virtualization layer.", True),
        ("Virtualization was disabled, not enabled.", True),
        ("Virtualization is not disabled.", False),
        ("Virtualization wasn't disabled.", False),
        ("Virtualization was not actually disabled.", False),
        ("Virtualization is enabled.", False),
        ("Virtualization is not enabled; it is disabled.", True),
        ("The disabled feature was not virtualization.", False),
        ("No virtualization feature was disabled.", False),
    ],
)
def test_reason_assertion_preserves_polarity(answer, expected):
    assert _affirms_virtualization_was_disabled(answer) is expected
