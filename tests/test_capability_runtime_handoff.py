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
from jit_agent.models import EventType, MemoryNeedDecision, MemoryPacket


class Planner:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def plan_memory(self, task: str) -> MemoryNeedDecision:
        self.inputs.append(task)
        return MemoryNeedDecision(
            query_text="Project Oriole codename",
            entities=["Project Oriole"],
        )


def _packet(step_id: uuid.UUID, task_id: uuid.UUID, capability_id="internal_memory"):
    registration = DEFAULT_REGISTRY.get(capability_id)
    return CapabilityPacket(
        capability_request_id=deterministic_capability_request_id(step_id),
        requester_task_id=task_id,
        requester_step_id=step_id,
        need=CapabilityNeed(
            query_text="What did I establish?",
            supplemental_query_texts=["persisted internal history"],
            limit=1,
        ),
        matches=[CapabilityMatch(descriptor=registration.descriptor, score=1.0)],
        selected_query_role="canonical",
        selected_query_text="What did I establish?",
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


def _execute(monkeypatch, capability_id="internal_memory"):
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    state_event_id = uuid.uuid4()
    packet = _packet(step_id, task_id, capability_id)
    captured = {}
    _install_fakes(monkeypatch, packet, captured, [state_event_id])
    planner = Planner()

    capability_runtime.execute_registered_capability(
        object(),
        planner,
        registration=DEFAULT_REGISTRY.get(capability_id),
        capability_request_id=packet.capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_text="Natural-language request whose wording is not application policy.",
        capability_input="narrow the historical information need",
        before_global_seq=100,
        memory_request_id=uuid.uuid4(),
    )
    return captured, planner, state_event_id, conversation_id, correlation_id


def test_internal_memory_uses_working_state_and_stateless_semantic_plan(monkeypatch):
    captured, planner, state_event_id, conversation_id, correlation_id = _execute(monkeypatch)

    assert len(planner.inputs) == 1
    planner_input = planner.inputs[0]
    assert "[Current task]" in planner_input
    assert "Natural-language request whose wording is not application policy." in planner_input
    assert "[Capability narrowing]" in planner_input
    assert "narrow the historical information need" in planner_input
    assert "[Active canonical context]" in planner_input
    assert "The active situation is Project Oriole planning." in planner_input

    need = captured["need"]
    assert need.conversation_id is None
    assert need.active_event_ids == [state_event_id]
    assert need.entities == ["Project Oriole"]
    assert need.reference_time is None
    assert need.supplemental_query_texts == [
        "Project Oriole codename",
        "persisted internal history",
    ]
    assert captured["activation"]["conversation_id"] == conversation_id
    assert captured["activation"]["correlation_id"] == correlation_id


def test_memory_analysis_uses_same_state_driven_memory_boundary(monkeypatch):
    captured, planner, state_event_id, _, _ = _execute(monkeypatch, "memory_analysis")

    assert "[Active canonical context]" in planner.inputs[0]
    need = captured["need"]
    assert need.active_event_ids == [state_event_id]
    assert need.entities == ["Project Oriole"]
    assert need.supplemental_query_texts[0] == "Project Oriole codename"