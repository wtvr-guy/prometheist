from __future__ import annotations

import os
from uuid import uuid4

import pytest

from jit_agent.percept_response_worker import (
    _INTERACTIVE_PERSONALITY_PROMPT,
    _USER_PROMPT_COMPOSER,
    UserPromptLLM,
    UserPromptWorkSelection,
)
from jit_agent.percept_response_runtime import _RESPONSE_POLICY_PROMPT
from jit_agent.models import EventType, MemoryNeed, MemoryPacket
from jit_agent.response_policy import (
    HistoricalEvidenceScope,
    ResponseSurfaceMode,
    source_types_for_scope,
)
from jit_agent.self_memory import (
    IdentityCentrality,
    SelfContextAdmission,
    SelfContextItem,
    SelfContextPacket,
    SelfEvidenceMetrics,
    SelfPerspective,
    SelfRepresentationKind,
    SelfResolutionStatus,
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


def test_user_prompt_composer_accepts_and_renders_typed_self_context(monkeypatch) -> None:
    llm = UserPromptLLM()
    captured: dict[str, str] = {}

    def fake_structured(kind, system, current_user, evidence, schema, max_tokens):
        del system, schema, max_tokens
        captured["kind"] = kind
        captured["current_user"] = current_user
        captured["evidence"] = evidence
        return '{"sufficient":true,"memory_deficit":null}'

    monkeypatch.setattr(llm, "_structured_with_evidence", fake_structured)

    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="What do I usually prefer?"),
        supported=False,
        items=[],
    )
    self_context = SelfContextPacket(
        admission=SelfContextAdmission.PRIMARY_DERIVED_CONTEXT,
        items=(
            SelfContextItem(
                representation_id=uuid4(),
                kind=SelfRepresentationKind.PREFERENCE,
                perspective=SelfPerspective.INFERRED,
                statement="The person usually prefers modular systems.",
                status=SelfResolutionStatus.ESTABLISHED,
                identity_centrality=IdentityCentrality.MODERATE,
                metrics=SelfEvidenceMetrics(
                    support_root_count=3,
                    opposition_root_count=0,
                    source_type_count=1,
                    source_count=1,
                    context_count=2,
                ),
                support_event_types=(EventType.USER_PROMPT,),
            ),
        ),
    )

    decision = llm.assess_memory_sufficiency(
        "What do I usually prefer?",
        packet,
        self_context,
    )

    assert decision.sufficient is True
    assert captured["kind"] == "V2_MEMORY_SUFFICIENCY_USER_PROMPT"
    assert "What do I usually prefer?" in captured["current_user"]
    assert "[Derived self-memory]" in captured["evidence"]
    assert "The person usually prefers modular systems." in captured["evidence"]


def test_response_policy_defaults_ordinary_questions_to_natural_language() -> None:
    normalized = " ".join(_RESPONSE_POLICY_PROMPT.split()).casefold()
    assert "natural_language is the default for ordinary questions" in normalized
    assert "only when the current user explicitly requires exact raw output" in normalized
    assert "a request to answer naturally" in normalized
    assert "self_model" in normalized
    assert "what do i usually prefer?" in normalized


@pytest.mark.parametrize(
    ("scope", "expected_types"),
    [
        (HistoricalEvidenceScope.USER_AUTHORED, {EventType.USER_PROMPT}),
        (
            HistoricalEvidenceScope.SELF_MODEL,
            {
                EventType.USER_PROMPT,
                EventType.TOOL_RESULT,
                EventType.PERCEPT_OBSERVATION,
                EventType.SYSTEM_EVENT,
            },
        ),
        (
            HistoricalEvidenceScope.MODEL_OUTPUT,
            {
                EventType.INTERACTION_RESPONSE,
                EventType.AGENT_RESPONSE,
                EventType.AGENT_RESULT,
            },
        ),
        (
            HistoricalEvidenceScope.MIXED_CONVERSATION,
            {
                EventType.USER_PROMPT,
                EventType.INTERACTION_RESPONSE,
                EventType.AGENT_RESPONSE,
                EventType.AGENT_RESULT,
            },
        ),
        (
            HistoricalEvidenceScope.EXTERNAL_TOOL,
            {EventType.TOOL_RESULT, EventType.PERCEPT_OBSERVATION},
        ),
        (
            HistoricalEvidenceScope.SYSTEM_RECORD,
            {
                EventType.SYSTEM_EVENT,
                EventType.ERROR,
                EventType.INTERACTION_WORKING_STATE,
            },
        ),
        (
            HistoricalEvidenceScope.DERIVED_INTERNAL,
            {
                EventType.DERIVED_REPRESENTATION,
                EventType.AGENT_DECISION,
                EventType.RETRIEVAL_REQUEST,
                EventType.RETRIEVAL_RESULT,
                EventType.MEMORY_REQUEST,
                EventType.MEMORY_PACKET,
                EventType.AGENT_DELEGATION,
                EventType.TOOL_REQUEST,
                EventType.CAPABILITY_REQUEST,
                EventType.CAPABILITY_PACKET,
                EventType.CAPABILITY_RESULT,
            },
        ),
        (
            HistoricalEvidenceScope.GENERAL_OR_CURRENT,
            {
                EventType.USER_PROMPT,
                EventType.TOOL_RESULT,
                EventType.SYSTEM_EVENT,
            },
        ),
    ],
)
def test_response_scope_maps_to_exact_retrieval_event_roles(scope, expected_types) -> None:
    assert set(source_types_for_scope(scope)) == expected_types


@pytest.mark.parametrize(
    ("prompt", "scope"),
    [
        ("What constraint did I give you?", HistoricalEvidenceScope.USER_AUTHORED),
        ("What do I usually prefer?", HistoricalEvidenceScope.SELF_MODEL),
        ("Quote the assistant's prior response verbatim.", HistoricalEvidenceScope.MODEL_OUTPUT),
        ("Summarize our prior conversation.", HistoricalEvidenceScope.MIXED_CONVERSATION),
        ("What is the current status?", HistoricalEvidenceScope.GENERAL_OR_CURRENT),
    ],
)
def test_response_policy_worker_selects_scope_without_historical_evidence(
    monkeypatch,
    prompt,
    scope,
) -> None:
    llm = UserPromptLLM()
    calls: list[tuple[str, str]] = []

    def fake_structured(kind, system, current_user, evidence, schema, max_tokens):
        del schema, max_tokens
        calls.append((current_user, evidence))
        assert kind == "V2_RESPONSE_POLICY"
        assert prompt in current_user
        assert evidence.endswith("none")
        return (
            '{"evidence_scope":"'
            f"{scope.value}"
            '","surface_mode":"NATURAL_LANGUAGE","insufficient_literal":null}'
        )

    monkeypatch.setattr(llm, "_structured_with_evidence", fake_structured)

    policy = llm._response_policy(prompt)

    assert policy.evidence_scope is scope
    assert policy.surface_mode is ResponseSurfaceMode.NATURAL_LANGUAGE
    assert len(calls) == 1


def test_explicit_prior_assistant_reference_uses_mixed_scope_without_model_classification(
    monkeypatch,
) -> None:
    llm = UserPromptLLM()

    def fail_if_called(*args, **kwargs):
        del args, kwargs
        raise AssertionError("explicit prior-assistant references must use the deterministic path")

    monkeypatch.setattr(llm, "_structured_with_evidence", fail_if_called)

    policy = llm._response_policy("What did you tell me earlier about PostgreSQL?")

    assert policy.evidence_scope is HistoricalEvidenceScope.MIXED_CONVERSATION
    assert set(source_types_for_scope(policy.evidence_scope)) == {
        EventType.USER_PROMPT,
        EventType.INTERACTION_RESPONSE,
        EventType.AGENT_RESPONSE,
        EventType.AGENT_RESULT,
    }


def test_interactive_identity_belongs_to_prometheist_not_disposable_llm() -> None:
    normalized = " ".join(_INTERACTIVE_PERSONALITY_PROMPT.split()).casefold()
    assert "you are prometheist" in normalized
    assert "language model is a fresh, disposable semantic worker" in normalized
    assert "not prometheist's identity" in normalized


def test_user_prompt_llm_always_installs_core_interactive_personality(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PROMETHEIST_PERSONALITY_PROMPT", raising=False)

    UserPromptLLM()

    resolved = os.environ["PROMETHEIST_PERSONALITY_PROMPT"]
    assert resolved == _INTERACTIVE_PERSONALITY_PROMPT.strip()
    assert "A historical USER_PROMPT is direct evidence" in resolved


def test_user_configured_personality_extends_core_accuracy_contract(monkeypatch) -> None:
    configured = "Use concise dry humor when appropriate, without sacrificing precision."
    monkeypatch.setenv("PROMETHEIST_PERSONALITY_PROMPT", configured)

    UserPromptLLM()

    resolved = os.environ["PROMETHEIST_PERSONALITY_PROMPT"]
    assert resolved.startswith(_INTERACTIVE_PERSONALITY_PROMPT.strip())
    assert "[User-configured personality]" in resolved
    assert configured in resolved
    assert "A historical USER_PROMPT is direct evidence" in resolved
