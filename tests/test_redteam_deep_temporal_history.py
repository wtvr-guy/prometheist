from __future__ import annotations

import uuid

import pytest

from jit_agent import db, event_store, postgres_memory_kernel
from jit_agent.jit_memory import ATTENTION_ACTIVATION_CANDIDATE_LIMIT
from jit_agent.memory_kernel import CueState
from jit_agent.models import EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record(conn, conversation_id: uuid.UUID, text: str):
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": text},
        payload_text=text,
    )


def test_original_fact_survives_more_same_topic_updates_than_candidate_window(conn):
    """An explicit original-state question must not silently become newest-only recall.

    Every record deliberately has the same lexical specificity. The only fact that
    makes the target the answer is canonical chronology: it is the first Project
    Falcon launch-code statement. More same-topic records are then appended than the
    production attention candidate window can hold.

    If candidate routing is exclusively newest-first for tied lexical matches, the
    exact old canonical fact becomes unreachable before a model can reason about
    `originally` at all.
    """

    conversation_id = event_store.start_conversation(conn)
    original_code = f"ORIGIN-{uuid.uuid4().hex[:10].upper()}"
    target = _record(
        conn,
        conversation_id,
        f"The launch code for Project Falcon is {original_code}.",
    )

    for index in range(ATTENTION_ACTIVATION_CANDIDATE_LIMIT + 64):
        _record(
            conn,
            conversation_id,
            f"The launch code for Project Falcon is DECOY-{index:04d}.",
        )

    postgres_memory_kernel.rebuild(conn)
    packet = postgres_memory_kernel.recall_from_postgres(
        conn,
        CueState(
            query_text="What launch code did I originally give Project Falcon?",
            source_types=(EventType.USER_PROMPT.value,),
            limit=6,
        ),
        candidate_limit=ATTENTION_ACTIVATION_CANDIDATE_LIMIT,
    )

    assert str(target.event_id) in {event.event_id for event in packet.items}, (
        "The oldest same-topic canonical fact was excluded before ranking because the "
        "bounded candidate router broke lexical ties by newest global sequence only."
    )
