import re
import uuid

import pytest

from jit_agent import db, event_store, primary_agent
from jit_agent.models import AgentAction, AgentDecision, EventType, RetrievalItem


class FakeLLM:
    """Deterministic rule-based stand-in for an LLM, used so tests don't
    depend on Ollama being installed/reliable. Exercises the same
    classify -> retrieve -> respond pipeline the real OllamaClient would.
    """

    def classify(self, prompt: str) -> AgentDecision:
        lowered = prompt.lower()
        if "what" in lowered and ("remember" in lowered or "number" in lowered):
            return AgentDecision(action=AgentAction.RETRIEVE_CONTEXT, query_text="remember")
        return AgentDecision(action=AgentAction.RESPOND_DIRECTLY)

    def respond(self, prompt: str, retrieved_items: list[RetrievalItem] | None) -> str:
        if retrieved_items:
            match = re.search(r"[0-9a-fA-F]{6,}", retrieved_items[0].content)
            if match:
                return f"You asked me to remember {match.group(0)}."
            return retrieved_items[0].content
        if "hello" in prompt.lower():
            return "Hello! How can I help?"
        return "Got it."


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def test_acceptance_scenario_three_interactions(conn):
    """Reproduces spec section 14: hello -> remember X -> what was X, using
    fresh handle_interaction calls (each a separate 'interaction')."""
    conversation_id = uuid.uuid4()
    llm = FakeLLM()

    reply1 = primary_agent.handle_interaction(conn, llm, "hello", conversation_id)
    assert reply1

    token = uuid.uuid4().hex[:10]
    reply2 = primary_agent.handle_interaction(
        conn, llm, f"I want you to remember {token}.", conversation_id
    )
    assert reply2

    reply3 = primary_agent.handle_interaction(
        conn, llm, "what was that number I just asked you to remember?", conversation_id
    )
    assert token in reply3


def test_memory_spans_conversations_by_default(conn):
    """Conversation boundaries are organizational metadata, not memory
    walls: a fact told in one conversation must be recallable from a brand
    new conversation, not just the one it was originally told in.
    """
    llm = FakeLLM()
    conv_a = uuid.uuid4()
    conv_b = uuid.uuid4()

    token = uuid.uuid4().hex[:10]
    primary_agent.handle_interaction(conn, llm, f"remember {token}", conv_a)

    reply = primary_agent.handle_interaction(
        conn, llm, "what number did I ask you to remember?", conv_b
    )
    assert token in reply


class RaisingLLM:
    def classify(self, prompt: str) -> AgentDecision:
        raise RuntimeError("boom")

    def respond(self, prompt: str, retrieved_items: list[RetrievalItem] | None) -> str:
        raise AssertionError("should not be reached")


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
    """Two calls using brand-new LLM client instances each time -- proves no
    state needs to survive in the orchestration layer between interactions."""
    conversation_id = uuid.uuid4()

    reply1 = primary_agent.handle_interaction(conn, FakeLLM(), "hello", conversation_id)
    reply2 = primary_agent.handle_interaction(conn, FakeLLM(), "hello again", conversation_id)

    assert reply1 and reply2
