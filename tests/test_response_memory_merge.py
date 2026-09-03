from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent import percept_response_runtime


def _evidence(label: str, seq: int) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=seq,
        global_seq=seq,
        content=label,
    )


def _packet(*items: MemoryEvidence) -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="memory"),
        supported=bool(items),
        items=list(items),
    )


def test_saturated_adaptive_expansion_cannot_evict_initial_aperture_evidence(monkeypatch):
    monkeypatch.setattr(percept_response_runtime, "_RESPONSE_MEMORY_ITEM_LIMIT", 3)
    base_items = (_evidence("base-a", 1), _evidence("base-b", 2))
    expansion_items = (
        _evidence("expansion-a", 3),
        _evidence("expansion-b", 4),
        _evidence("expansion-c", 5),
    )

    merged = percept_response_runtime._merge_memory_packets(
        uuid4(),
        _packet(*base_items),
        _packet(*expansion_items),
        round_index=0,
    )

    assert [item.source_event_id for item in merged.items[:2]] == [
        item.source_event_id for item in base_items
    ]
    assert merged.items[2].source_event_id == expansion_items[0].source_event_id
