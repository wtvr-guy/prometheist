import re
import uuid
from datetime import datetime, timezone

import pytest

from jit_agent import db, event_store
from jit_agent.attention_aperture import ATTENTION_APERTURE_VERSION
from jit_agent.attention_observation import HostResourceMetrics
from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.interaction_policy import (
    INTERACTION_STAGES,
    InteractionAction,
    InteractionDecision,
    InteractionStage,
    requires_persisted_context,
)
from jit_agent.interaction_runtime import (
    begin_interaction,
    execute_next_interaction_step,
    finish_interaction,
    handle_interaction,
)
from jit_agent.models import (
    EventType,
    FocusedMemoryCandidateSelection,
    MemoryCandidateSelection,
    MemoryPacket,
)
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


def _candidate_index(packet: MemoryPacket, pattern: str | None = None) -> int:
    if pattern is not None:
        for index, item in enumerate(packet.items):
            if pattern in item.content:
                return index
    if not packet.items:
        raise AssertionError("expected at least one memory candidate")
    return 0


class FakeLLM:
    def classify(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        completed_results=(),
        capability_results=(),
    ) -> InteractionDecision:
        del (
            prompt,
            memory_packet,
            capability_catalog,
            completed_results,
            capability_results,
        )
        return InteractionDecision(
            next_action=InteractionAction.RESPOND,
            capability_indices=[],
        )

    def respond(
        self,
        prompt: str,
        memory_packet: MemoryPacket | None,
        capability_results=(),
    ) -> str:
        del prompt, capability_results
        if memory_packet and memory_packet.items:
            for item in memory_packet.items:
                match = re.search(r"[0-9a-f]{10}", item.content)
                if match:
                    return f"You asked me to remember {match.group(0)}."
        return "Got it."

    def select_research_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> MemoryCandidateSelection:
        del task
        return MemoryCandidateSelection(candidate_indices=[_candidate_index(packet)])

    def select_focused_candidate(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> FocusedMemoryCandidateSelection:
        del task
        return FocusedMemoryCandidateSelection(candidate_index=_candidate_index(packet))


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _kwargs():
    return {"probe": FixedProbe(), "clock": lambda: NOW}


def test_phrase_based_reference_detector_is_deprecated_and_disabled():
    assert requires_persisted_context("What did we just rule out?") is False
    assert requires_persisted_context("Use that approach.") is False
    assert requires_persisted_context("Tell me about PostgreSQL.") is False


def test_end_to_end_interaction_uses_only_durable_task_neutral_workers(conn):
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
        EventType.MEMORY_REQUEST,
        EventType.MEMORY_PACKET,
        EventType.INTERACTION_WORKING_STATE,
        EventType.SYSTEM_EVENT,
        EventType.INTERACTION_RESPONSE,
        EventType.INTERACTION_WORKING_STATE,
    ]
    round_event = next(event for event in events if event.event_type is EventType.SYSTEM_EVENT)
    assert round_event.payload["kind"] == "CAPABILITY_DECISION_ROUND"
    assert round_event.payload["round"]["decision"] == {
        "next_action": "RESPOND",
        "capability_indices": [],
    }
    assert round_event.payload["round"]["capability_results"] == []
    response_event = next(
        event for event in events if event.event_type is EventType.INTERACTION_RESPONSE
    )
    assert response_event.source == "attention_interaction"
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM attention_worker_results")
        assert cur.fetchone()[0] == len(INTERACTION_STAGES)
        cur.execute("SELECT status FROM attention_tasks")
        assert cur.fetchone()[0] == "COMPLETED"


def test_every_percept_opens_memory_context_before_capability_selection(conn):
    conversation_id = uuid.uuid4()
    handle_interaction(conn, FakeLLM(), "hello", conversation_id, **_kwargs())

    interaction = begin_interaction(
        conn,
        "entirely arbitrary follow-up wording",
        conversation_id,
        **_kwargs(),
    )
    execute_next_interaction_step(
        conn,
        FakeLLM(),
        interaction,
        worker_id="state-resolution-worker",
        **_kwargs(),
    )
    execute_next_interaction_step(
        conn,
        FakeLLM(),
        interaction,
        worker_id="state-selection-worker",
        **_kwargs(),
    )

    classify_id = deterministic_worker_step_id(
        interaction.assignment_id,
        InteractionStage.SELECT_CAPABILITY.value,
    )
    classified = load_worker_result(conn, classify_id)
    assert classified.output["attention_aperture_version"] == ATTENTION_APERTURE_VERSION
    assert classified.output["aperture_packet"]["memory_request_id"]
    assert classified.output["initial_round"]["decision"] == {
        "next_action": "RESPOND",
        "capability_indices": [],
    }
    assert classified.output["initial_round"]["execution_plan"]["items"] == []


def test_fresh_workers_resume_interaction_from_postgres_and_preserve_continuity(conn):
    fact_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10]
    handle_interaction(
        conn,
        FakeLLM(),
        f"I want you to remember {token}.",
        fact_conversation,
        **_kwargs(),
    )

    recall_conversation = uuid.uuid4()
    interaction = begin_interaction(
        conn,
        "What number did I ask you to remember, as we just discussed?",
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
        InteractionStage.SELECT_CAPABILITY.value,
    )
    classified = load_worker_result(conn, classify_id)
    assert classified.output["initial_round"]["decision"] == {
        "next_action": "RESPOND",
        "capability_indices": [],
    }
    events = event_store.get_events_by_conversation(conn, recall_conversation)
    event_types = [event.event_type for event in events]
    assert EventType.MEMORY_REQUEST in event_types
    assert EventType.MEMORY_PACKET in event_types
    assert EventType.CAPABILITY_REQUEST not in event_types
    assert EventType.CAPABILITY_PACKET not in event_types
    assert EventType.CAPABILITY_RESULT not in event_types
    assert EventType.INTERACTION_WORKING_STATE in event_types


def test_selected_deeper_research_gets_fresh_second_decision_before_final_response(conn):
    class ResearchLLM(FakeLLM):
        def __init__(self):
            self.classify_calls = 0
            self.respond_calls = 0
            self.routing_capability_results = []

        def classify(
            self,
            prompt: str,
            memory_packet: MemoryPacket,
            capability_catalog: tuple[CapabilityDescriptor, ...],
            completed_results=(),
            capability_results=(),
        ) -> InteractionDecision:
            del prompt, memory_packet, completed_results
            self.classify_calls += 1
            self.routing_capability_results.append(tuple(capability_results))
            if self.classify_calls == 1:
                index = next(
                    index
                    for index, descriptor in enumerate(capability_catalog)
                    if descriptor.capability_id == "deeper_research"
                )
                return InteractionDecision(
                    next_action=InteractionAction.USE_CAPABILITIES,
                    capability_indices=[index],
                )
            return InteractionDecision(
                next_action=InteractionAction.RESPOND,
                capability_indices=[],
            )

        def respond(self, prompt, memory_packet, capability_results=()):
            self.respond_calls += 1
            return super().respond(prompt, memory_packet, capability_results)

        def select_research_candidates(self, task, packet):
            del task
            return MemoryCandidateSelection(
                candidate_indices=[_candidate_index(packet, token)]
            )

    token = uuid.uuid4().hex[:10]
    handle_interaction(
        conn,
        FakeLLM(),
        f"I want you to remember opaque token {token}.",
        uuid.uuid4(),
        **_kwargs(),
    )
    llm = ResearchLLM()
    interaction = begin_interaction(
        conn,
        "Investigate my remembered opaque token more deeply before answering.",
        uuid.uuid4(),
        **_kwargs(),
    )
    for index in range(len(INTERACTION_STAGES)):
        execute_next_interaction_step(
            conn,
            llm,
            interaction,
            worker_id=f"research-worker-{index}",
            **_kwargs(),
        )

    response = finish_interaction(conn, interaction, **_kwargs())
    assert token in response
    assert llm.classify_calls == 2
    assert llm.respond_calls == 1
    assert llm.routing_capability_results[0] == ()
    assert len(llm.routing_capability_results[1]) == 1
    assert llm.routing_capability_results[1][0]["capability_id"] == "deeper_research"
    assert "result_data" in llm.routing_capability_results[1][0]
    execute_id = deterministic_worker_step_id(
        interaction.assignment_id,
        InteractionStage.EXECUTE_CAPABILITY.value,
    )
    execution = load_worker_result(conn, execute_id)
    assert len(execution.output["rounds"]) == 2
    assert execution.output["rounds"][1]["capability_results"][0][
        "capability_id"
    ] == "deeper_research"
    assert [item["capability_id"] for item in execution.output["executions"]] == [
        "deeper_research"
    ]
    assert execution.output["final_decision"] == {
        "next_action": "RESPOND",
        "capability_indices": [],
    }


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
    assert [event.event_type for event in events].count(EventType.INTERACTION_RESPONSE) == 1
    assert [event.event_type for event in events].count(EventType.INTERACTION_WORKING_STATE) == 2


def test_step_publication_repair_is_idempotent(conn):
    interaction = begin_interaction(conn, "hello", uuid.uuid4(), **_kwargs())

    execute_next_interaction_step(
        conn,
        FakeLLM(),
        interaction,
        worker_id="repair-check-worker",
        **_kwargs(),
    )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM attention_worker_steps WHERE task_id = %s",
            (interaction.task_id,),
        )
        assert cur.fetchone()[0] == len(INTERACTION_STAGES)
