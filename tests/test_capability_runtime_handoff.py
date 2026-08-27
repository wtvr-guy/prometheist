from datetime import datetime, timezone
import uuid

from jit_agent import capability_runtime, jit_memory
from jit_agent.capability_registry import DEFAULT_REGISTRY
from jit_agent.models import (
    CrossReferenceCandidateSelection,
    EventType,
    FocusedMemoryCandidateSelection,
    MemoryCandidateSelection,
    MemoryEvidence,
    MemoryNeed,
    MemoryPacket,
)


class Planner:
    def __init__(self, research_indices=(0,), cross_indices=(0, 1), focused_index=0) -> None:
        self.research_indices = list(research_indices)
        self.cross_indices = list(cross_indices)
        self.focused_index = focused_index
        self.research_packets: list[MemoryPacket] = []
        self.cross_packets: list[MemoryPacket] = []
        self.focused_packets: list[MemoryPacket] = []

    def select_research_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> MemoryCandidateSelection:
        del task
        self.research_packets.append(packet)
        return MemoryCandidateSelection(candidate_indices=self.research_indices)

    def select_cross_reference_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> CrossReferenceCandidateSelection:
        del task
        self.cross_packets.append(packet)
        return CrossReferenceCandidateSelection(candidate_indices=self.cross_indices)

    def select_focused_candidate(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> FocusedMemoryCandidateSelection:
        del task
        self.focused_packets.append(packet)
        return FocusedMemoryCandidateSelection(candidate_index=self.focused_index)


def _candidate_packet(count=3):
    conversation_id = uuid.uuid4()
    items = [
        MemoryEvidence(
            source_event_id=uuid.uuid4(),
            event_type=EventType.USER_PROMPT,
            source="user",
            created_at=datetime.now(timezone.utc),
            conversation_id=conversation_id,
            conversation_seq=index + 1,
            global_seq=index + 1,
            content=f"Canonical candidate {index}",
        )
        for index in range(count)
    ]
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="current percept", limit=max(1, count)),
        supported=bool(items),
        items=items,
    )


def _install_fakes(monkeypatch, captured):
    monkeypatch.setattr(
        capability_runtime.event_store,
        "get_event_by_id",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        capability_runtime.event_store,
        "record_event",
        lambda *args, **kwargs: None,
    )

    def fake_request_memory(_conn, **kwargs):
        captured["need"] = kwargs["need"]
        captured["profile"] = kwargs["recall_profile"]
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


def _execute(monkeypatch, capability_id, packet, planner=None):
    captured = {}
    _install_fakes(monkeypatch, captured)
    planner = planner or Planner()
    execution = capability_runtime.execute_registered_capability(
        object(),
        planner,
        registration=DEFAULT_REGISTRY.get(capability_id),
        capability_execution_id=uuid.uuid4(),
        requester_task_id=uuid.uuid4(),
        requester_step_id=uuid.uuid4(),
        round_index=1,
        plan_position=0,
        conversation_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        task_text="Investigate the unresolved question.",
        before_global_seq=100,
        memory_request_id=uuid.uuid4(),
        candidate_packet=packet,
    )
    return captured, planner, execution


def test_deeper_research_resolves_model_indices_to_canonical_focus_events(monkeypatch):
    packet = _candidate_packet(3)
    planner = Planner(research_indices=(2, 0))

    captured, planner, execution = _execute(
        monkeypatch,
        "deeper_research",
        packet,
        planner,
    )

    assert planner.research_packets == [packet]
    need = captured["need"]
    assert need.query_text is None
    assert need.entities == []
    assert need.focus_event_ids == [
        packet.items[2].source_event_id,
        packet.items[0].source_event_id,
    ]
    assert need.active_event_ids == []
    assert need.include_persisted_history is True
    assert captured["profile"] is jit_memory.MemoryRecallProfile.DEEPER_RESEARCH
    assert execution.result_data["candidate_indices"] == [2, 0]
    assert "answer" not in execution.model_dump(mode="json")


def test_cross_reference_resolves_two_or_more_candidates_as_one_joint_need(monkeypatch):
    packet = _candidate_packet(4)
    planner = Planner(cross_indices=(3, 1, 0))

    captured, planner, execution = _execute(
        monkeypatch,
        "cross_reference",
        packet,
        planner,
    )

    assert planner.cross_packets == [packet]
    need = captured["need"]
    assert need.query_text is None
    assert need.focus_event_ids == [
        packet.items[3].source_event_id,
        packet.items[1].source_event_id,
        packet.items[0].source_event_id,
    ]
    assert captured["profile"] is jit_memory.MemoryRecallProfile.CROSS_REFERENCE
    assert execution.result_data["candidate_indices"] == [3, 1, 0]


def test_focused_recall_resolves_exactly_one_canonical_candidate(monkeypatch):
    packet = _candidate_packet(3)
    planner = Planner(focused_index=1)

    captured, planner, execution = _execute(
        monkeypatch,
        "focused_recall",
        packet,
        planner,
    )

    assert planner.focused_packets == [packet]
    need = captured["need"]
    assert need.query_text is None
    assert need.focus_event_ids == [packet.items[1].source_event_id]
    assert captured["profile"] is jit_memory.MemoryRecallProfile.FOCUSED_RECALL
    assert execution.result_data["candidate_index"] == 1


def test_internal_memory_compatibility_path_uses_system_owned_current_task(monkeypatch):
    packet = _candidate_packet(1)

    captured, _, execution = _execute(monkeypatch, "internal_memory", packet)

    need = captured["need"]
    assert need.query_text == "Investigate the unresolved question."
    assert need.focus_event_ids == []
    assert captured["profile"] is jit_memory.MemoryRecallProfile.STANDARD
    assert execution.executor == "jit_memory"


def test_memory_capability_rejects_out_of_range_candidate_selection(monkeypatch):
    packet = _candidate_packet(1)
    planner = Planner(research_indices=(1,))
    captured = {}
    _install_fakes(monkeypatch, captured)

    try:
        capability_runtime.execute_registered_capability(
            object(),
            planner,
            registration=DEFAULT_REGISTRY.get("deeper_research"),
            capability_execution_id=uuid.uuid4(),
            requester_task_id=uuid.uuid4(),
            requester_step_id=uuid.uuid4(),
            round_index=0,
            plan_position=0,
            conversation_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            task_text="Investigate.",
            before_global_seq=100,
            memory_request_id=uuid.uuid4(),
            candidate_packet=packet,
        )
    except RuntimeError as exc:
        assert "outside the supplied packet" in str(exc)
    else:
        raise AssertionError("expected out-of-range candidate selection to fail closed")
