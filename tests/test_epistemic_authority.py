from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from jit_agent.epistemic_authority import (
    authority_for_event_type,
    format_authority_bound_response_memory_packet,
)
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


def _evidence(event_type: EventType, content: str, seq: int) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=event_type,
        source="test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=seq,
        global_seq=seq,
        content=content,
    )


def test_assistant_output_cannot_establish_user_testimony():
    authority = authority_for_event_type(EventType.INTERACTION_RESPONSE)

    assert authority.authority_class == "MODEL_OUTPUT_ONLY"
    assert "what Prometheist or another model previously emitted" in authority.may_establish
    assert "that the user said" in authority.cannot_establish
    assert "preferred" in authority.cannot_establish


def test_user_prompt_is_direct_user_testimony():
    authority = authority_for_event_type(EventType.USER_PROMPT)

    assert authority.authority_class == "DIRECT_USER_TESTIMONY"
    assert "what the user previously said" in authority.may_establish


def test_response_evidence_inventory_does_not_promote_model_output_to_user_testimony():
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Favorite color?"),
        supported=True,
        items=[
            _evidence(
                EventType.INTERACTION_RESPONSE,
                "The user's favorite color is Cerulean-DEADBEEF.",
                1,
            )
        ],
    )

    rendered = format_authority_bound_response_memory_packet(packet)

    assert "direct_user_testimony_orders: none" in rendered
    assert "authority_class: MODEL_OUTPUT_ONLY" in rendered
    assert "MODEL_OUTPUT_ONLY is never a substitute for DIRECT_USER_TESTIMONY" in rendered
    assert "The user's favorite color is Cerulean-DEADBEEF." in rendered


def test_response_evidence_inventory_identifies_user_authored_support_separately():
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Favorite color?"),
        supported=True,
        items=[
            _evidence(EventType.USER_PROMPT, "My favorite color is green.", 1),
            _evidence(
                EventType.INTERACTION_RESPONSE,
                "The user's favorite color is blue.",
                2,
            ),
        ],
    )

    rendered = format_authority_bound_response_memory_packet(packet)

    assert "direct_user_testimony_orders: 0" in rendered
    assert "authority_class: DIRECT_USER_TESTIMONY" in rendered
    assert "authority_class: MODEL_OUTPUT_ONLY" in rendered
