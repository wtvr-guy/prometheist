from __future__ import annotations

import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.attention_aperture import open_attention_aperture
from jit_agent.models import EventType


RT04_QUERY = "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT."


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def test_assistant_only_claim_reaches_production_attention_aperture(conn):
    hallucination_conversation = event_store.start_conversation(conn, uuid.uuid4())
    question_conversation = event_store.start_conversation(conn, uuid.uuid4())
    fake_color = f"Cerulean-{uuid.uuid4().hex[:8].upper()}"
    hallucinated = event_store.record_event(
        conn,
        conversation_id=hallucination_conversation,
        correlation_id=uuid.uuid4(),
        event_type=EventType.INTERACTION_RESPONSE,
        source="redteam-seeded-assistant-response",
        payload={"text": f"The user's favorite color is {fake_color}."},
        payload_text=f"The user's favorite color is {fake_color}.",
    )
    correlation_id = uuid.uuid4()
    current = event_store.record_event(
        conn,
        conversation_id=question_conversation,
        correlation_id=correlation_id,
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": RT04_QUERY},
        payload_text=RT04_QUERY,
    )
    packet = open_attention_aperture(
        conn,
        conversation_id=question_conversation,
        correlation_id=correlation_id,
        requester_task_id=uuid.uuid4(),
        user_text=RT04_QUERY,
        before_global_seq=current.global_seq,
    )
    assert hallucinated.event_id in {item.source_event_id for item in packet.items}
