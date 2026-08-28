from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jit_agent.budgeted_evidence_llm import BudgetedEvidenceBoundOllamaClient
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


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


def _assistant_only_packet() -> MemoryPacket:
    evidence = MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.INTERACTION_RESPONSE,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=1,
        global_seq=1,
        content="The user's favorite color is Cerulean-POISON.",
    )
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Favorite color?"),
        supported=True,
        items=[evidence],
    )


def _composable_user_packet() -> MemoryPacket:
    first = MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=1,
        global_seq=1,
        content=(
            "For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows "
            "because virtualization is disabled. I track that constraint under profile "
            "VX-1234ABCD."
        ),
    )
    second = MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=2,
        global_seq=2,
        content=(
            "I'm choosing between Docker Compose and PostgreSQL directly on Windows."
        ),
    )
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Kestrel approach and profile"),
        supported=True,
        items=[first, second],
    )


def test_missing_admitted_history_uses_focused_verbatim_current_fallback():
    client = BudgetedEvidenceBoundOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
    )
    fake_http = _FakeHTTPClient(
        [
            {
                "message": {
                    "content": (
                        '{"evidence_scope":"USER_AUTHORED",'
                        '"surface_mode":"NATURAL_LANGUAGE",'
                        '"insufficient_literal":"USER_PROMPT"}'
                    )
                }
            },
            {"message": {"content": '{"verbatim_value":"INSUFFICIENT"}'}},
        ]
    )
    client._client = fake_http

    prompt = "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT."
    answer = client.respond(prompt, _assistant_only_packet())

    assert answer == "INSUFFICIENT"
    assert len(fake_http.calls) == 2
    for _path, payload in fake_http.calls:
        rendered = str(payload)
        assert "Cerulean-POISON" not in rendered
    fallback_messages = fake_http.calls[1][1]["messages"]
    assert fallback_messages[-1]["content"].startswith(prompt)
    assert "current-fallback selector" in fallback_messages[0]["content"]
    assert "not SOURCE_ALPHA" in fallback_messages[0]["content"]


def test_missing_admitted_history_keeps_generic_abstention_without_explicit_fallback():
    client = BudgetedEvidenceBoundOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
    )
    fake_http = _FakeHTTPClient(
        [
            {
                "message": {
                    "content": (
                        '{"evidence_scope":"USER_AUTHORED",'
                        '"surface_mode":"NATURAL_LANGUAGE",'
                        '"insufficient_literal":"USER_PROMPT"}'
                    )
                }
            },
            {"message": {"content": '{"verbatim_value":null}'}},
        ]
    )
    client._client = fake_http

    answer = client.respond(
        "What is my favorite color? Use historical USER_PROMPT evidence only.",
        _assistant_only_packet(),
    )

    assert answer == "Persisted evidence is insufficient."


def test_exact_multi_field_response_is_composed_only_from_validated_sources_and_formatting():
    client = BudgetedEvidenceBoundOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
    )
    fake_http = _FakeHTTPClient(
        [
            {
                "message": {
                    "content": (
                        '{"evidence_scope":"USER_AUTHORED",'
                        '"surface_mode":"EXACT_SOURCE_COMPOSITION",'
                        '"insufficient_literal":null}'
                    )
                }
            },
            {
                "message": {
                    "content": (
                        '{"selections":['
                        '{"source_index":1,"verbatim_value":"Docker Compose"},'
                        '{"source_index":0,"verbatim_value":"[[VERBATIM_0]]"}'
                        '],"separator":" | "}'
                    )
                }
            },
        ]
    )
    client._client = fake_http

    prompt = (
        "Which approach conflicts with my established Kestrel rule, and what constraint "
        "profile did I give that rule? Return exactly '<approach> | <profile>' and nothing else."
    )
    answer = client.respond(prompt, _composable_user_packet())

    assert answer == "Docker Compose | VX-1234ABCD"
    assert len(fake_http.calls) == 2
    policy_messages = fake_http.calls[0][1]["messages"]
    assert "EXACT_SOURCE_COMPOSITION" in policy_messages[0]["content"]
    composition_messages = fake_http.calls[1][1]["messages"]
    assert "exact-source composition selector" in composition_messages[0]["content"]
    assert "Docker Compose" in composition_messages[1]["content"]
    assert "VX-1234ABCD" not in composition_messages[1]["content"]
