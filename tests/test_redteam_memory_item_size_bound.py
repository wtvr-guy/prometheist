from __future__ import annotations

import uuid
from datetime import UTC, datetime

from jit_agent.llm import _format_memory_packet
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


def test_single_oversized_memory_event_cannot_expand_llm_context_without_bound():
    """A bounded item count is not a bounded cognitive context if one item is unbounded.

    The system may truncate, summarize through an explicitly bounded mechanism, or
    fail closed. It must not blindly serialize an arbitrarily large canonical event
    into the next model prompt merely because the MemoryPacket contains only one item.
    """

    huge_content = "OVERSIZED-CANONICAL-EVIDENCE " + ("x" * 2_000_000)
    packet = MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="What does the stored evidence say?", limit=1),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid.uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                created_at=datetime.now(UTC),
                conversation_id=uuid.uuid4(),
                conversation_seq=1,
                global_seq=1,
                content=huge_content,
            )
        ],
    )

    try:
        rendered = _format_memory_packet(packet)
    except (ValueError, RuntimeError):
        return  # Explicit fail-closed handling is acceptable.

    assert huge_content not in rendered, (
        "One oversized canonical event was copied into the model context in full. "
        "MemoryPacket item-count bounds therefore do not bound actual prompt size."
    )
