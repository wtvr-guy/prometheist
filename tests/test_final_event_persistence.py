import uuid

import pytest

from jit_agent import db, event_store, memory_specialist, primary_agent
from jit_agent.models import AgentAction, AgentDecision, EventType, MemoryNeedDecision, MemoryPacket


class DirectLLM:
    def classify(self, prompt: str) -> AgentDecision:
        return AgentDecision(action=AgentAction.RESPOND_DIRECTLY)

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        return "completed response"

    def plan_memory(self, task: str) -> MemoryNeedDecision:
        return MemoryNeedDecision(query_text="missing evidence")

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        return "completed specialist result"


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def test_primary_final_response_write_failure_records_error(conn, monkeypatch):
    conversation_id = uuid.uuid4()
    original_record_event = event_store.record_event

    def fail_agent_response(*args, **kwargs):
        if kwargs.get("event_type") == EventType.AGENT_RESPONSE:
            raise RuntimeError("final response write failed")
        return original_record_event(*args, **kwargs)

    monkeypatch.setattr(event_store, "record_event", fail_agent_response)

    with pytest.raises(RuntimeError, match="final response write failed"):
        primary_agent.handle_interaction(conn, DirectLLM(), "hello", conversation_id)

    events = event_store.get_events_by_conversation(conn, conversation_id)
    errors = [event for event in events if event.event_type == EventType.ERROR]
    assert errors
    assert errors[-1].payload["stage"] == "persist_response"
    assert errors[-1].payload["error_type"] == "RuntimeError"


def test_specialist_final_result_write_failure_records_error(conn, monkeypatch):
    conversation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    event_store.start_conversation(conn, conversation_id)
    boundary_event = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": "boundary"},
        payload_text="boundary",
    )

    original_record_event = event_store.record_event

    def fail_agent_result(*args, **kwargs):
        if kwargs.get("event_type") == EventType.AGENT_RESULT:
            raise RuntimeError("final specialist result write failed")
        return original_record_event(*args, **kwargs)

    monkeypatch.setattr(event_store, "record_event", fail_agent_result)

    with pytest.raises(RuntimeError, match="final specialist result write failed"):
        memory_specialist.handle_task(
            conn,
            DirectLLM(),
            task="recall something unavailable",
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            before_global_seq=boundary_event.global_seq,
        )

    events = event_store.get_events_by_conversation(conn, conversation_id)
    errors = [event for event in events if event.event_type == EventType.ERROR]
    assert errors
    assert errors[-1].payload["stage"] == "specialist_persist_result"
    assert errors[-1].payload["error_type"] == "RuntimeError"
