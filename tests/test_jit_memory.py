import uuid

import pytest

from jit_agent import db, event_store, jit_memory
from jit_agent.models import EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record_text(conn, conversation_id, text, *, event_type=EventType.USER_PROMPT, source="user"):
    event_store.start_conversation(conn, conversation_id)
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=event_type,
        source=source,
        payload={"text": text},
        payload_text=text,
    )


def test_shared_memory_boundary_projects_new_events_without_manual_rebuild(conn):
    source_conversation = uuid.uuid4()
    request_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()
    source_event = _record_text(
        conn,
        source_conversation,
        f"The codename for Project Oriole is {token}.",
    )
    current_prompt = _record_text(conn, request_conversation, "What is Project Oriole's codename?")

    need = jit_memory.build_memory_need(
        "Project Oriole codename",
        entities=["Project Oriole"],
        conversation_id=request_conversation,
    )
    packet = jit_memory.request_memory(
        conn,
        conversation_id=request_conversation,
        correlation_id=current_prompt.correlation_id,
        requesting_agent="test_agent",
        need=need,
        before_global_seq=current_prompt.global_seq,
    )

    assert packet.supported is True
    assert packet.items[0].source_event_id == source_event.event_id
    assert token in packet.items[0].content

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM memory_projection_entries
            WHERE source_event_id = %s AND projection_name = 'lexical'
            """,
            (source_event.event_id,),
        )
        assert cur.fetchone()[0] == 1


def test_memory_boundary_preserves_unknown_fact_abstention(conn):
    source_conversation = uuid.uuid4()
    request_conversation = uuid.uuid4()
    _record_text(conn, source_conversation, "My vehicle is a red Mazda crossover.")
    current_prompt = _record_text(conn, request_conversation, "Who insures my vehicle?")

    packet = jit_memory.request_memory(
        conn,
        conversation_id=request_conversation,
        correlation_id=current_prompt.correlation_id,
        requesting_agent="test_agent",
        need=jit_memory.build_memory_need("Who insures my vehicle?"),
        before_global_seq=current_prompt.global_seq,
    )

    assert packet.supported is False
    assert packet.items == []


def test_memory_request_and_packet_are_persisted_with_same_request_id(conn):
    conversation_id = uuid.uuid4()
    source_event = _record_text(conn, conversation_id, "Remember the passphrase cobalt raven.")
    current_prompt = _record_text(conn, conversation_id, "What passphrase did I give you?")

    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=current_prompt.correlation_id,
        requesting_agent="primary_agent",
        need=jit_memory.build_memory_need("passphrase cobalt raven"),
        before_global_seq=current_prompt.global_seq,
    )
    assert source_event.event_id in {item.source_event_id for item in packet.items}

    events = event_store.get_events_by_conversation(conn, conversation_id)
    request_event = next(event for event in events if event.event_type == EventType.MEMORY_REQUEST)
    packet_event = next(event for event in events if event.event_type == EventType.MEMORY_PACKET)

    assert request_event.correlation_id == current_prompt.correlation_id
    assert packet_event.correlation_id == current_prompt.correlation_id
    assert request_event.payload["memory_request_id"] == str(packet.memory_request_id)
    assert packet_event.payload["packet"]["memory_request_id"] == str(packet.memory_request_id)
    assert request_event.payload["origin"] == "INTERNAL_MEMORY"


def test_control_plane_memory_events_do_not_become_default_evidence(conn):
    conversation_id = uuid.uuid4()
    source_event = _record_text(conn, conversation_id, "The launch phrase is silver comet.")
    first_prompt = _record_text(conn, conversation_id, "What is the launch phrase?")

    first = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=first_prompt.correlation_id,
        requesting_agent="primary_agent",
        need=jit_memory.build_memory_need("launch phrase silver comet"),
        before_global_seq=first_prompt.global_seq,
    )
    assert source_event.event_id in {item.source_event_id for item in first.items}

    later_prompt = _record_text(conn, conversation_id, "Tell me the launch phrase again.")
    second = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=later_prompt.correlation_id,
        requesting_agent="memory_specialist",
        need=jit_memory.build_memory_need("launch phrase silver comet"),
        before_global_seq=later_prompt.global_seq,
    )

    assert second.items
    assert all(item.event_type not in {EventType.MEMORY_REQUEST, EventType.MEMORY_PACKET} for item in second.items)
