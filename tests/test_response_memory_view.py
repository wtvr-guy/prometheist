from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.percept_response_runtime import ResponseMemoryPackage
from jit_agent.percept_response_worker import UserPromptLLM


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": self._content}}


class _FakeHTTPClient:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, *, json: dict) -> _FakeResponse:
        self.calls.append((path, json))
        return _FakeResponse(self._content)


def _evidence(
    *,
    event_type: EventType,
    content: str,
    conversation_id,
    conversation_seq: int,
    global_seq: int,
) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=event_type,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=conversation_id,
        conversation_seq=conversation_seq,
        global_seq=global_seq,
        content=content,
    )


def test_final_responder_receives_compact_oldest_to_newest_evidence_timeline():
    historical_conversation = uuid4()
    active_conversation = uuid4()
    historical = _evidence(
        event_type=EventType.USER_PROMPT,
        content="Historical rule under profile VX-ABC123.",
        conversation_id=historical_conversation,
        conversation_seq=1,
        global_seq=1,
    )
    turn1 = _evidence(
        event_type=EventType.USER_PROMPT,
        content="Call the active plan BlueHarbor-ABC123.",
        conversation_id=active_conversation,
        conversation_seq=1,
        global_seq=20,
    )
    turn2_response = _evidence(
        event_type=EventType.INTERACTION_RESPONSE,
        content="Docker Compose | VX-ABC123",
        conversation_id=active_conversation,
        conversation_seq=13,
        global_seq=32,
    )
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="What nickname and ruled-out approach?"),
        supported=True,
        items=[turn2_response, historical, turn1],
    )
    package = ResponseMemoryPackage(
        memory_packet=packet,
        sufficient=True,
        composer_rounds=1,
        adaptive_recall_rounds=0,
    )
    client = UserPromptLLM(base_url="http://ollama.test", model="model:test")
    fake = _FakeHTTPClient('{"answer":"ok"}')
    client._client = fake

    assert client.generate_final_response("Answer from the timeline.", package, ()) == "ok"
    path, payload = fake.calls[0]
    assert path == "/api/chat"
    model_input = payload["messages"][1]["content"]
    assert "[Evidence timeline: oldest to newest]" in model_input
    assert model_input.index("Historical rule") < model_input.index("Call the active plan")
    assert model_input.index("Call the active plan") < model_input.index("Docker Compose")
    assert "conversation_scope: historical_context" in model_input
    assert "conversation_scope: recent_conversation" in model_input
    assert str(packet.memory_request_id) not in model_input
    assert str(historical.source_event_id) not in model_input
    assert str(turn1.source_event_id) not in model_input
    assert str(turn2_response.source_event_id) not in model_input
    assert "global_seq:" not in model_input
    assert "conversation_seq:" not in model_input
    assert "created_at:" not in model_input
    assert "retrieval_reasons:" not in model_input
