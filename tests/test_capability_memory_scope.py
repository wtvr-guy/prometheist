from datetime import datetime, timezone
import uuid

import pytest

from jit_agent import capability_runtime
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


class FakeLLM:
    def select_research_candidates(self, task, packet):
        del task, packet
        return MemoryCandidateSelection(candidate_indices=[0])

    def select_cross_reference_candidates(self, task, packet):
        del task, packet
        return CrossReferenceCandidateSelection(candidate_indices=[0, 1])

    def select_focused_candidate(self, task, packet):
        del task, packet
        return FocusedMemoryCandidateSelection(candidate_index=0)


def _candidate_packet(count: int) -> MemoryPacket:
    conversation_id = uuid.uuid4()
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="current percept", limit=max(1, count)),
        supported=bool(count),
        items=[
            MemoryEvidence(
                source_event_id=uuid.uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                created_at=datetime.now(timezone.utc),
                conversation_id=conversation_id,
                conversation_seq=index + 1,
                global_seq=index + 1,
                content=f"Candidate {index}",
            )
            for index in range(count)
        ],
    )


@pytest.mark.parametrize(
    ("capability_id", "candidate_count"),
    [
        ("internal_memory", 1),
        ("deeper_research", 1),
        ("cross_reference", 2),
        ("focused_recall", 1),
    ],
)
def test_persisted_memory_capabilities_are_not_walled_by_conversation(
    monkeypatch,
    capability_id: str,
    candidate_count: int,
):
    captured = {}
    memory_request_id = uuid.uuid4()
    active_conversation_id = uuid.uuid4()

    monkeypatch.setattr(
        capability_runtime,
        "activate_working_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        capability_runtime.event_store,
        "get_event_by_id",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        capability_runtime.event_store,
        "record_event",
        lambda *args, **kwargs: None,
    )

    def fake_request_memory(_conn, **kwargs):
        captured["need"] = kwargs["need"]
        captured["event_conversation_id"] = kwargs["conversation_id"]
        captured["before_global_seq"] = kwargs["before_global_seq"]
        captured["recall_profile"] = kwargs["recall_profile"]
        return MemoryPacket(
            memory_request_id=kwargs["memory_request_id"],
            need=kwargs["need"],
            supported=False,
            items=[],
        )

    monkeypatch.setattr(capability_runtime.jit_memory, "request_memory", fake_request_memory)

    capability_runtime.execute_registered_capability(
        object(),
        FakeLLM(),
        registration=DEFAULT_REGISTRY.get(capability_id),
        capability_execution_id=uuid.uuid4(),
        requester_task_id=uuid.uuid4(),
        requester_step_id=uuid.uuid4(),
        round_index=0,
        plan_position=0,
        conversation_id=active_conversation_id,
        correlation_id=uuid.uuid4(),
        task_text="What did I establish previously?",
        before_global_seq=73,
        memory_request_id=memory_request_id,
        candidate_packet=_candidate_packet(candidate_count),
    )

    assert captured["event_conversation_id"] == active_conversation_id
    assert captured["need"].conversation_id is None
    assert captured["need"].include_persisted_history is True
    assert captured["need"].active_event_ids == []
    assert captured["before_global_seq"] == 73
