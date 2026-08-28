from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.final_response_directive import (
    FinalAbstainReason,
    FinalReadinessDecision,
    FinalResponseAction,
    FinalResponseDirective,
)
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.personality import configured_personality_prompt
from jit_agent.pre_cognitive_response_runtime import (
    _record_error_best_effort,
    _release_claim_best_effort,
)
from jit_agent.response_policy import (
    HistoricalEvidenceScope,
    ResponsePolicy,
    ResponseSurfaceMode,
)


NOW = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class _FakeHTTPClient:
    def __init__(self, bodies):
        self._bodies = iter(bodies)
        self.calls = []

    def post(self, path, *, json):
        self.calls.append((path, json))
        return _FakeResponse(next(self._bodies))


def _packet() -> MemoryPacket:
    conversation_id = uuid4()
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="stored preference", limit=1),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid4(),
                event_type=EventType.USER_PROMPT,
                source="test",
                created_at=NOW,
                conversation_id=conversation_id,
                conversation_seq=1,
                global_seq=1,
                content="I prefer concise answers.",
            )
        ],
    )


def _kestrel_packet() -> MemoryPacket:
    conversation_id = uuid4()
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Project Kestrel", limit=1),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                created_at=NOW,
                conversation_id=conversation_id,
                conversation_seq=1,
                global_seq=1,
                content=(
                    "For Project Kestrel, never use Docker; deploy PostgreSQL directly on "
                    "Windows because virtualization is disabled."
                ),
            )
        ],
    )


def _respond_directive(packet: MemoryPacket) -> FinalResponseDirective:
    personality = configured_personality_prompt()
    return FinalResponseDirective(
        action=FinalResponseAction.RESPOND,
        intent_mode="RECALL",
        evidence_state="ACTIVATED_MEMORY_SUFFICIENT",
        claim_scopes=["USER_HISTORY"],
        requirement_flags=[],
        response_policy=ResponsePolicy(
            evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
            surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
        ),
        final_memory_request_id=packet.memory_request_id,
        capability_ids=[],
        personality_prompt_version=personality.version,
        personality_prompt_sha256=personality.sha256,
    )


def test_final_readiness_contract_has_no_capability_or_prose_surface():
    with pytest.raises(ValidationError):
        FinalReadinessDecision.model_validate(
            {
                "action": "RESPOND",
                "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
                "capability_indices": [0],
            }
        )


def test_final_directive_is_terminal_and_rejects_response_fallback():
    packet = _packet()
    directive = _respond_directive(packet)
    with pytest.raises(ValidationError):
        directive.model_copy(
            update={"fallback_literal": "UNKNOWN"}
        ).model_dump()
        # model_copy intentionally does not revalidate; force validation below.
        FinalResponseDirective.model_validate(
            directive.model_copy(update={"fallback_literal": "UNKNOWN"}).model_dump()
        )


def test_abstain_requires_reason_and_may_carry_current_fallback():
    packet = _packet()
    personality = configured_personality_prompt()
    directive = FinalResponseDirective(
        action=FinalResponseAction.ABSTAIN,
        abstain_reason=FinalAbstainReason.SOURCE_POLICY_UNSUPPORTED,
        intent_mode="RECALL",
        evidence_state="INSUFFICIENT_AFTER_AVAILABLE_WORK",
        claim_scopes=["USER_HISTORY"],
        requirement_flags=["ABSTAIN_IF_UNSUPPORTED"],
        response_policy=ResponsePolicy(
            evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
            surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
        ),
        fallback_literal="UNKNOWN",
        final_memory_request_id=packet.memory_request_id,
        personality_prompt_version=personality.version,
        personality_prompt_sha256=personality.sha256,
    )
    assert directive.action is FinalResponseAction.ABSTAIN
    assert directive.fallback_literal == "UNKNOWN"


def test_personality_prompt_is_nonempty_and_content_addressed(monkeypatch):
    monkeypatch.setenv("PROMETHEIST_PERSONALITY_PROMPT", "A stable test personality.")
    monkeypatch.setenv("PROMETHEIST_PERSONALITY_PROMPT_VERSION", "test-personality-v1")
    first = configured_personality_prompt()
    second = configured_personality_prompt()
    assert first.text == "A stable test personality."
    assert first.version == "test-personality-v1"
    assert first.sha256 == second.sha256
    assert len(first.sha256) == 64


def test_final_responder_rejects_abstain_before_model_inference():
    packet = _packet()
    personality = configured_personality_prompt()
    directive = FinalResponseDirective(
        action=FinalResponseAction.ABSTAIN,
        abstain_reason=FinalAbstainReason.PRE_COGNITIVE_INSUFFICIENT,
        intent_mode="RECALL",
        evidence_state="INSUFFICIENT_AFTER_AVAILABLE_WORK",
        claim_scopes=["USER_HISTORY"],
        requirement_flags=["ABSTAIN_IF_UNSUPPORTED"],
        response_policy=ResponsePolicy(
            evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
            surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
        ),
        final_memory_request_id=packet.memory_request_id,
        personality_prompt_version=personality.version,
        personality_prompt_sha256=personality.sha256,
    )
    client = DurableResponseBudgetedOllamaClient.__new__(DurableResponseBudgetedOllamaClient)
    with pytest.raises(RuntimeError, match="never be invoked for an ABSTAIN"):
        client.respond_with_final_directive("What did I prefer?", packet, (), directive)


def test_final_responder_rejects_personality_drift_before_model_inference():
    packet = _packet()
    directive = _respond_directive(packet).model_copy(
        update={"personality_prompt_sha256": "0" * 64}
    )
    client = DurableResponseBudgetedOllamaClient.__new__(DurableResponseBudgetedOllamaClient)
    with pytest.raises(RuntimeError, match="personality prompt changed"):
        client.respond_with_final_directive("What did I prefer?", packet, (), directive)


def test_durable_response_policy_captures_current_enumerated_outputs():
    prompt = (
        "Return exactly one of these labels and nothing else: "
        "Docker Compose | PostgreSQL directly on Windows."
    )
    client = DurableResponseBudgetedOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
    )
    client._client = _FakeHTTPClient(
        [
            {
                "message": {
                    "content": (
                        '{"evidence_scope":"GENERAL_OR_CURRENT",'
                        '"surface_mode":"EXACT_SOURCE_SUBSTRING",'
                        '"insufficient_literal":null,'
                        '"allowed_output_literals":["Docker Compose",'
                        '"PostgreSQL directly on Windows"]}'
                    )
                }
            }
        ]
    )

    policy = client.classify_response_policy(prompt)

    assert policy.allowed_output_literals == [
        "Docker Compose",
        "PostgreSQL directly on Windows",
    ]
    system = client._client.calls[0][1]["messages"][0]["content"]
    assert "allowed_output_literals" in system
    assert "Never derive this list from historical evidence" in system


def test_final_exact_selector_rejects_surrounding_sentence_and_retries_allowed_label():
    packet = _kestrel_packet()
    prompt = (
        "I'm choosing between Docker Compose and PostgreSQL directly on Windows. "
        "Return exactly one of these labels and nothing else: "
        "Docker Compose | PostgreSQL directly on Windows."
    )
    personality = configured_personality_prompt()
    directive = FinalResponseDirective(
        action=FinalResponseAction.RESPOND,
        intent_mode="RECALL",
        evidence_state="ACTIVATED_MEMORY_SUFFICIENT",
        claim_scopes=["USER_HISTORY"],
        requirement_flags=[],
        response_policy=ResponsePolicy(
            evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
            surface_mode=ResponseSurfaceMode.EXACT_SOURCE_SUBSTRING,
            allowed_output_literals=[
                "Docker Compose",
                "PostgreSQL directly on Windows",
            ],
        ),
        final_memory_request_id=packet.memory_request_id,
        capability_ids=[],
        personality_prompt_version=personality.version,
        personality_prompt_sha256=personality.sha256,
    )
    client = DurableResponseBudgetedOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
    )
    client._client = _FakeHTTPClient(
        [
            {
                "message": {
                    "content": (
                        '{"source_index":0,"verbatim_value":'
                        '"For Project Kestrel, never use Docker; deploy PostgreSQL directly '
                        'on Windows because virtualization is disabled."}'
                    )
                }
            },
            {
                "message": {
                    "content": (
                        '{"source_index":0,"verbatim_value":'
                        '"PostgreSQL directly on Windows"}'
                    )
                }
            },
        ]
    )

    answer = client.respond_with_final_directive(prompt, packet, (), directive)

    assert answer == "PostgreSQL directly on Windows"
    assert len(client._client.calls) == 2
    system = client._client.calls[0][1]["messages"][0]["content"]
    assert "APPLICATION-VALIDATED CURRENT OUTPUT LITERALS" in system
    assert "PostgreSQL directly on Windows" in system


def test_malformed_legacy_control_brief_is_rejected_before_system_injection():
    packet = _packet()
    client = DurableResponseBudgetedOllamaClient.__new__(DurableResponseBudgetedOllamaClient)
    malformed = (
        {
            "capability_id": "pre_cognitive_brief",
            "executor": "application_control",
            "result_data": {
                "scheme_version": "pre-cognitive-transient-workers-v1",
                "intent_mode": "RECALL",
                "evidence_state": "ACTIVATED_MEMORY_SUFFICIENT",
                "claim_scopes": ["USER_HISTORY"],
                "requirement_flags": [],
                "acquisition_disposition": "RESPOND",
                "follow_up_executed": False,
                "injected_extra_key": "must not reach system prompt",
            },
        },
    )
    with pytest.raises(ValidationError):
        client.respond("What did I prefer?", packet, malformed)


def test_error_recording_failure_is_best_effort(monkeypatch):
    class Interaction:
        conversation_id = uuid4()
        correlation_id = uuid4()

    def fail_record(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("diagnostic write failed")

    monkeypatch.setattr(
        "jit_agent.pre_cognitive_response_runtime.event_store.record_event",
        fail_record,
    )
    _record_error_best_effort(
        object(),
        interaction=Interaction(),
        claim_id=uuid4(),
        stage=__import__(
            "jit_agent.interaction_policy", fromlist=["InteractionStage"]
        ).InteractionStage.RESPOND,
        exc=RuntimeError("original"),
    )


def test_claim_release_failure_preserves_original_error_path(monkeypatch):
    def fail_release(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("release failed")

    monkeypatch.setattr(
        "jit_agent.pre_cognitive_response_runtime.release_worker_claim",
        fail_release,
    )
    _release_claim_best_effort(
        object(),
        claim_id=uuid4(),
        worker_id="worker-1",
        scheduler_key="test",
    )
