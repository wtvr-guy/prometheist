from types import SimpleNamespace
import uuid

from jit_agent import capability_runtime
from jit_agent.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityMatch,
    CapabilityNeed,
    CapabilityPacket,
    deterministic_capability_request_id,
)
from jit_agent.models import (
    EventType,
    MemoryNeedDecision,
    MemoryPacket,
    MemoryRetrievalScope,
)


class Planner:
    def __init__(self, scope: MemoryRetrievalScope = MemoryRetrievalScope.ACTIVE_AND_HISTORY) -> None:
        self.scope = scope
        self.inputs: list[str] = []
        self.active_state_flags: list[bool] = []

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision:
        self.inputs.append(task)
        self.active_state_flags.append(active_state_available)
        if self.scope is MemoryRetrievalScope.ACTIVE_ONLY:
            return MemoryNeedDecision(scope=self.scope, anchor_indices=[])

        catalog = task.split("[Anchor catalog]\n", 1)[1]
        entries = {}
        for line in catalog.splitlines():
            index_text, value = line.split(": ", 1)
            entries[value] = int(index_text)
        return MemoryNeedDecision(
            scope=self.scope,
            anchor_indices=[entries["oriole"]],
        )


def _packet(step_id: uuid.UUID, task_id: uuid.UUID, capability_id="internal_memory"):
    registration = DEFAULT_REGISTRY.get(capability_id)
    return CapabilityPacket(
        capability_request_id=deterministic_capability_request_id(step_id),
        requester_task_id=task_id,
        requester_step_id=step_id,
        need=CapabilityNeed(query_text=capability_id, limit=1),
        matches=[CapabilityMatch(descriptor=registration.descriptor, score=8.0)],
        selected_query_role="canonical",
        selected_query_text=capability_id,
    )


def _install_fakes(monkeypatch, packet, captured, active_event_ids):
    active_events = {
        event_id: SimpleNamespace(
            event_type=EventType.USER_PROMPT,
            payload={"text": "The active situation is Project Oriole planning."},
            global_seq=25,
        )
        for event_id in active_event_ids
    }

    def fake_get_event(_conn, event_id):
        if event_id in active_events:
            return active_events[event_id]
        return SimpleNamespace(
            event_type=EventType.CAPABILITY_PACKET,
            payload={"packet": packet.model_dump(mode="json")},
        )

    monkeypatch.setattr(capability_runtime.event_store, "get_event_by_id", fake_get_event)
    monkeypatch.setattr(
        capability_runtime.event_store,
        "record_event",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        capability_runtime,
        "load_working_state",
        lambda _conn, _conversation_id: SimpleNamespace(
            active_event_ids=list(active_event_ids)
        ),
    )

    def fake_request_memory(_conn, **kwargs):
        captured["need"] = kwargs["need"]
        return MemoryPacket(
            memory_request_id=kwargs["memory_request_id"],
            need=kwargs["need"],
            supported=False,
            items=[],
        )

    monkeypatch.setattr(capability_runtime.jit_memory, "request_memory", fake_request_memory)
    monkeypatch.setattr(
        capability_runtime,
        "activate_working_state",
        lambda *args, **kwargs: captured.setdefault("activation", kwargs),
    )


def _execute(
    monkeypatch,
    capability_id="internal_memory",
    scope: MemoryRetrievalScope = MemoryRetrievalScope.ACTIVE_AND_HISTORY,
):
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    state_event_id = uuid.uuid4()
    packet = _packet(step_id, task_id, capability_id)
    captured = {}
    _install_fakes(monkeypatch, packet, captured, [state_event_id])
    planner = Planner(scope)

    capability_runtime.execute_registered_capability(
        object(),
        planner,
        registration=DEFAULT_REGISTRY.get(capability_id),
        capability_request_id=packet.capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_text="What codename applies to Project Oriole in the active plan?",
        before_global_seq=100,
        memory_request_id=uuid.uuid4(),
    )
    return captured, planner, state_event_id, conversation_id, correlation_id


def test_internal_memory_uses_active_context_and_index_only_memory_routing(monkeypatch):
    captured, planner, state_event_id, conversation_id, correlation_id = _execute(monkeypatch)

    assert len(planner.inputs) == 1
    assert planner.active_state_flags == [True]
    planner_input = planner.inputs[0]
    assert "[Current task]" in planner_input
    assert "[Active canonical context]" in planner_input
    assert "The active situation is Project Oriole planning." in planner_input
    assert "[Anchor catalog]" in planner_input
    assert "oriole" in planner_input

    need = captured["need"]
    assert need.conversation_id is None
    assert need.active_event_ids == [state_event_id]
    assert need.include_persisted_history is True
    assert need.entities == ["oriole"]
    assert need.reference_time is None
    assert need.supplemental_query_texts == []
    assert captured["activation"]["conversation_id"] == conversation_id
    assert captured["activation"]["correlation_id"] == correlation_id


def test_active_only_scope_disables_long_term_search_without_phrase_policy(monkeypatch):
    captured, planner, state_event_id, _, _ = _execute(
        monkeypatch,
        scope=MemoryRetrievalScope.ACTIVE_ONLY,
    )

    assert planner.active_state_flags == [True]
    need = captured["need"]
    assert need.active_event_ids == [state_event_id]
    assert need.include_persisted_history is False
    assert need.entities == []


def test_memory_analysis_uses_same_index_only_memory_boundary(monkeypatch):
    captured, planner, state_event_id, _, _ = _execute(monkeypatch, "memory_analysis")

    assert planner.active_state_flags == [True]
    assert "[Anchor catalog]" in planner.inputs[0]
    need = captured["need"]
    assert need.active_event_ids == [state_event_id]
    assert need.include_persisted_history is True
    assert need.entities == ["oriole"]
