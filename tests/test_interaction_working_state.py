import uuid

import pytest

from jit_agent import db, event_store, jit_memory
from jit_agent.interaction_working_state import (
    InteractionWorkingState,
    activate_working_state,
    load_working_state,
)
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.response_policy import (
    HistoricalEvidenceScope,
    ResponsePolicy,
    ResponseSurfaceMode,
)


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _event(conn, conversation_id, text):
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": text},
        payload_text=text,
    )


def _memory_evidence(event):
    return MemoryEvidence(
        source_event_id=event.event_id,
        event_type=event.event_type,
        source=event.source,
        created_at=event.created_at,
        conversation_id=event.conversation_id,
        conversation_seq=event.conversation_seq,
        global_seq=event.global_seq,
        content=event.payload["text"],
        score=1.0,
    )


def test_working_state_is_only_bounded_canonical_event_activation(conn):
    conversation_id = event_store.start_conversation(conn, uuid.uuid4())
    first = _event(conn, conversation_id, "first canonical event")
    second = _event(conn, conversation_id, "second canonical event")
    third = _event(conn, conversation_id, "third canonical event")

    state1 = activate_working_state(
        conn,
        interaction_id=uuid.uuid4(),
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        activated_event_ids=[second.event_id, first.event_id],
    )
    assert state1.revision == 1
    assert state1.active_event_ids == [second.event_id, first.event_id]

    state2 = activate_working_state(
        conn,
        interaction_id=uuid.uuid4(),
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        activated_event_ids=[third.event_id, second.event_id],
    )
    assert state2.revision == 2
    assert state2.active_event_ids == [third.event_id, second.event_id, first.event_id]
    assert load_working_state(conn, conversation_id) == state2

    # v0.7 deliberately does not persist parsed labels/options/conclusions here.
    assert set(InteractionWorkingState.model_fields) == {
        "version",
        "state_id",
        "revision",
        "conversation_ids",
        "active_event_ids",
    }


def test_response_activation_preserves_policy_admitted_canonical_support(conn):
    conversation_id = event_store.start_conversation(conn, uuid.uuid4())
    historical_user = _event(
        conn,
        conversation_id,
        "For Project Kestrel, deploy PostgreSQL directly on Windows because virtualization is disabled.",
    )
    current_prompt = _event(conn, conversation_id, "Give me a short Kestrel recap.")
    prior_model = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.INTERACTION_RESPONSE,
        source="test-model",
        payload={"text": "A prior model restatement."},
        payload_text="A prior model restatement.",
    )

    final_packet = MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="Kestrel recap"),
        supported=True,
        items=[_memory_evidence(prior_model), _memory_evidence(historical_user)],
    )
    policy = ResponsePolicy(
        evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
        surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
    )
    workpiece_event = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.SYSTEM_EVENT,
        source="test-finalizer",
        payload={
            "kind": "INTERACTION_WORKPIECE_SNAPSHOT",
            "version": "interaction-workpiece-v1",
            "workpiece": {
                "components": [
                    {
                        "component_type": "FINAL_EVIDENCE",
                        "memory_packet": final_packet.model_dump(mode="json"),
                    },
                    {
                        "component_type": "FINAL_RESPONSE_DIRECTIVE",
                        "directive": {
                            "response_policy": policy.model_dump(mode="json"),
                        },
                    },
                ]
            },
        },
    )
    response_event = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.INTERACTION_RESPONSE,
        source="test-finalizer",
        payload={
            "text": "PostgreSQL directly on Windows.",
            "workpiece_event_id": str(workpiece_event.event_id),
        },
        payload_text="PostgreSQL directly on Windows.",
    )

    state = activate_working_state(
        conn,
        interaction_id=uuid.uuid4(),
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        activated_event_ids=[response_event.event_id, current_prompt.event_id],
    )

    assert state.active_event_ids[:3] == [
        response_event.event_id,
        historical_user.event_id,
        current_prompt.event_id,
    ]
    assert prior_model.event_id not in state.active_event_ids


def test_jit_memory_rehydrates_active_canonical_events_before_lexical_fallback(conn):
    conversation_id = event_store.start_conversation(conn, uuid.uuid4())
    active = _event(
        conn,
        conversation_id,
        "BlueHarbor-ABC123 was the current plan label.",
    )

    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        requesting_component="test-working-state",
        need=jit_memory.build_memory_need(
            "lexically unrelated request",
            active_event_ids=[active.event_id],
        ),
        before_global_seq=None,
    )

    assert packet.supported is True
    assert packet.items[0].source_event_id == active.event_id
    assert packet.items[0].retrieval_reasons == ["ACTIVE_WORKING_STATE"]
    assert packet.retrieval_trace["working_state_event_ids"] == [str(active.event_id)]
