import re
import uuid

import pytest

from jit_agent import db, event_store, primary_agent
from jit_agent.models import (
    AgentAction,
    AgentDecision,
    EventType,
    MemoryNeedDecision,
    MemoryPacket,
)


class FakeLLM:
    """Deterministic stateless stand-in for the Primary and specialist roles."""

    def classify(self, prompt: str) -> AgentDecision:
        lowered = prompt.lower()
        if "memory specialist" in lowered:
            return AgentDecision(
                action=AgentAction.DELEGATE_MEMORY_SPECIALIST,
                delegation_task=prompt,
            )
        if "what" in lowered and ("remember" in lowered or "number" in lowered):
            return AgentDecision(action=AgentAction.RETRIEVE_CONTEXT, query_text="remember")
        return AgentDecision(action=AgentAction.RESPOND_DIRECTLY)

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        if memory_packet and memory_packet.items:
            match = re.search(r"[0-9a-fA-F]{6,}", memory_packet.items[0].content)
            if match:
                return f"You asked me to remember {match.group(0)}."
            return memory_packet.items[0].content
        if "hello" in prompt.lower():
            return "Hello! How can I help?"
        return "Got it."

    def plan_memory(self, task: str) -> MemoryNeedDecision:
        return MemoryNeedDecision(query_text="Project Oriole codename", entities=["Project Oriole"])

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        return packet.items[0].content


class LossyRetrievalCueLLM(FakeLLM):
    """Classifier that intentionally destroys the useful lexical recall cue."""

    def classify(self, prompt: str) -> AgentDecision:
        return AgentDecision(
            action=AgentAction.RETRIEVE_CONTEXT,
            query_text="previous persisted information",
        )


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def test_acceptance_scenario_three_interactions(conn):
    conversation_id = uuid.uuid4()

    reply1 = primary_agent.handle_interaction(conn, FakeLLM(), "hello", conversation_id)
    assert reply1

    token = uuid.uuid4().hex[:10]
    reply2 = primary_agent.handle_interaction(
        conn, FakeLLM(), f"I want you to remember {token}.", conversation_id
    )
    assert reply2

    reply3 = primary_agent.handle_interaction(
        conn, FakeLLM(), "what was that number I just asked you to remember?", conversation_id
    )
    assert token in reply3


def test_memory_spans_conversations_by_default(conn):
    conv_a = uuid.uuid4()
    conv_b = uuid.uuid4()

    token = uuid.uuid4().hex[:10]
    primary_agent.handle_interaction(conn, FakeLLM(), f"remember {token}", conv_a)

    reply = primary_agent.handle_interaction(
        conn, FakeLLM(), "what number did I ask you to remember?", conv_b
    )
    assert token in reply


def test_primary_memory_request_preserves_exact_user_cue(conn):
    """A lossy classifier paraphrase must not replace the canonical recall cue."""
    fact_conversation = uuid.uuid4()
    recall_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()
    question = "What codename did I give Project Oriole?"

    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        f"The codename for Project Oriole is {token}.",
        fact_conversation,
    )

    reply = primary_agent.handle_interaction(
        conn,
        LossyRetrievalCueLLM(),
        question,
        recall_conversation,
    )
    assert token in reply

    events = event_store.get_events_by_conversation(conn, recall_conversation)
    decision_event = next(event for event in events if event.event_type == EventType.AGENT_DECISION)
    request_event = next(event for event in events if event.event_type == EventType.MEMORY_REQUEST)

    assert decision_event.payload["query_text"] == "previous persisted information"
    assert request_event.payload["need"]["query_text"] == question


class RaisingLLM(FakeLLM):
    def classify(self, prompt: str) -> AgentDecision:
        raise RuntimeError("boom")


def test_classify_failure_is_persisted_as_error_event(conn):
    conversation_id = uuid.uuid4()

    with pytest.raises(RuntimeError):
        primary_agent.handle_interaction(conn, RaisingLLM(), "hello", conversation_id)

    events = event_store.get_events_by_conversation(conn, conversation_id)
    error_events = [e for e in events if e.event_type == EventType.ERROR]
    assert len(error_events) == 1
    assert error_events[0].payload["stage"] == "classify"
    assert error_events[0].payload["error_type"] == "RuntimeError"


def test_handle_interaction_needs_no_shared_python_state(conn):
    conversation_id = uuid.uuid4()

    reply1 = primary_agent.handle_interaction(conn, FakeLLM(), "hello", conversation_id)
    reply2 = primary_agent.handle_interaction(conn, FakeLLM(), "hello again", conversation_id)

    assert reply1 and reply2


def test_specialist_independently_recalls_prior_process_style_history(conn):
    """v0.6 vertical acceptance: fresh Primary -> delegation -> specialist -> JIT memory."""
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()

    # Interaction A. Nothing from this FakeLLM object is reused later.
    primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        f"The codename for Project Oriole is {token}.",
        fact_conversation,
    )

    # Interaction B uses a brand-new stateless client and a new conversation.
    answer = primary_agent.handle_interaction(
        conn,
        FakeLLM(),
        "Use the memory specialist to tell me the codename for Project Oriole.",
        task_conversation,
    )
    assert token in answer

    events = event_store.get_events_by_conversation(conn, task_conversation)
    event_types = [event.event_type for event in events]
    assert EventType.AGENT_DELEGATION in event_types
    assert EventType.MEMORY_REQUEST in event_types
    assert EventType.MEMORY_PACKET in event_types
    assert EventType.AGENT_RESULT in event_types
    assert EventType.AGENT_RESPONSE in event_types

    correlations = {event.correlation_id for event in events}
    assert len(correlations) == 1

    packet_event = next(event for event in events if event.event_type == EventType.MEMORY_PACKET)
    result_event = next(event for event in events if event.event_type == EventType.AGENT_RESULT)
    memory_request_id = packet_event.payload["packet"]["memory_request_id"]
    assert memory_request_id in result_event.payload["memory_request_ids"]
    assert packet_event.payload["packet"]["supported"] is True
    assert packet_event.payload["packet"]["items"]
