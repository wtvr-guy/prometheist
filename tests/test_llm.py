from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent import llm
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


class _FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


class _FakeHTTPClient:
    def __init__(self, contents):
        self._contents = iter(contents)
        self.calls = []

    def post(self, path, *, json):
        self.calls.append((path, json))
        return _FakeResponse(next(self._contents))


def test_response_prompts_do_not_leak_acceptance_scenario_facts():
    response_prompts = (
        llm._RESPOND_SYSTEM_PROMPT + llm._SPECIALIST_ANSWER_PROMPT
    ).casefold()

    assert "project kestrel" not in response_prompts
    assert "virtualization is disabled" not in response_prompts
    assert "blueharbor" not in response_prompts
    assert "vx-" not in response_prompts


def test_user_facing_answers_use_a_deterministic_structured_envelope():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(['{"answer":"Final answer only."}'])
    client._client = fake_http

    assert client.respond("Question", None) == "Final answer only."

    path, payload = fake_http.calls[0]
    assert path == "/api/chat"
    assert payload["format"]["required"] == ["answer"]
    assert payload["think"] is False
    assert payload["stream"] is False
    assert payload["options"] == {"num_predict": 256, "temperature": 0}


def test_user_facing_answer_retries_invalid_structured_output():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    fake_http = _FakeHTTPClient(["not-json", '{"answer":"Recovered answer."}'])
    client._client = fake_http

    assert client.respond("Question", None) == "Recovered answer."
    assert len(fake_http.calls) == 2


def test_user_facing_answer_fails_closed_after_two_invalid_outputs():
    client = llm.OllamaClient(base_url="http://ollama.test", model="model:test")
    client._client = _FakeHTTPClient(["not-json", '{"answer":"   "}'])

    with pytest.raises(ValueError, match="agent answer failed to validate"):
        client.respond("Question", None)


def test_causal_clause_highlight_uses_asserted_user_authored_clauses_only():
    conversation_id = uuid4()

    def evidence(event_type, source, content, seq):
        return MemoryEvidence(
            source_event_id=uuid4(),
            event_type=event_type,
            source=source,
            created_at=datetime.now(timezone.utc),
            conversation_id=conversation_id,
            conversation_seq=seq,
            global_seq=seq,
            content=content,
        )

    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Why?"),
        supported=False,
        items=[
            evidence(
                EventType.AGENT_RESPONSE,
                "primary_agent",
                "Avoid option A because an invented agent rationale applies.",
                2,
            ),
            evidence(
                EventType.USER_PROMPT,
                "user",
                (
                    "It was not because virtualization is disabled; "
                    "avoid option A because the service account is unavailable. "
                    "Was it because the network is offline?"
                ),
                1,
            ),
        ],
    )

    highlight = llm._format_explicit_causal_clauses(packet)

    assert "- the service account is unavailable" in highlight
    assert "virtualization is disabled" not in highlight
    assert "network is offline" not in highlight
    assert "invented agent rationale" not in highlight


@pytest.mark.parametrize(
    "content",
    [
        "Tell me whether it was because the service account is unavailable.",
        "Maybe it failed because the service account is unavailable.",
        "Was it because the service account is unavailable?",
    ],
)
def test_causal_clause_highlight_rejects_uncertain_or_interrogative_sources(content):
    conversation_id = uuid4()
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Why?"),
        supported=False,
        items=[
            MemoryEvidence(
                source_event_id=uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                created_at=datetime.now(timezone.utc),
                conversation_id=conversation_id,
                conversation_seq=1,
                global_seq=1,
                content=content,
            )
        ],
    )

    assert llm._format_explicit_causal_clauses(packet) == ""
