from datetime import datetime, timezone
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


DISCOVERY_TIME = datetime(2026, 8, 26, 17, 18, tzinfo=timezone.utc)


class Planner:
    def plan_memory(self, task: str) -> MemoryNeedDecision:
        return MemoryNeedDecision(
            query_text="Project Oriole codename",
            entities=["Project Oriole"],
        )


def _packet(step_id: uuid.UUID, task_id: uuid.UUID) -> CapabilityPacket:
    registration = DEFAULT_REGISTRY.get("internal_memory")
    return CapabilityPacket(
        capability_request_id=deterministic_capability_request_id(step_id),
        requester_task_id=task_id,
        requester_step_id=step_id,
        need=CapabilityNeed(
            query_text="What did I establish?",
            supplemental_query_texts=[
                "access to persisted internal history to identify established kestrel rule "
                "and its associated constraint profile"
            ],
            limit=1,
        ),
        matches=[
            CapabilityMatch(
                descriptor=registration.descriptor,
                score=1.0,
            )
        ],
        selected_query_role="canonical",
        selected_query_text="What did I establish?",
    )


def _install_fakes(monkeypatch, packet: CapabilityPacket, captured: dict) -> None:
    monkeypatch.setattr(
        capability_runtime.event_store,
        "get_event_by_id",
        lambda _conn, _event_id: SimpleNamespace(
            event_type=EventType.CAPABILITY_PACKET,
            payload={"packet": packet.model_dump(mode="json")},
            created_at=DISCOVERY_TIME,
        ),
    )
    monkeypatch.setattr(
        capability_runtime.event_store,
        "record_event",
        lambda *args, **kwargs: None,
    )

    def fake_request_memory(_conn, **kwargs):
        captured["need"] = kwargs["need"]
        return MemoryPacket(
            memory_request_id=kwargs["memory_request_id"],
            need=kwargs["need"],
            supported=False,
            items=[],
        )

    monkeypatch.setattr(
        capability_runtime.jit_memory,
        "request_memory",
        fake_request_memory,
    )


def test_internal_memory_preserves_discovery_supplemental_and_cross_conversation_scope(
    monkeypatch,
):
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    packet = _packet(step_id, task_id)
    captured = {}
    _install_fakes(monkeypatch, packet, captured)

    capability_runtime.execute_registered_capability(
        object(),
        Planner(),
        registration=DEFAULT_REGISTRY.get("internal_memory"),
        capability_request_id=packet.capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        task_text=(
            "Which of those approaches conflicts with my established Kestrel rule, "
            "and what constraint profile did I give that rule?"
        ),
        capability_input=None,
        before_global_seq=100,
        memory_request_id=uuid.uuid4(),
    )

    need = captured["need"]
    assert need.conversation_id is None
    assert need.entities == ["Kestrel"]
    assert need.reference_time is None
    assert need.supplemental_query_texts == [
        "access to persisted internal history to identify established kestrel rule "
        "and its associated constraint profile"
    ]


def test_internal_memory_uses_durable_reference_time_for_recent_context(monkeypatch):
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    packet = _packet(step_id, task_id)
    captured = {}
    _install_fakes(monkeypatch, packet, captured)

    capability_runtime.execute_registered_capability(
        object(),
        Planner(),
        registration=DEFAULT_REGISTRY.get("internal_memory"),
        capability_request_id=packet.capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        task_text="What nickname are we using for this plan, and which approach did you just rule out?",
        capability_input=None,
        before_global_seq=100,
        memory_request_id=uuid.uuid4(),
    )

    need = captured["need"]
    assert need.reference_time == DISCOVERY_TIME
    assert need.conversation_id is None


def test_memory_analysis_merges_discovery_and_planned_supplementals(monkeypatch):
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    packet = _packet(step_id, task_id)
    packet = packet.model_copy(
        update={
            "matches": [
                CapabilityMatch(
                    descriptor=DEFAULT_REGISTRY.get("memory_analysis").descriptor,
                    score=1.0,
                )
            ]
        }
    )
    captured = {}
    _install_fakes(monkeypatch, packet, captured)

    capability_runtime.execute_registered_capability(
        object(),
        Planner(),
        registration=DEFAULT_REGISTRY.get("memory_analysis"),
        capability_request_id=packet.capability_request_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        conversation_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        task_text="Use memory analysis to recall the codename.",
        capability_input=None,
        before_global_seq=100,
        memory_request_id=uuid.uuid4(),
    )

    need = captured["need"]
    assert need.conversation_id is None
    assert need.entities == ["Project Oriole"]
    assert need.reference_time is None
    assert need.supplemental_query_texts == [
        "access to persisted internal history to identify established kestrel rule "
        "and its associated constraint profile",
        "Project Oriole codename",
    ]
