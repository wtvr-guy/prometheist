import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.attention_aperture import (
    ATTENTION_APERTURE_VERSION,
    DEFAULT_ATTENTION_APERTURE_LIMIT,
    open_attention_aperture,
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


def test_every_percept_can_activate_relevant_history_without_model_planning(conn):
    historical_conversation = uuid.uuid4()
    active_conversation = uuid.uuid4()
    historical = _record_prompt(
        conn,
        historical_conversation,
        "For Project Atlas, never use Docker; deploy PostgreSQL directly on Windows "
        "because virtualization is disabled.",
    )
    current = _record_prompt(
        conn,
        active_conversation,
        "I'm revisiting Project Atlas and choosing between Docker Compose and "
        "PostgreSQL directly on Windows.",
    )

    packet = open_attention_aperture(
        conn,
        conversation_id=active_conversation,
        correlation_id=current.correlation_id,
        requester_task_id=uuid.uuid4(),
        user_text=current.payload["text"],
        before_global_seq=current.global_seq,
    )

    assert historical.event_id in {item.source_event_id for item in packet.items}
    assert len(packet.items) <= DEFAULT_ATTENTION_APERTURE_LIMIT
    assert packet.retrieval_trace["retrieval_role"] == "ATTENTION_ACTIVATION"
    assert packet.retrieval_trace["activation_kernel"]["kernel"] == "recall_from_postgres"

    events = event_store.get_events_by_conversation(conn, active_conversation)
    request = next(event for event in events if event.event_type is EventType.MEMORY_REQUEST)
    assert request.payload["retrieval_role"] == "ATTENTION_ACTIVATION"
    assert request.source.startswith(f"attention-aperture:{ATTENTION_APERTURE_VERSION}")


def test_aperture_activation_does_not_require_conversation_scope(conn):
    source_conversation = uuid.uuid4()
    current_conversation = uuid.uuid4()
    source = _record_prompt(
        conn,
        source_conversation,
        "Project Meridian uses the opaque marker MERIDIAN-8421.",
    )
    current = _record_prompt(
        conn,
        current_conversation,
        "What marker belongs to Project Meridian?",
    )

    packet = open_attention_aperture(
        conn,
        conversation_id=current_conversation,
        correlation_id=current.correlation_id,
        requester_task_id=uuid.uuid4(),
        user_text=current.payload["text"],
        before_global_seq=current.global_seq,
    )

    assert source.event_id in {item.source_event_id for item in packet.items}
    assert packet.need.conversation_id is None
