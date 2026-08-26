"""Shared JIT Memory boundary for every stateless Prometheist agent.

Agents express *what* internal persisted information they need through
``MemoryNeed``. This module owns *how* the current verified Memory Kernel is
used, persists request/result provenance, and returns a bounded ``MemoryPacket``.
No caller needs to know about candidate routing, lexical projections,
associations, PostgreSQL FTS, or future retrieval mechanisms.
"""
from __future__ import annotations

from dataclasses import asdict
import uuid

import psycopg
from psycopg.types.json import Json

from jit_agent import event_store, postgres_memory_kernel
from jit_agent.association_projection import ASSOCIATION_PROJECTION_VERSION, derive_associations
from jit_agent.memory_kernel import CueState
from jit_agent.memory_projection import LexicalProjection, build_projection
from jit_agent.models import (
    EventType,
    KnowledgeOrigin,
    MemoryEvidence,
    MemoryNeed,
    MemoryPacket,
)

SOURCE = "jit_memory"
CANDIDATE_LIMIT = 500
ASSOCIATION_LIMIT = 250
MAX_HOPS = 2
ASSOCIATION_DECAY = 0.85
MINIMUM_SCORE = 0.15

# Control-plane events are intentionally excluded by default. Memory packets,
# memory requests, decisions, delegations, and errors should not recursively
# become evidence merely because they mention the same words as a later query.
DEFAULT_EVIDENCE_TYPES = (
    EventType.USER_PROMPT,
    EventType.AGENT_RESPONSE,
    EventType.AGENT_RESULT,
    EventType.TOOL_RESULT,
    EventType.SYSTEM_EVENT,
)


def build_memory_need(
    query_text: str | None,
    *,
    supplemental_query_texts: list[str] | None = None,
    entities: list[str] | None = None,
    conversation_id: uuid.UUID | None = None,
    limit: int = 5,
) -> MemoryNeed:
    """Application policy for a normal internal-memory request."""
    return MemoryNeed(
        query_text=query_text,
        supplemental_query_texts=supplemental_query_texts or [],
        entities=entities or [],
        conversation_id=conversation_id,
        source_types=list(DEFAULT_EVIDENCE_TYPES),
        limit=limit,
    )


def _effective_source_types(need: MemoryNeed) -> tuple[EventType, ...]:
    return tuple(need.source_types) if need.source_types else DEFAULT_EVIDENCE_TYPES


def _query_variants(need: MemoryNeed) -> tuple[tuple[str, str | None], ...]:
    """Return deterministic canonical-then-fallback query formulations.

    The canonical query always gets first refusal. Supplemental formulations are
    only useful if the canonical kernel pass produces no admissible evidence.
    Duplicate/blank formulations are removed without changing the persisted
    ``MemoryNeed`` itself, so request provenance remains exact.
    """
    variants: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    def add(role: str, value: str | None) -> None:
        if value is None or not value.strip():
            return
        key = " ".join(value.split()).casefold()
        if key in seen:
            return
        seen.add(key)
        variants.append((role, value))

    add("canonical", need.query_text)
    for value in need.supplemental_query_texts:
        add("supplemental", value)

    if not variants:
        variants.append(("canonical", None))
    return tuple(variants)


def _ensure_projection_fresh(
    conn: psycopg.Connection,
    *,
    before_global_seq: int | None,
) -> None:
    """Incrementally make the v0.5 derived routes usable by the live MAS.

    v0.5 benchmark setup explicitly rebuilt projections before recall. The live
    event store, correctly, only appends authoritative events. v0.6 therefore
    needs a bridge that projects newly visible events without rewriting history
    or forcing a destructive full rebuild on each memory request.

    Lexical rows are genuinely incremental. Association derivation is computed
    from the visible append-only history and inserted idempotently; v0.5's rule
    families only add relationships as new events arrive, so previously derived
    association rows remain valid. This keeps the frozen kernel untouched.
    """
    events = postgres_memory_kernel.load_events(conn, before_global_seq=before_global_seq)
    if not events:
        return

    projection = LexicalProjection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_event_id
            FROM memory_projection_entries
            WHERE projection_name = %s AND projection_version = %s
            """,
            (projection.name, projection.version),
        )
        projected_ids = {str(row[0]) for row in cur.fetchall()}

    missing_events = [event for event in events if event.event_id not in projected_ids]
    if not missing_events:
        return

    entries = build_projection(missing_events, projection)
    associations = derive_associations(events)

    with conn.cursor() as cur:
        if entries:
            cur.executemany(
                """
                INSERT INTO memory_projection_entries (
                    projection_name, projection_version, source_event_id,
                    source_global_seq, source_hash, data
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (projection_name, projection_version, source_event_id)
                DO NOTHING
                """,
                [
                    (
                        entry.projection_name,
                        entry.projection_version,
                        uuid.UUID(entry.source_event_id),
                        entry.source_global_seq,
                        entry.source_hash,
                        Json(dict(entry.data)),
                    )
                    for entry in entries
                ],
            )

        if associations:
            cur.executemany(
                """
                INSERT INTO memory_association_entries (
                    association_id, projection_version, source_kind, source,
                    target_kind, target, relationship, strength,
                    provenance_event_ids, required_cue_terms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (association_id) DO NOTHING
                """,
                [
                    (
                        association.association_id,
                        ASSOCIATION_PROJECTION_VERSION,
                        association.source_kind,
                        association.source,
                        association.target_kind,
                        association.target,
                        association.relationship,
                        association.strength,
                        Json(list(association.provenance_event_ids)),
                        Json(list(association.required_cue_terms)),
                    )
                    for association in associations
                ],
            )
    conn.commit()


def _packet_from_kernel(
    memory_request_id: uuid.UUID,
    need: MemoryNeed,
    kernel_packet,
) -> MemoryPacket:
    trace_by_id = {item.event_id: item for item in kernel_packet.trace.items}
    evidence: list[MemoryEvidence] = []

    for event in kernel_packet.items:
        trace_item = trace_by_id.get(event.event_id)
        reasons: list[str] = []
        provenance: set[uuid.UUID] = set()
        score: float | None = None

        if trace_item is not None:
            score = float(trace_item.total_score)
            if trace_item.baseline_score > 0:
                reasons.append("DIRECT_CUE")
            if trace_item.associative_activation > 0:
                reasons.append("ASSOCIATIVE_ROUTE")
            for hop in trace_item.association_hops:
                for event_id in hop.provenance_event_ids:
                    try:
                        provenance.add(uuid.UUID(event_id))
                    except (ValueError, TypeError):
                        continue

        evidence.append(
            MemoryEvidence(
                source_event_id=uuid.UUID(event.event_id),
                event_type=EventType(event.event_type),
                source=event.source,
                created_at=event.created_at,
                conversation_id=uuid.UUID(event.conversation_id),
                conversation_seq=event.conversation_seq,
                global_seq=event.global_seq,
                content=event.text,
                score=score,
                retrieval_reasons=reasons,
                provenance_event_ids=sorted(provenance, key=str),
            )
        )

    return MemoryPacket(
        memory_request_id=memory_request_id,
        need=need,
        supported=bool(evidence),
        items=evidence,
        retrieval_trace={
            "kernel": "associative_recall_from_postgres",
            "kernel_trace": asdict(kernel_packet.trace),
        },
    )


def _recall_for_query(
    conn: psycopg.Connection,
    *,
    need: MemoryNeed,
    query_text: str | None,
    before_global_seq: int | None,
):
    cue = CueState(
        query_text=query_text,
        entities=tuple(need.entities),
        reference_time=need.reference_time,
        conversation_id=str(need.conversation_id) if need.conversation_id else None,
        source_types=tuple(item.value for item in _effective_source_types(need)),
        limit=need.limit,
        minimum_score=MINIMUM_SCORE,
    )
    return postgres_memory_kernel.associative_recall_from_postgres(
        conn,
        cue,
        before_global_seq=before_global_seq,
        candidate_limit=CANDIDATE_LIMIT,
        association_limit=ASSOCIATION_LIMIT,
        max_hops=MAX_HOPS,
        decay=ASSOCIATION_DECAY,
    )


def request_memory(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_agent: str,
    need: MemoryNeed,
    before_global_seq: int | None,
    memory_request_id: uuid.UUID | None = None,
) -> MemoryPacket:
    """Persist and satisfy one internal-memory request for any agent.

    The exact canonical query is evaluated first. Only an empty admissible result
    permits a bounded supplemental formulation to be tried. This keeps the
    verified v0.5 kernel unchanged while preventing either a verbose user query
    or a lossy LLM compression from becoming a single point of recall failure.
    """
    memory_request_id = memory_request_id or uuid.uuid4()
    effective_need = need.model_copy(update={"source_types": list(_effective_source_types(need))})

    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.MEMORY_REQUEST,
        source=requesting_agent,
        payload={
            "memory_request_id": str(memory_request_id),
            "origin": KnowledgeOrigin.INTERNAL_MEMORY.value,
            "need": effective_need.model_dump(mode="json"),
        },
        payload_text=effective_need.query_text,
        event_id=uuid.uuid5(memory_request_id, "memory-request-event"),
    )

    _ensure_projection_fresh(conn, before_global_seq=before_global_seq)

    attempts: list[dict[str, object]] = []
    selected_kernel_packet = None
    selected_role: str | None = None
    selected_query_text: str | None = None

    for role, query_text in _query_variants(effective_need):
        kernel_packet = _recall_for_query(
            conn,
            need=effective_need,
            query_text=query_text,
            before_global_seq=before_global_seq,
        )
        attempts.append(
            {
                "role": role,
                "query_text": query_text,
                "supported": bool(kernel_packet.items),
                "kernel_trace": asdict(kernel_packet.trace),
            }
        )
        if selected_kernel_packet is None:
            selected_kernel_packet = kernel_packet
        if kernel_packet.items:
            selected_kernel_packet = kernel_packet
            selected_role = role
            selected_query_text = query_text
            break

    assert selected_kernel_packet is not None
    packet = _packet_from_kernel(memory_request_id, effective_need, selected_kernel_packet)
    packet = packet.model_copy(
        update={
            "retrieval_trace": {
                "kernel": "associative_recall_from_postgres",
                "query_strategy": "canonical_then_supplemental_on_empty",
                "selected_query_role": selected_role,
                "selected_query_text": selected_query_text,
                "query_attempts": attempts,
            }
        }
    )

    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.MEMORY_PACKET,
        source=SOURCE,
        payload={
            "requesting_agent": requesting_agent,
            "packet": packet.model_dump(mode="json"),
        },
        event_id=uuid.uuid5(memory_request_id, "memory-packet-event"),
    )
    return packet
