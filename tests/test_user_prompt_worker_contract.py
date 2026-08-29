from __future__ import annotations

from jit_agent.percept_response_worker import (
    _INTERACTIVE_PERSONALITY_PROMPT,
    _USER_PROMPT_COMPOSER,
    UserPromptWorkSelection,
)


def test_user_prompt_work_schema_cannot_decide_response_requirement() -> None:
    schema = UserPromptWorkSelection.model_json_schema()
    assert "response_required" not in schema.get("properties", {})
    assert set(schema.get("properties", {})) == {"capability_indices"}


def test_composer_treats_current_prompt_as_direct_evidence() -> None:
    normalized = " ".join(_USER_PROMPT_COMPOSER.split()).casefold()
    assert "current user prompt is itself direct current evidence" in normalized
    assert "do not require" in normalized
    assert "historical memory" in normalized


def test_interactive_identity_belongs_to_prometheist_not_disposable_llm() -> None:
    normalized = " ".join(_INTERACTIVE_PERSONALITY_PROMPT.split()).casefold()
    assert "you are prometheist" in normalized
    assert "language model is a fresh, disposable semantic worker" in normalized
    assert "not prometheist's identity" in normalized
