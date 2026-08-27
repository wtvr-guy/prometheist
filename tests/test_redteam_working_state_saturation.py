from __future__ import annotations

import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.attention_aperture import open_attention_aperture
from jit_agent.interaction_policy import (
    deterministic_interaction_event_id,
    deterministic_interaction_id,
)
from jit_agent.interaction_working_state import (
    MAX_ACTIVE_EVENT_IDS,
    activate_working_state,
    load_working_state,
)
from jit_agent.models import EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record_prompt(conn, conversation_id: uuid.UUID, text: str):
    event_store.start_conversation(conn, conversation_id)
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": text},
        payload_text=text,
    )


def test_newly_relevant_recall_can_enter_saturated_working_state(conn):
    """A full stale WorkingState must not lock newly relevant evidence out of focus.

    Red-team scenario:
    1. Saturate WorkingState with unrelated but valid canonical events.
    2. Switch topics to a historically stored fact that the aperture successfully recalls.
    3. Require that recalled fact to become active so a following anaphoric turn can use it.

    If the fact is visible for the current turn but discarded during activation, the
    system has a one-turn continuity hole: the response may be correct now while the
    next fresh worker loses the evidence that just mattered.
    """

    historical_conversation = uuid.uuid4()
    active_conversation = uuid.uuid4()

    target = _record_prompt(
        conn,
        historical_conversation,
        "For Project Meridian, deployment must use PostgreSQL directly on Windows "
        "because virtualization is disabled.",
    )

    stale = [
        _record_prompt(
            conn,
            active_conversation,
            f"Legacy focus item {index}: bakery inventory marker {uuid.uuid4().hex[:8]}",
        )
        for index in range(MAX_ACTIVE_EVENT_IDS)
    ]
    activate_working_state(
        conn,
        interaction_id=uuid.uuid4(),
        conversation_id=active_conversation,
        correlation_id=uuid.uuid4(),
        activated_event_ids=[event.event_id for event in stale],
        activation_key="redteam-saturated-state",
    )

    correlation_id = uuid.uuid4()
    interaction_id = deterministic_interaction_id(active_conversation, correlation_id)
    prompt_event_id = deterministic_interaction_event_id(interaction_id, "user-prompt")
    current = event_store.record_event(
        conn,
        conversation_id=active_conversation,
        correlation_id=correlation_id,
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={
            "text": "I'm switching to Project Meridian. What deployment constraint applies?"
        },
        payload_text="I'm switching to Project Meridian. What deployment constraint applies?",
        event_id=prompt_event_id,
    )

    packet = open_attention_aperture(
        conn,
        conversation_id=active_conversation,
        correlation_id=correlation_id,
        requester_task_id=uuid.uuid4(),
        user_text=current.payload["text"],
        before_global_seq=current.global_seq,
    )

    packet_ids = {item.source_event_id for item in packet.items}
    assert target.event_id in packet_ids, (
        "Red-team setup failed: the target historical fact was not recalled, so this "
        "test did not reach the WorkingState saturation condition."
    )

    state = load_working_state(conn, active_conversation)
    assert state is not None
    assert state.active_event_ids[0] == prompt_event_id
    assert target.event_id in state.active_event_ids, (
        "A newly relevant fact was recalled into the attention aperture but was then "
        "discarded while saturated WorkingState preserved older stale activations. "
        "That creates a continuity hole for the next stateless worker."
    )
