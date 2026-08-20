import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.memory_kernel import CueState
from jit_agent.models import EventType
from jit_agent.postgres_memory_kernel import rebuild, recall_from_postgres, verify


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record(conn, conversation_id, text, *, entities=()):
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test",
        payload={"text": text, "entities": list(entities)},
        payload_text=text,
    )


def test_rebuild_is_idempotent_and_events_remain_authoritative(conn):
    conversation_id = event_store.start_conversation(conn)
    first = _record(conn, conversation_id, "I prefer black coffee.")
    second = _record(conn, conversation_id, "My bicycle is blue.")
    before = [event.model_dump(mode="json") for event in event_store.get_events_by_conversation(conn, conversation_id)]

    first_rebuild = rebuild(conn)
    second_rebuild = rebuild(conn)
    after = [event.model_dump(mode="json") for event in event_store.get_events_by_conversation(conn, conversation_id)]

    assert first_rebuild["projection_digest"] == second_rebuild["projection_digest"]
    assert first_rebuild["source_event_count"] == second_rebuild["source_event_count"]
    assert before == after
    assert verify(conn).valid is True
    assert {first.event_id, second.event_id} == {
        event_store.get_event_by_id(conn, first.event_id).event_id,
        event_store.get_event_by_id(conn, second.event_id).event_id,
    }


def test_postgres_recall_returns_bounded_source_evidence(conn):
    conversation_id = event_store.start_conversation(conn)
    coffee = _record(conn, conversation_id, "I drink black coffee every morning.")
    _record(conn, conversation_id, "I bought a blue bicycle.")
    rebuild(conn)

    packet = recall_from_postgres(
        conn,
        CueState(query_text="What coffee do I drink?", entities=("coffee",), limit=1),
    )

    assert [event.event_id for event in packet.items] == [str(coffee.event_id)]
    assert packet.trace.items[0].selected is True
    assert "LEXICAL_CUE" in packet.trace.items[0].reasons


def test_postgres_candidate_selection_respects_ignored_terms_and_nfkc_entities(conn):
    conversation_id = event_store.start_conversation(conn)
    coffee = _record(conn, conversation_id, "Coffee is black.", entities=("Sarah",))
    _record(conn, conversation_id, "Jordan went for a walk.")
    _record(conn, conversation_id, "Jordan read a book.")
    rebuild(conn)

    packet = recall_from_postgres(
        conn,
        CueState(
            query_text="ＪＯＲＤＡＮ coffee",
            entities=("ＳＡＲＡＨ",),
            ignored_terms=("Jordan",),
            limit=1,
        ),
        candidate_limit=1,
    )

    assert [event.event_id for event in packet.items] == [str(coffee.event_id)]
