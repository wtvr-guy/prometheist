import pytest

from jit_agent.llm import _strip_thinking


def test_strip_thinking_preserves_plain_answer():
    assert _strip_thinking("final answer") == "final answer"


def test_strip_thinking_removes_complete_think_block():
    assert _strip_thinking("<think>hidden reasoning</think>final answer") == "final answer"


def test_strip_thinking_uses_content_after_unmatched_closing_tag():
    assert _strip_thinking("hidden reasoning</think>final answer") == "final answer"


def test_strip_thinking_rejects_truncated_response_with_no_post_tag_answer():
    with pytest.raises(ValueError, match="no answer content"):
        _strip_thinking("hidden reasoning</think>")


def test_strip_thinking_rejects_think_only_response():
    with pytest.raises(ValueError, match="no answer content"):
        _strip_thinking("<think>hidden reasoning</think>")


def test_strip_thinking_rejects_empty_response():
    with pytest.raises(ValueError, match="no answer content"):
        _strip_thinking("   ")
