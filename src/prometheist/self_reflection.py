"""Narrow self-reflection contracts over bounded canonical evidence.

Proposal and review are separate semantic responsibilities. The proposer may
suggest typed self representations from canonical evidence. The reviewer sees
the candidate plus independently expanded related evidence and decides whether
the application should attempt to establish, contest, reject, or retain it as a
candidate. Application code resolves all indices to canonical event IDs and owns
the final state transition.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
import json
from uuid import UUID, uuid5

import psycopg
from pydantic import Field, model_validator

from prometheist import event_store, jit_memory
from prometheist.cognitive_store import COGNITIVE_NAMESPACE, get_record
from prometheist.models import EventType, MemoryPacket
from prometheist.percept_context import FrozenRecord, Reference
from prometheist.self_memory import (
    FutureOrientation,
    IdentityCentrality,
    MAX_SELF_CONTEXT_TAGS,
    MAX_SELF_STATEMENT_CHARS,
    SelfEvidenceOrigin,
    SelfEvidenceRelation,
    SelfPerspective,
    SelfRepresentation,
    SelfRepresentationKind,
    SELF_SUBJECT,
    SelfResolution,
    SelfResolutionStatus,
    current_self_resolution,
    default_plasticity,
    ensure_self_representation,
    record_self_evidence,
    resolve_self_representation,
    self_evidence,
    self_evidence_root_allowed,
)
from prometheist.situations import Situation

MAX_REFLECTION_EVIDENCE_ITEMS = 12
MAX_SELF_PROPOSALS_PER_BATCH = 8
MAX_REVIEW_EVIDENCE_ITEMS = 10
MAX_REVIEW_RATIONALE_CHARS = 1024
MAX_REVIEW_FOCUS_ROOTS = 4
MIN_RELATIONAL_REVIEW_ROOTS = 2
SELF_REFLECTION_POLICY = "self-reflection/v1"


class SelfReviewVerdict(str, Enum):
    ESTABLISH = "ESTABLISH"
    CONTEST = "CONTEST"
    REJECT = "REJECT"
    KEEP_CANDIDATE = "KEEP_CANDIDATE"


class ReflectionEvidence(FrozenRecord):
    event_id: UUID
    event_type: EventType
    source: Reference
    created_at: str
    content: str
    context_refs: tuple[Reference, ...] = Field(default=(), max_length=MAX_SELF_CONTEXT_TAGS)


class SelfSchemaProposal(FrozenRecord):
    kind: SelfRepresentationKind
    perspective: SelfPerspective
    statement: str = Field(min_length=1, max_length=MAX_SELF_STATEMENT_CHARS)
    identity_centrality: IdentityCentrality
    context_tags: tuple[Reference, ...] = Field(default=(), max_length=MAX_SELF_CONTEXT_TAGS)
    relationship_ref: Reference | None = None
    future_orientation: FutureOrientation | None = None
    procedure_ref: Reference | None = None
    embodiment_ref: Reference | None = None
    support_indices: tuple[int, ...] = Field(min_length=1, max_length=MAX_REFLECTION_EVIDENCE_ITEMS)

    @model_validator(mode="after")
    def proposal_contract(self) -> "SelfSchemaProposal":
        if len(self.support_indices) != len(set(self.support_indices)):
            raise ValueError("support_indices must not contain duplicates")
        return self


class SelfSchemaProposalBatch(FrozenRecord):
    proposals: tuple[SelfSchemaProposal, ...] = Field(
        default=(),
        max_length=MAX_SELF_PROPOSALS_PER_BATCH,
    )


class SelfSchemaReview(FrozenRecord):
    verdict: SelfReviewVerdict
    opposition_indices: tuple[int, ...] = Field(default=(), max_length=MAX_REVIEW_EVIDENCE_ITEMS)
    rationale: str = Field(min_length=1, max_length=MAX_REVIEW_RATIONALE_CHARS)

    @model_validator(mode="after")
    def review_contract(self) -> "SelfSchemaReview":
        if len(self.opposition_indices) != len(set(self.opposition_indices)):
            raise ValueError("opposition_indices must not contain duplicates")
        if (
            self.verdict is SelfReviewVerdict.CONTEST
            and not self.opposition_indices
        ):
            raise ValueError(
                "CONTEST requires at least one concrete opposition index"
            )
        return self


SELF_SCHEMA_PROPOSAL_PROMPT = """\
You are Prometheist's Self-Schema Proposal Specialist. Your only job is to
propose compact, typed, revisable self representations that are directly
supported by the supplied canonical evidence.

Do not answer a user. Do not execute work. Do not decide whether a proposal is
true enough to establish. Do not invent evidence or event IDs; select only
support_indices from the numbered evidence.

Distinguish these perspectives:
- AVOWED: the person explicitly describes their present/past self.
- OBSERVED: directly observed behavior/state without broad generalization.
- INFERRED: a cautious pattern inferred across evidence.
- ASPIRATIONAL: desired future self, aspiration, or goal identity.
- NORMATIVE: what the person says they should/ought to be or do.
- SOCIAL_ATTRIBUTION: an attributed view of the person from another source.

Never convert an aspiration into a present trait. Never convert one behavior
into a stable trait/value/decision policy. Values should describe principles
that appear to guide tradeoffs, not ordinary likes. Traits and behavioral
tendencies should be context-qualified when evidence is context-dependent.
Narrative hypotheses are interpretations, never canonical facts.

Learning timescale is application-owned. Do not propose or choose a plasticity
class. context_tags describe the semantic scope of the representation; they do
not count as independent evidence or prove cross-context breadth.

identity_centrality means how central the representation appears to the person's
self-organization, not how true it is. Be conservative.
"""

SELF_SCHEMA_REVIEW_PROMPT = """\
You are Prometheist's Self-Schema Review Specialist. Your only job is to review
one proposed self representation against two explicitly separated channels:
(1) canonical support roots already attached to the candidate, and
(2) independently retrieved related/counterevidence.

opposition_indices refer ONLY to the numbered related/counterevidence channel.
Never select a support root as opposition. A merely different topic, different
preference, different context, or absence of corroboration is not contrary
evidence.

Return:
- ESTABLISH only when the candidate remains well supported after considering
  related/disconfirming evidence;
- CONTEST only when one or more related-evidence items materially contradict
  the candidate; include every such item's opposition_index;
- REJECT when the proposed abstraction is not supported by its support roots;
- KEEP_CANDIDATE when support is plausible but too narrow for establishment.

If verdict is CONTEST, opposition_indices must be non-empty. If no material
contrary evidence exists, do not return CONTEST.

Do not explain contradictions away merely to preserve a coherent identity.
Context-specific differences are legitimate, but the application—not you—owns
final promotion and may keep a generalized candidate unestablished. A derived
schema never outranks its canonical evidence.
"""


def _proposal_root_allowed(conn: psycopg.Connection, event) -> bool:
    """Only explicit user evidence or opted-in non-user sensors may seed identity."""

    if event.event_type is EventType.USER_PROMPT:
        return True
    if event.event_type is not EventType.PERCEPT_OBSERVATION:
        return False
    percept = event.payload.get("percept")
    if not isinstance(percept, dict):
        return False
    source = percept.get("source")
    if not isinstance(source, dict):
        return False
    source_id = source.get("source_id")
    if not isinstance(source_id, str):
        return False
    policy = get_record(conn, "source_policy", source_id)
    return bool(policy and policy.get("self_model_evidence") is True)


def _event_observed_at(event) -> datetime:
    """Recover source-observation time without rewriting canonical insertion time."""

    payload = event.payload if isinstance(event.payload, dict) else {}
    percept = payload.get("percept")
    if isinstance(percept, dict):
        value = percept.get("observed_at")
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    fixture = payload.get("benchmark_fixture")
    if isinstance(fixture, dict):
        value = fixture.get("occurred_at")
        if isinstance(value, str):
            return datetime.fromisoformat(value)
    value = payload.get("occurred_at")
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return event.created_at


def _event_content(event) -> str:
    text = event.payload.get("text")
    if isinstance(text, str) and text.strip():
        return text
    return json.dumps(
        event.payload,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def collect_consolidation_evidence(
    conn: psycopg.Connection,
    consolidation_id: UUID,
) -> tuple[ReflectionEvidence, ...]:
    """Recover canonical roots plus application-derived source contexts.

    Context breadth is computed from durable situation identity, never from
    model-proposed context tags. A candidate can describe its semantic scope,
    but it cannot manufacture evidence that it generalized across situations.
    """

    input_data = get_record(conn, "consolidation_input", str(consolidation_id))
    if input_data is None:
        raise KeyError(consolidation_id)

    roots: dict[UUID, tuple[object, set[str]]] = {}
    for key in input_data.get("record_keys", []):
        data = get_record(conn, "situation_ingest", str(key))
        if data is None:
            raise RuntimeError(f"missing frozen situation input: {key}")
        situation = Situation.model_validate(data)
        context_ref = f"situation:{situation.situation_id}"
        root_ids = set(situation.provenance)
        root_ids.update(
            state.source_event_id
            for state in situation.observed_state
            if state.source_event_id is not None
        )
        for root_id in root_ids:
            event = event_store.get_event_by_id(conn, root_id)
            if event is None:
                raise RuntimeError(
                    f"self reflection root event is missing: {root_id}"
                )
            if (
                not self_evidence_root_allowed(event.event_type)
                or not _proposal_root_allowed(conn, event)
            ):
                continue
            stored = roots.setdefault(event.event_id, (event, set()))
            stored[1].add(context_ref)

    values = []
    for event, contexts in roots.values():
        values.append(
            ReflectionEvidence(
                event_id=event.event_id,
                event_type=event.event_type,
                source=event.source,
                created_at=_event_observed_at(event).isoformat(),
                content=_event_content(event),
                context_refs=tuple(sorted(contexts)),
            )
        )
    return tuple(
        sorted(
            values,
            key=lambda item: (
                event_store.get_event_by_id(conn, item.event_id).global_seq,
                str(item.event_id),
            ),
        )
    )


def reflection_batches(
    evidence: tuple[ReflectionEvidence, ...],
) -> tuple[tuple[ReflectionEvidence, ...], ...]:
    return tuple(
        evidence[index : index + MAX_REFLECTION_EVIDENCE_ITEMS]
        for index in range(0, len(evidence), MAX_REFLECTION_EVIDENCE_ITEMS)
    )


def render_reflection_evidence(
    evidence: tuple[ReflectionEvidence, ...],
) -> str:
    blocks = []
    for index, item in enumerate(evidence):
        blocks.append(
            "\n".join(
                (
                    f"evidence_index={index}",
                    f"event_id={item.event_id}",
                    f"event_type={item.event_type.value}",
                    f"source={item.source}",
                    f"created_at={item.created_at}",
                    "context_refs=" + ",".join(item.context_refs),
                    f"content={item.content}",
                )
            )
        )
    return "\n\n".join(blocks)


def materialize_proposal(
    conn: psycopg.Connection,
    *,
    proposal: SelfSchemaProposal,
    evidence: tuple[ReflectionEvidence, ...],
    derived_at,
) -> tuple[SelfRepresentation, SelfResolution]:
    for index in proposal.support_indices:
        if index < 0 or index >= len(evidence):
            raise ValueError("self proposal selected unavailable support evidence")

    representation = ensure_self_representation(
        conn,
        subject=SELF_SUBJECT,
        kind=proposal.kind,
        perspective=proposal.perspective,
        statement=proposal.statement,
        plasticity=default_plasticity(proposal.kind),
        created_at=derived_at,
        context_tags=proposal.context_tags,
        relationship_ref=proposal.relationship_ref,
        future_orientation=proposal.future_orientation,
        procedure_ref=proposal.procedure_ref,
        embodiment_ref=proposal.embodiment_ref,
    )
    for index in proposal.support_indices:
        root = evidence[index]
        record_self_evidence(
            conn,
            representation=representation,
            root_event_id=root.event_id,
            relation=SelfEvidenceRelation.SUPPORTS,
            origin=SelfEvidenceOrigin.DIRECT,
            derivation_method=SELF_REFLECTION_POLICY,
            observed_at=datetime.fromisoformat(root.created_at),
            known_at=event_store.get_event_by_id(conn, root.event_id).created_at,
            context_tags=root.context_refs,
        )
    resolution = resolve_self_representation(
        conn,
        representation_id=representation.representation_id,
        requested_status=SelfResolutionStatus.CANDIDATE,
        identity_centrality=proposal.identity_centrality,
        counterevidence_checked=False,
        resolved_at=derived_at,
    )
    return representation, resolution


def render_candidate_support_evidence(
    conn: psycopg.Connection,
    representation: SelfRepresentation,
) -> str:
    blocks: list[str] = []
    support = [
        item
        for item in self_evidence(conn, representation.representation_id)
        if item.relation is SelfEvidenceRelation.SUPPORTS
    ]
    for index, item in enumerate(
        sorted(support, key=lambda value: (value.observed_at, str(value.root_event_id)))
    ):
        root = event_store.get_event_by_id(conn, item.root_event_id)
        if root is None:
            raise RuntimeError(
                f"self support evidence root is missing: {item.root_event_id}"
            )
        blocks.append(
            "\n".join(
                (
                    f"support_index={index}",
                    f"event_id={root.event_id}",
                    f"event_type={root.event_type.value}",
                    f"source={root.source}",
                    f"observed_at={item.observed_at.isoformat()}",
                    f"content={_event_content(root)}",
                )
            )
        )
    return (
        "[Canonical support roots]\n"
        + ("\n\n".join(blocks) if blocks else "items: []")
    )


def review_memory_packet(
    conn: psycopg.Connection,
    *,
    representation: SelfRepresentation,
    conversation_id: UUID,
    correlation_id: UUID,
    before_global_seq: int,
) -> MemoryPacket:
    support_ids = [
        evidence.root_event_id
        for evidence in self_evidence(conn, representation.representation_id)
        if evidence.relation is SelfEvidenceRelation.SUPPORTS
    ]
    focus = support_ids[:MAX_REVIEW_FOCUS_ROOTS]
    if len(focus) >= MIN_RELATIONAL_REVIEW_ROOTS:
        recall_stage = jit_memory.AdaptiveRecallStage.RELATIONAL
    elif len(focus) == 1:
        recall_stage = jit_memory.AdaptiveRecallStage.FOCUSED
    else:
        recall_stage = jit_memory.AdaptiveRecallStage.BROAD
    need = jit_memory.build_memory_need(
        representation.statement,
        focus_event_ids=focus if recall_stage is not jit_memory.AdaptiveRecallStage.BROAD else [],
        include_persisted_history=True,
        conversation_id=None,
        limit=MAX_REVIEW_EVIDENCE_ITEMS,
        source_types=[
            EventType.USER_PROMPT,
            EventType.TOOL_RESULT,
            EventType.PERCEPT_OBSERVATION,
            EventType.SYSTEM_EVENT,
        ],
    )
    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=(
            f"self-review:{SELF_REFLECTION_POLICY}:"
            f"{representation.representation_id}"
        ),
        need=need,
        before_global_seq=before_global_seq,
        memory_request_id=uuid5(
            COGNITIVE_NAMESPACE,
            (
                f"self-review-memory:{representation.representation_id}:"
                f"{before_global_seq}"
            ),
        ),
        recall_stage=recall_stage,
    )
    support_set = set(support_ids)
    related_items = [
        item for item in packet.items if item.source_event_id not in support_set
    ]
    return packet.model_copy(
        update={
            "items": related_items,
            "supported": bool(related_items),
            "retrieval_trace": {
                **dict(packet.retrieval_trace),
                "self_review_support_roots_excluded": [
                    str(value) for value in support_ids
                ],
            },
        },
        deep=True,
    )


def apply_review(
    conn: psycopg.Connection,
    *,
    representation: SelfRepresentation,
    review: SelfSchemaReview,
    review_packet: MemoryPacket,
    resolved_at,
) -> SelfResolution:
    support_ids = {
        item.root_event_id
        for item in self_evidence(conn, representation.representation_id)
        if item.relation is SelfEvidenceRelation.SUPPORTS
    }
    recorded_opposition_ids: set[UUID] = set()
    for index in review.opposition_indices:
        if index < 0 or index >= len(review_packet.items):
            raise ValueError("self review selected unavailable opposition evidence")
        item = review_packet.items[index]
        if item.source_event_id in support_ids:
            continue
        root = event_store.get_event_by_id(conn, item.source_event_id)
        if root is None:
            raise RuntimeError(
                f"self review evidence root is missing: {item.source_event_id}"
            )
        record_self_evidence(
            conn,
            representation=representation,
            root_event_id=item.source_event_id,
            relation=SelfEvidenceRelation.OPPOSES,
            origin=SelfEvidenceOrigin.DIRECT,
            derivation_method=SELF_REFLECTION_POLICY,
            known_at=root.created_at,
        )
        recorded_opposition_ids.add(item.source_event_id)

    requested_status = {
        SelfReviewVerdict.ESTABLISH: SelfResolutionStatus.ESTABLISHED,
        SelfReviewVerdict.CONTEST: (
            SelfResolutionStatus.CONTESTED
            if recorded_opposition_ids
            else SelfResolutionStatus.CANDIDATE
        ),
        SelfReviewVerdict.REJECT: SelfResolutionStatus.REJECTED,
        SelfReviewVerdict.KEEP_CANDIDATE: SelfResolutionStatus.CANDIDATE,
    }[review.verdict]
    current = current_self_resolution(conn, representation.representation_id)
    if current is None:
        raise RuntimeError("self review candidate has no prior resolution")
    return resolve_self_representation(
        conn,
        representation_id=representation.representation_id,
        requested_status=requested_status,
        identity_centrality=current.identity_centrality,
        counterevidence_checked=True,
        resolved_at=resolved_at,
    )


def proposal_batch_schema() -> dict:
    return SelfSchemaProposalBatch.model_json_schema()


def review_schema() -> dict:
    return SelfSchemaReview.model_json_schema()
