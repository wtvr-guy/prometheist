from __future__ import annotations

import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.interaction_worker import (
    RESPONSE_POLICY_SOURCE,
    _record_response_policy_event,
)
from jit_agent.models import EventType
from jit_agent.response_policy import (
    RESPONSE_POLICY_VERSION,
    HistoricalEvidenceScope,
    ResponsePolicy,
    ResponseSurfaceMode,
)


def test_response_policy_event_is_canonical_and_causally_linked():
    conversation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    claim_id = uuid.uuid4()
    step_id = uuid.uuid4()
    policy = ResponsePolicy(
        evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
        surface_mode=ResponseSurfaceMode.EXACT_SOURCE_SUBSTRING,
        insufficient_literal="INSUFFICIENT",
    )

    with db.get_connection() as conn:
        event_store.start_conversation(conn, conversation_id)
        event_id = _record_response_policy_event(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            claim_id=claim_id,
            step_id=step_id,
            stage="RESPOND",
            policy=policy,
        )
        events = event_store.get_events_by_conversation(conn, conversation_id)

    persisted = next(event for event in events if event.event_id == event_id)
    assert persisted.event_type is EventType.SYSTEM_EVENT
    assert persisted.source == RESPONSE_POLICY_SOURCE
    assert persisted.correlation_id == correlation_id
    assert persisted.payload == {
        "policy_version": RESPONSE_POLICY_VERSION,
        "claim_id": str(claim_id),
        "step_id": str(step_id),
        "stage": "RESPOND",
        "policy": policy.model_dump(mode="json"),
    }


def test_response_policy_provenance_rejects_non_response_stage():
    policy = ResponsePolicy(
        evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
        surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
        insufficient_literal=None,
    )

    with db.get_connection() as conn:
        with pytest.raises(RuntimeError, match="outside the RESPOND stage"):
            _record_response_policy_event(
                conn,
                conversation_id=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
                claim_id=uuid.uuid4(),
                step_id=uuid.uuid4(),
                stage="APERTURE",
                policy=policy,
            )
