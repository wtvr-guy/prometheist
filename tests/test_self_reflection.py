from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from jit_agent import db, event_store
from jit_agent.cognitive_store import list_records, put_record
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.perception import normalize_user_interaction_percept
from jit_agent.self_memory import (
    FutureOrientation,
    IdentityCentrality,
    PlasticityClass,
    SELF_SUBJECT,
    SelfPerspective,
    SelfRepresentationKind,
    SelfResolutionStatus,
    current_self_resolution,
    default_plasticity,
    resolve_self_representation,
    self_evidence,
)
from jit_agent.self_reflection import (
    ReflectionEvidence,
    SelfReviewVerdict,
    SelfSchemaProposal,
    SelfSchemaReview,
    apply_review,
    collect_consolidation_evidence,
    materialize_proposal,
)
from jit_agent.situations import persist_situations


@pytest.fixture
def conn():
    with db.get_connection() as connection:
        yield connection


def _record_user_prompt(conn, text: str):
    conversation_id = uuid4()
    correlation_id = uuid4()
    event_store.start_conversation(conn, conversation_id)
    event = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": text},
        payload_text=text,
        event_id=uuid4(),
    )
    percept = normalize_user_interaction_percept(
        user_text=text,
        observed_at=event.created_at,
        correlation_id=correlation_id,
        source_event_id=event.event_id,
        conversation_id=conversation_id,
    )
    situations = persist_situations(conn, percept)
    return event, situations


def test_proposal_model_cannot_choose_plasticity():
    assert "plasticity" not in SelfSchemaProposal.model_fields
    assert default_plasticity(SelfRepresentationKind.EMBODIMENT_STATE) is (
        PlasticityClass.FAST
    )
    assert default_plasticity(SelfRepresentationKind.PREFERENCE) is (
        PlasticityClass.MEDIUM
    )
    assert default_plasticity(SelfRepresentationKind.VALUE) is PlasticityClass.SLOW
    assert default_plasticity(SelfRepresentationKind.NARRATIVE_HYPOTHESIS) is (
        PlasticityClass.VERY_SLOW
    )


def test_consolidation_evidence_includes_free_text_roots_and_real_situation_contexts(conn):
    first, _ = _record_user_prompt(conn, "I prefer systems I can inspect.")
    second, _ = _record_user_prompt(conn, "I also choose local control over convenience.")

    rows = list_records(conn, "situation_ingest")
    selected = [
        key
        for key, data in rows
        if str(first.event_id) in data["provenance"]
        or str(second.event_id) in data["provenance"]
    ]
    assert len(selected) == 2

    consolidation_id = uuid4()
    put_record(
        conn,
        "consolidation_input",
        str(consolidation_id),
        {
            "after_key": "",
            "record_keys": selected,
            "derived_at": datetime.now(timezone.utc).isoformat(),
            "next_cursor": selected[-1],
        },
        revision="1",
    )

    evidence = collect_consolidation_evidence(conn, consolidation_id)
    by_id = {item.event_id: item for item in evidence}

    assert first.event_id in by_id
    assert second.event_id in by_id
    assert len(by_id[first.event_id].context_refs) == 1
    assert len(by_id[second.event_id].context_refs) == 1
    assert by_id[first.event_id].context_refs != by_id[second.event_id].context_refs


def test_materialization_uses_application_contexts_for_breadth(conn):
    first, _ = _record_user_prompt(conn, "I chose inspectability over speed.")
    second, _ = _record_user_prompt(conn, "I chose auditability over convenience.")
    evidence = (
        ReflectionEvidence(
            event_id=first.event_id,
            event_type=first.event_type,
            source=first.source,
            created_at=first.created_at.isoformat(),
            content=first.payload["text"],
            context_refs=("situation:first",),
        ),
        ReflectionEvidence(
            event_id=second.event_id,
            event_type=second.event_type,
            source=second.source,
            created_at=second.created_at.isoformat(),
            content=second.payload["text"],
            context_refs=("situation:second",),
        ),
    )
    proposal = SelfSchemaProposal(
        kind=SelfRepresentationKind.VALUE,
        perspective=SelfPerspective.INFERRED,
        statement="Auditability strongly influences important choices.",
        identity_centrality=IdentityCentrality.CENTRAL,
        context_tags=("architecture", "systems"),
        support_indices=(0, 1),
    )

    representation, _ = materialize_proposal(
        conn,
        proposal=proposal,
        evidence=evidence,
        derived_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    resolution = current_self_resolution(conn, representation.representation_id)
    assert resolution is not None
    assert resolution.status is SelfResolutionStatus.CANDIDATE

    established = resolve_self_representation(
        conn,
        representation_id=representation.representation_id,
        requested_status=SelfResolutionStatus.ESTABLISHED,
        identity_centrality=IdentityCentrality.CENTRAL,
        counterevidence_checked=True,
        resolved_at=datetime.now(timezone.utc) + timedelta(minutes=2),
    )

    assert established.status is SelfResolutionStatus.ESTABLISHED
    assert established.metrics.context_count == 2
    assert {
        tag
        for item in self_evidence(conn, representation.representation_id)
        for tag in item.context_tags
    } == {"situation:first", "situation:second"}


def test_invalid_support_index_fails_before_creating_representation(conn):
    root, _ = _record_user_prompt(conn, "I like modular systems.")
    proposal = SelfSchemaProposal(
        kind=SelfRepresentationKind.PREFERENCE,
        perspective=SelfPerspective.AVOWED,
        statement="I like modular systems.",
        identity_centrality=IdentityCentrality.MODERATE,
        support_indices=(1,),
    )
    evidence = (
        ReflectionEvidence(
            event_id=root.event_id,
            event_type=root.event_type,
            source=root.source,
            created_at=root.created_at.isoformat(),
            content=root.payload["text"],
            context_refs=("situation:test",),
        ),
    )

    with pytest.raises(ValueError, match="unavailable support"):
        materialize_proposal(
            conn,
            proposal=proposal,
            evidence=evidence,
            derived_at=datetime.now(timezone.utc),
        )


def test_review_opposition_index_is_application_validated(conn):
    root, _ = _record_user_prompt(conn, "I prefer modular systems.")
    proposal = SelfSchemaProposal(
        kind=SelfRepresentationKind.PREFERENCE,
        perspective=SelfPerspective.AVOWED,
        statement="I prefer modular systems.",
        identity_centrality=IdentityCentrality.MODERATE,
        support_indices=(0,),
    )
    evidence = (
        ReflectionEvidence(
            event_id=root.event_id,
            event_type=root.event_type,
            source=root.source,
            created_at=root.created_at.isoformat(),
            content=root.payload["text"],
            context_refs=("situation:test",),
        ),
    )
    representation, _ = materialize_proposal(
        conn,
        proposal=proposal,
        evidence=evidence,
        derived_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="modular", limit=1),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=root.event_id,
                event_type=root.event_type,
                source=root.source,
                created_at=root.created_at,
                conversation_id=root.conversation_id,
                conversation_seq=root.conversation_seq,
                global_seq=root.global_seq,
                content=root.payload["text"],
            )
        ],
    )
    review = SelfSchemaReview(
        verdict=SelfReviewVerdict.CONTEST,
        opposition_indices=(1,),
        rationale="Contrary evidence was claimed outside the supplied packet.",
    )

    with pytest.raises(ValueError, match="unavailable opposition"):
        apply_review(
            conn,
            representation=representation,
            review=review,
            review_packet=packet,
            resolved_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        )


def test_materialized_self_subject_is_fixed(conn):
    root, _ = _record_user_prompt(conn, "I want to become an AI engineer.")
    proposal = SelfSchemaProposal(
        kind=SelfRepresentationKind.PROSPECTIVE_SELF,
        perspective=SelfPerspective.ASPIRATIONAL,
        statement="I want to become an AI engineer.",
        identity_centrality=IdentityCentrality.CENTRAL,
        future_orientation=FutureOrientation.DESIRED,
        support_indices=(0,),
    )
    evidence = (
        ReflectionEvidence(
            event_id=root.event_id,
            event_type=root.event_type,
            source=root.source,
            created_at=root.created_at.isoformat(),
            content=root.payload["text"],
            context_refs=("situation:career",),
        ),
    )
    representation, _ = materialize_proposal(
        conn,
        proposal=proposal,
        evidence=evidence,
        derived_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )

    assert representation.subject == SELF_SUBJECT
