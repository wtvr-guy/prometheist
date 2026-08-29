import uuid

import pytest
from psycopg.types.json import Json

from jit_agent import db, event_store, jit_memory
from jit_agent.adaptive_memory_attention import MemoryUncertainty, RetrievalTelemetry
from jit_agent.adaptive_memory_retrieval import RETRIEVAL_ROLE, request_adaptive_memory
from jit_agent.association_projection import ASSOCIATION_PROJECTION_VERSION
from jit_agent.models import EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record(conn, conversation_id, text):
    event_store.start_conversation(conn, conversation_id)
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="adaptive-retrieval-test",
        payload={"text": text},
        payload_text=text,
    )


def _associate(conn, association_id, source_event_id, target_event_id, *, term_source=None):
    source_kind = "TERM" if term_source is not None else "EVENT"
    source = term_source if term_source is not None else str(source_event_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO memory_association_entries (
                association_id, projection_version, source_kind, source,
                target_kind, target, relationship, strength,
                provenance_event_ids, required_cue_terms
            ) VALUES (%s, %s, %s, %s, 'EVENT', %s, 'TEST_LINK', 1.0, %s, %s)
            """,
            (
                association_id,
                ASSOCIATION_PROJECTION_VERSION,
                source_kind,
                source,
                str(target_event_id),
                Json([str(target_event_id)]),
                Json([]),
            ),
        )
    conn.commit()


def test_adaptive_retrieval_executes_derived_narrow_shallow_policy(conn):
    conversation_id = uuid.uuid4()
    anchor = _record(conn, conversation_id, "Opaque selected anchor.")
    target = _record(conn, conversation_id, "The hidden exact value is VECTOR-71.")
    prompt = _record(conn, conversation_id, "What exact hidden value belongs to this anchor?")
    jit_memory._ensure_projection_fresh(conn, before_global_seq=prompt.global_seq)
    _associate(conn, "adaptive-test-direct", anchor.event_id, target.event_id)

    packet = request_adaptive_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=prompt.correlation_id,
        requesting_component="adaptive-test",
        need=jit_memory.build_memory_need(
            prompt.payload["text"],
            focus_event_ids=[anchor.event_id],
            limit=5,
        ),
        uncertainty=MemoryUncertainty.SPECIFIC_DETAIL_MISSING,
        telemetry=RetrievalTelemetry(candidate_scores=(0.90, 0.10)),
        before_global_seq=prompt.global_seq,
        memory_request_id=uuid.uuid4(),
    )

    assert target.event_id in {item.source_event_id for item in packet.items}
    assert packet.retrieval_trace["retrieval_role"] == RETRIEVAL_ROLE
    assert packet.retrieval_trace["used_focus_event_ids"] == [str(anchor.event_id)]
    policy = packet.retrieval_trace["adaptive_policy"]
    assert policy["scope"] == "NARROW"
    assert policy["association_effort"] == "SHALLOW"
    assert policy["focus_mode"] == "SINGLE_ANCHOR"
    assert policy["candidate_limit"] == 175
    assert policy["max_hops"] == 2
    assert policy["minimum_score"] == 0.15


def test_adaptive_reorientation_drops_anchor_but_keeps_current_semantic_cue(conn):
    conversation_id = uuid.uuid4()
    anchor = _record(conn, conversation_id, "Misleading selected anchor.")
    target = _record(conn, conversation_id, "Opaque correction token is REORIENT-88.")
    prompt = _record(conn, conversation_id, "escape from the misleading focus")
    jit_memory._ensure_projection_fresh(conn, before_global_seq=prompt.global_seq)
    _associate(
        conn,
        "adaptive-test-term-route",
        anchor.event_id,
        target.event_id,
        term_source="escape",
    )

    packet = request_adaptive_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=prompt.correlation_id,
        requesting_component="adaptive-test",
        need=jit_memory.build_memory_need(
            prompt.payload["text"],
            focus_event_ids=[anchor.event_id],
            limit=5,
        ),
        uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
        telemetry=RetrievalTelemetry(
            candidate_scores=(0.90, 0.10),
            anchored_rounds=2,
            support_gain=0.0,
        ),
        before_global_seq=prompt.global_seq,
        memory_request_id=uuid.uuid4(),
    )

    assert target.event_id in {item.source_event_id for item in packet.items}
    assert packet.retrieval_trace["focus_event_ids"] == [str(anchor.event_id)]
    assert packet.retrieval_trace["used_focus_event_ids"] == []
    assert packet.retrieval_trace["adaptive_policy"]["focus_mode"] == "REORIENT"
    assert packet.retrieval_trace["semantic_query_text"] == prompt.payload["text"]


def test_adaptive_retrieval_preserves_global_sequence_leakage_boundary(conn):
    conversation_id = uuid.uuid4()
    anchor = _record(conn, conversation_id, "Historical selected anchor.")
    prompt = _record(conn, conversation_id, "What evidence is associated with this anchor?")
    future = _record(conn, conversation_id, "Future-only evidence must not leak backward.")
    jit_memory._ensure_projection_fresh(conn, before_global_seq=prompt.global_seq)
    _associate(conn, "adaptive-test-future", anchor.event_id, future.event_id)

    packet = request_adaptive_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=prompt.correlation_id,
        requesting_component="adaptive-test",
        need=jit_memory.build_memory_need(
            prompt.payload["text"],
            focus_event_ids=[anchor.event_id],
            limit=5,
        ),
        uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
        telemetry=RetrievalTelemetry(candidate_scores=(1.0,)),
        before_global_seq=prompt.global_seq,
        memory_request_id=uuid.uuid4(),
    )

    assert future.event_id not in {item.source_event_id for item in packet.items}
