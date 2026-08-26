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
        ("The rule prohibits Docker Compose.", True),
        ("Native Windows conflicts; Docker Compose does not conflict.", False),
        ("Docker Compose wasn't ruled out.", False),
        ("Neither approach conflicts.", False),
    ],
)
def test_conflict_assertion_preserves_polarity(answer, expected):
    assert _affirms_docker_compose_conflicts(answer) is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("We ruled out Docker Compose.", True),
        ("The ruled-out approach was Docker Compose.", True),
        ("We did not rule out Docker Compose.", False),
        ("We ruled out native Windows, not Docker Compose.", False),
    ],
)
def test_ruled_out_assertion_preserves_polarity(answer, expected):
    assert _affirms_docker_compose_was_ruled_out(answer) is expected


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Virtualization is disabled.", True),
        ("Virtualization was disabled, not enabled.", True),
        ("Virtualization isn't disabled.", False),
        ("Virtualization is enabled.", False),
        ("The disabled feature was not virtualization.", False),
    ],
)
def test_reason_assertion_preserves_polarity(answer, expected):
    assert _affirms_virtualization_was_disabled(answer) is expected
