from types import SimpleNamespace
import uuid

import pytest

from jit_agent import capability_runtime
from jit_agent.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityMatch,
    CapabilityNeed,
    CapabilityPacket,
)
from jit_agent.models import EventType, MemoryNeedDecision, MemoryPacket


class FakeLLM:
    def plan_memory(self, task: str) -> MemoryNeedDecision:
        return MemoryNeedDecision(query_text=task, entities=[])


@pytest.mark.parametrize("capability_id", ["internal_memory", "memory_analysis"])
def test_persisted_memory_capabilities_are_not_walled_by_conversation(
    monkeypatch,
    capability_id: str,
):
    captured = {}
    memory_request_id = uuid.uuid4()
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    capability_request_id = uuid.uuid4()
    registration = DEFAULT_REGISTRY.get(capability_id)
    discovery_packet = CapabilityPacket(
        capability_request_id=capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        need=CapabilityNeed(query_text="What did I establish previously?", limit=1),
        matches=[CapabilityMatch(descriptor=registration.descriptor, score=1.0)],
        selected_query_role="canonical",
        selected_query_text="What did I establish previously?",
    )

    monkeypatch.setattr(
        capability_runtime.event_store,
        "get_event_by_id",
        lambda _conn, _event_id: SimpleNamespace(
            event_type=EventType.CAPABILITY_PACKET,
            payload={"packet": discovery_packet.model_dump(mode="json")},
        ),
    )
    monkeypatch.setattr(
        capability_runtime,
        "load_working_state",
        lambda _conn, _conversation_id: None,
    )
    monkeypatch.setattr(
        capability_runtime,
        "activate_working_state",
        lambda *args, **kwargs: None,
    )

    def fake_request_memory(
        conn,
        *,
        conversation_id,
        correlation_id,
        requesting_component,
        need,
        before_global_seq,
        memory_request_id,
    ):
        captured["need"] = need
        captured["event_conversation_id"] = conversation_id
        captured["before_global_seq"] = before_global_seq
        return MemoryPacket(
            memory_request_id=memory_request_id,
            need=need,
            supported=False,
            items=[],
        )

    monkeypatch.setattr(capability_runtime.jit_memory, "request_memory", fake_request_memory)
    monkeypatch.setattr(
        capability_runtime.event_store,
        "record_event",
        lambda *args, **kwargs: None,
    )

    active_conversation_id = uuid.uuid4()
    capability_runtime.execute_registered_capability(
        object(),
        FakeLLM(),
        registration=registration,
        capability_request_id=capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=active_conversation_id,
        correlation_id=uuid.uuid4(),
        task_text="What did I establish previously?",
        capability_input=None,
        before_global_seq=73,
        memory_request_id=memory_request_id,
    )

    assert captured["event_conversation_id"] == active_conversation_id
    assert captured["need"].conversation_id is None
    assert captured["before_global_seq"] == 73
