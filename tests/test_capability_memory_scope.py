from types import SimpleNamespace
import uuid

import pytest

from jit_agent import capability_runtime
from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.models import (
    MemoryNeedDecision,
    MemoryPacket,
    MemoryRetrievalScope,
)


class FakeLLM:
    def __init__(self) -> None:
        self.active_state_flags: list[bool] = []

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision:
        self.active_state_flags.append(active_state_available)
        catalog = task.split("[Anchor catalog]\n", 1)[1]
        first_index = int(catalog.splitlines()[0].split(": ", 1)[0])
        return MemoryNeedDecision(
            scope=MemoryRetrievalScope.HISTORY_ONLY,
            anchor_indices=[first_index],
        )


@pytest.mark.parametrize("capability_id", ["internal_memory", "deeper_research"])
def test_persisted_memory_capabilities_are_not_walled_by_conversation(
    monkeypatch,
    capability_id: str,
):
    captured = {}
    memory_request_id = uuid.uuid4()
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    registration = DEFAULT_REGISTRY.get(capability_id)

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
    llm = FakeLLM()
    capability_runtime.execute_registered_capability(
        object(),
        llm,
        registration=registration,
        capability_execution_id=uuid.uuid4(),
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=active_conversation_id,
        correlation_id=uuid.uuid4(),
        task_text="What did I establish previously?",
        before_global_seq=73,
        memory_request_id=memory_request_id,
    )

    assert llm.active_state_flags == [False]
    assert captured["event_conversation_id"] == active_conversation_id
    assert captured["need"].conversation_id is None
    assert captured["need"].include_persisted_history is True
    assert captured["need"].active_event_ids == []
    assert captured["before_global_seq"] == 73