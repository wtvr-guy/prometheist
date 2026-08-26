import re
import uuid
from datetime import datetime, timezone

import pytest

from jit_agent import db, event_store, primary_agent
from jit_agent.attention_observation import HostResourceMetrics
from jit_agent.interaction_policy import (
    CONTINUITY_POLICY_VERSION,
    INTERACTION_STAGES,
    InteractionStage,
    requires_persisted_context,
)
from jit_agent.interaction_runtime import (
    begin_interaction,
    execute_next_interaction_step,
    finish_interaction,
    handle_interaction,
)
from jit_agent.models import AgentAction, AgentDecision, EventType, MemoryNeedDecision, MemoryPacket
from jit_agent.worker_protocol import deterministic_worker_step_id
from jit_agent.worker_store import load_worker_result


NOW = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)


class FixedProbe:
    def capture(self) -> HostResourceMetrics:
        return HostResourceMetrics(
            platform="test",
            logical_cpu_count=8,
            cpu_utilization_percent=10,
            load_1m=0,
            memory_total_mib=16_384,
            memory_available_mib=12_000,
        )


class FakeLLM:
    def classify(self, prompt: str) -> AgentDecision:
        if "what" in prompt.lower() and "remember" in prompt.lower():
            return AgentDecision(
                action=AgentAction.RETRIEVE_CONTEXT,
                query_text="remembered value",
            )
        return AgentDecision(action=AgentAction.RESPOND_DIRECTLY)

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        if memory_packet and memory_packet.items:
            match = re.search(r"[0-9a-f]{10}", memory_packet.items[0].content)
            return f"You asked me to remember {match.group(0)}."
        return "Got it."

    def plan_memory(self, task: str) -> MemoryNeedDecision:
        return MemoryNeedDecision(query_text=task)

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        return packet.items[0].content


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _kwargs():
    return {"probe": FixedProbe(), "clock": lambda: NOW}


def test_reference_policy_is_reusable_and_does_not_claim_general_coreference():
    assert requires_persisted_context("What did we just rule out?") is True
    assert requires_persisted_context("Use that approach.") is True
    assert requires_persisted_context(
        "Compare caching and recomputation; which of those approaches is safer?"
    ) is False
    assert requires_persisted_context("Tell me about PostgreSQL.") is False


def test_end_to_end_interaction_uses_durable_workers_not_primary_agent(conn, monkeypatch):
    monkeypatch.setattr(
        primary_agent,
        "handle_interaction",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("legacy path used")),
    )
    conversation_id = uuid.uuid4()
    response = handle_interaction(
        conn,
        FakeLLM(),
        "hello",
        conversation_id,
        **_kwargs(),
    )

    assert response == "Got it."
    events = event_store.get_events_by_conversation(conn, conversation_id)
    assert [event.event_type for event in events] == [
        EventType.USER_PROMPT,
        EventType.AGENT_RESPONSE,
    ]
    assert events[-1].source == "attention_interaction"
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM attention_worker_results")
        assert cur.fetchone()[0] == len(INTERACTION_STAGES)
        cur.execute("SELECT status FROM attention_tasks")
        assert cur.fetchone()[0] == "COMPLETED"


def test_fresh_workers_resume_interaction_from_postgres_and_preserve_continuity(conn):
    fact_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10]
    handle_interaction(
        conn,
        FakeLLM(),
        f"Remember {token}.",
        fact_conversation,
        **_kwargs(),
    )

    recall_conversation = uuid.uuid4()
    interaction = begin_interaction(
        conn,
        "What did we just decide to remember?",
        recall_conversation,
        **_kwargs(),
    )
    first = execute_next_interaction_step(
        conn,
        FakeLLM(),
        interaction,
        worker_id="worker-process-1",
        **_kwargs(),
    )
    assert first is InteractionStage.RESOLVE_REFERENCES

    # Every following call reconstructs inputs from PostgreSQL and uses a new
    # worker and stateless LLM object; no Python transcript or coordinator state survives.
    for index in range(1, len(INTERACTION_STAGES)):
        execute_next_interaction_step(
            conn,
            FakeLLM(),
            interaction,
            worker_id=f"worker-process-{index + 1}",
            **_kwargs(),
        )
    response = finish_interaction(conn, interaction, **_kwargs())
    assert token in response

    classify_id = deterministic_worker_step_id(
        interaction.assignment_id,
        InteractionStage.CLASSIFY.value,
    )
    classified = load_worker_result(conn, classify_id)
    assert classified.output["continuity_policy"] == CONTINUITY_POLICY_VERSION
    assert classified.output["decision"]["action"] == AgentAction.RETRIEVE_CONTEXT.value


def test_deterministic_response_event_retry_does_not_duplicate_history(conn):
    conversation_id = uuid.uuid4()
    interaction = begin_interaction(conn, "hello", conversation_id, **_kwargs())
    for index in range(len(INTERACTION_STAGES)):
        execute_next_interaction_step(
            conn,
            FakeLLM(),
            interaction,
            worker_id=f"worker-{index}",
            **_kwargs(),
        )
    assert finish_interaction(conn, interaction, **_kwargs()) == "Got it."
    assert finish_interaction(conn, interaction, **_kwargs()) == "Got it."
    events = event_store.get_events_by_conversation(conn, conversation_id)
    assert [event.event_type for event in events].count(EventType.AGENT_RESPONSE) == 1
