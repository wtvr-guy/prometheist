import uuid
from datetime import datetime, timezone

import pytest

from jit_agent import db, event_store
from jit_agent.attention_observation import HostResourceMetrics
from jit_agent.interaction_policy import (
    INTERACTION_STAGES,
    CapabilityRequirement,
    InteractionDecision,
    InteractionStage,
)
from jit_agent.interaction_runtime import (
    begin_interaction,
    execute_next_interaction_step,
)
from jit_agent.models import (
    EventType,
    MemoryNeedDecision,
    MemoryPacket,
    MemoryRetrievalScope,
)


NOW = datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc)


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


class DirectLLM:
    def classify(self, prompt: str, memory_packet: MemoryPacket) -> InteractionDecision:
        del prompt, memory_packet
        return InteractionDecision(required_capability=CapabilityRequirement.NONE)

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        return "completed response"

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision:
        del task, active_state_available
        return MemoryNeedDecision(
            scope=MemoryRetrievalScope.HISTORY_ONLY,
            anchor_indices=[0],
        )

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        return "completed analysis"


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _kwargs():
    return {"probe": FixedProbe(), "clock": lambda: NOW}


def test_final_interaction_event_failure_records_durable_error(conn, monkeypatch):
    conversation_id = uuid.uuid4()
    interaction = begin_interaction(conn, "hello", conversation_id, **_kwargs())
    for index, stage in enumerate(INTERACTION_STAGES[:-1]):
        assert (
            execute_next_interaction_step(
                conn,
                DirectLLM(),
                interaction,
                worker_id=f"worker-{index}",
                **_kwargs(),
            )
            is stage
        )

    original_record_event = event_store.record_event

    def fail_interaction_response(*args, **kwargs):
        if kwargs.get("event_type") is EventType.INTERACTION_RESPONSE:
            raise RuntimeError("final interaction event write failed")
        return original_record_event(*args, **kwargs)

    monkeypatch.setattr(event_store, "record_event", fail_interaction_response)

    with pytest.raises(RuntimeError, match="final interaction event write failed"):
        execute_next_interaction_step(
            conn,
            DirectLLM(),
            interaction,
            worker_id="persist-worker",
            **_kwargs(),
        )

    events = event_store.get_events_by_conversation(conn, conversation_id)
    errors = [event for event in events if event.event_type is EventType.ERROR]
    assert errors[-1].payload["stage"] == InteractionStage.PERSIST_RESULT.value
    assert errors[-1].payload["error_type"] == "RuntimeError"