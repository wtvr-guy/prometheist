"""Shared JIT Memory boundaries for stateless Prometheist cognition.

``request_attention_activation`` is the shallow, high-recall activation boundary
used automatically for every percept. ``request_memory`` is the conservative
evidence boundary used by explicit research capabilities.

Focused research never asks a model to write a query. A model may select prior
MemoryPacket candidates by bounded index; Prometheist resolves those indices to
canonical event IDs and uses those events as first-class deterministic
association seeds. The current percept remains the semantic cue throughout the
research loop. As focus narrows, direct-candidate breadth decreases while the
bounded association neighborhood becomes deeper/wider.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import uuid

import psycopg
from psycopg.types.json import Json

from jit_agent import event_store, postgres_memory_kernel
from jit_agent.association_projection import ASSOCIATION_PROJECTION_VERSION, derive_associations
from jit_agent.memory_kernel import CueState
from jit_agent.memory_projection import LexicalProjection, build_projection
from jit_agent.models import EventType, KnowledgeOrigin, MemoryEvidence, MemoryNeed, MemoryPacket

SOURCE = "jit_memory"
CANDIDATE_LIMIT = 500
ATTENTION_ACTIVATION_CANDIDATE_LIMIT = 750
ASSOCIATION_LIMIT = 250
MAX_HOPS = 2
ASSOCIATION_DECAY = 0.85
MINIMUM_SCORE = 0.15


class MemoryRecallProfile(str, Enum):
    STANDARD = "STANDARD"
    DEEPER_RESEARCH = "DEEPER_RESEARCH"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    FOCUSED_RECALL = "FOCUSED_RECALL"


@dataclass(frozen=True, slots=True)
class _RecallPolicy:
    candidate_limit: int
    association_limit: int
    max_hops: int
    decay: float


_RECALL_POLICIES = {
    MemoryRecallProfile.STANDARD: _RecallPolicy(
        candidate_limit=CANDIDATE_LIMIT,
        association_limit=ASSOCIATION_LIMIT,
        max_hops=MAX_HOPS,
        decay=ASSOCIATION_DECAY,
    ),
    MemoryRecallProfile.DEEPER_RESEARCH: _RecallPolicy(
        candidate_limit=350,
        association_limit=600,
        max_hops=3,
        decay=0.88,
    ),
    MemoryRecallProfile.CROSS_REFERENCE: _RecallPolicy(
        candidate_limit=250,
        association_limit=900,
        max_hops=4,
        decay=0.90,
    ),
    MemoryRecallProfile.FOCUSED_RECALL: _RecallPolicy(
        candidate_limit=150,
        association_limit=1200,
        max_hops=5,
        decay=0.92,
    ),
}

DEFAULT_EVIDENCE_TYPES = (
    EventType.USER_PROMPT,
    EventType.INTERACTION_RESPONSE,
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
    active_event_ids: list[uuid.UUID] | None = None,
    focus_event_ids: list[uuid.UUID] | None = None,
    include_persisted_history: bool = True,
    reference_time: datetime | None = None,
    conversation_id: uuid.UUID | None = None,
    limit: int = 5,
) -> MemoryNeed:
    return MemoryNeed(
        query_text=query_text,
        supplemental_query_texts=supplemental_query_texts or [],
        entities=entities or [],
        active_event_ids=active_event_ids or [],
        focus_event_ids=focus_event_ids or [],
        include_persisted_history=include_persisted_history,
        reference_time=reference_time,
        conversation_id=conversation_id,
        source_types=list(DEFAULT_EVIDENCE_TYPES),
        limit=limit,
    )


def _effective_source_types(need: MemoryNeed) -> tuple[EventType, ...]:
    return tuple(need.source_types) if need.source_types else DEFAULT_EVIDENCE_TYPES


def _query_variants(need: MemoryNeed) -> tuple[tuple[str, str | None], ...]:
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


def _ensure_projection_fresh(conn: psycopg.Connection, *, before_global_seq: int | None) -> None:
    events = postgres_memory_kernel.load_events(conn, before_global_seq=before_global_seq)
    if not events:
        return
    projection = LexicalProjection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_event_id FROM memory_projection_entries WHERE projection_name = %s AND projection_version = %s",
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
                ON CONFLICT (projection_name, projection_version, source_event_id) DO NOTHING
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


def _packet_from_kernel(memory_request_id: uuid.UUID, need: MemoryNeed, kernel_packet) -> MemoryPacket:
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


def _packet_from_activation_kernel(
    memory_request_id: uuid.UUID,
    need: MemoryNeed,
    kernel_packet,
) -> MemoryPacket:
    trace_by_id = {item.event_id: item for item in kernel_packet.trace.items}
    items: list[MemoryEvidence] = []
    for event in kernel_packet.items:
        trace_item = trace_by_id.get(event.event_id)
        score = float(trace_item.score.total) if trace_item is not None else None
        reasons = ["ATTENTION_APERTURE"]
        if trace_item is not None:
            reasons.extend(trace_item.reasons)
        items.append(
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
                provenance_event_ids=[],
            )
        )
    return MemoryPacket(
        memory_request_id=memory_request_id,
        need=need,
        supported=bool(items),
        items=items,
        retrieval_trace={
            "kernel": "recall_from_postgres",
            "retrieval_role": "ATTENTION_ACTIVATION",
            "kernel_trace": asdict(kernel_packet.trace),
        },
    )


def _active_working_state_evidence(
    conn: psycopg.Connection,
    need: MemoryNeed,
    *,
    before_global_seq: int | None,
    max_items: int | None,
) -> list[MemoryEvidence]:
    allowed_types = set(_effective_source_types(need))
    evidence: list[MemoryEvidence] = []
    for event_id in need.active_event_ids:
        event = event_store.get_event_by_id(conn, event_id)
        if event is None:
            continue
        if before_global_seq is not None and event.global_seq >= before_global_seq:
            continue
        if allowed_types and event.event_type not in allowed_types:
            continue
        text = event.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        evidence.append(
            MemoryEvidence(
                source_event_id=event.event_id,
                event_type=event.event_type,
                source=event.source,
                created_at=event.created_at,
                conversation_id=event.conversation_id,
                conversation_seq=event.conversation_seq,
                global_seq=event.global_seq,
                content=text,
                score=1.0,
                retrieval_reasons=["ACTIVE_WORKING_STATE"],
                provenance_event_ids=[],
            )
        )
        if max_items is not None and len(evidence) == max_items:
            break
    return evidence


def _focus_source_events(
    conn: psycopg.Connection,
    need: MemoryNeed,
    *,
    before_global_seq: int | None,
) -> list[tuple[uuid.UUID, str]]:
    """Rehydrate model-selected canonical candidates for deterministic focusing."""

    allowed_types = set(_effective_source_types(need))
    focused: list[tuple[uuid.UUID, str]] = []
    for event_id in need.focus_event_ids:
        event = event_store.get_event_by_id(conn, event_id)
        if event is None:
            raise RuntimeError("focused memory candidate no longer exists")
        if before_global_seq is not None and event.global_seq >= before_global_seq:
            raise RuntimeError("focused memory candidate crosses the leakage boundary")
        if allowed_types and event.event_type not in allowed_types:
            raise RuntimeError("focused memory candidate has a disallowed source type")
        text = event.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("focused memory candidate has no canonical text")
        focused.append((event_id, " ".join(text.split())))
    return focused


def _recall_for_query(
    conn: psycopg.Connection,
    *,
    need: MemoryNeed,
    query_text: str | None,
    before_global_seq: int | None,
    recall_profile: MemoryRecallProfile,
    seed_event_ids: tuple[uuid.UUID, ...] = (),
):
    policy = _RECALL_POLICIES[recall_profile]
    recall_limit = min(20, need.limit + len(need.active_event_ids))
    cue = CueState(
        query_text=query_text,
        entities=tuple(need.entities),
        reference_time=need.reference_time,
        conversation_id=str(need.conversation_id) if need.conversation_id else None,
        source_types=tuple(item.value for item in _effective_source_types(need)),
        limit=recall_limit,
        minimum_score=MINIMUM_SCORE,
    )
    return postgres_memory_kernel.associative_recall_from_postgres(
        conn,
        cue,
        before_global_seq=before_global_seq,
        candidate_limit=policy.candidate_limit,
        association_limit=policy.association_limit,
        max_hops=policy.max_hops,
        decay=policy.decay,
        seed_event_ids=tuple(str(value) for value in seed_event_ids),
    )


def _activation_recall(
    conn: psycopg.Connection,
    *,
    need: MemoryNeed,
    before_global_seq: int | None,
):
    recall_limit = min(20, need.limit + len(need.active_event_ids))
    cue = CueState(
        query_text=need.query_text,
        entities=tuple(need.entities),
        reference_time=need.reference_time,
        conversation_id=str(need.conversation_id) if need.conversation_id else None,
        source_types=tuple(item.value for item in _effective_source_types(need)),
        limit=recall_limit,
        minimum_score=MINIMUM_SCORE,
    )
    return postgres_memory_kernel.recall_from_postgres(
        conn,
        cue,
        before_global_seq=before_global_seq,
        candidate_limit=ATTENTION_ACTIVATION_CANDIDATE_LIMIT,
    )


def _compose_evidence(
    active: list[MemoryEvidence],
    historical: list[MemoryEvidence],
    *,
    limit: int,
) -> list[MemoryEvidence]:
    if not active:
        return historical[:limit]
    if not historical:
        return active[:limit]

    history_budget = max(1, (limit + 1) // 2)
    active_budget = max(1, limit - history_budget)
    merged: list[MemoryEvidence] = []
    seen: set[uuid.UUID] = set()

    def append(items: list[MemoryEvidence], count: int) -> None:
        added = 0
        for item in items:
            if item.source_event_id in seen:
                continue
            seen.add(item.source_event_id)
            merged.append(item)
            added += 1
            if added == count or len(merged) == limit:
                break

    append(historical, history_budget)
    append(active, active_budget)
    if len(merged) < limit:
        append(historical, limit - len(merged))
    if len(merged) < limit:
        append(active, limit - len(merged))
    return merged[:limit]


def _compose_attention_activation(
    active: list[MemoryEvidence],
    historical: list[MemoryEvidence],
    *,
    recalled_limit: int,
) -> list[MemoryEvidence]:
    """Guarantee bounded active state, then add bounded baseline recall."""

    merged: list[MemoryEvidence] = []
    seen: set[uuid.UUID] = set()
    for item in active:
        if item.source_event_id in seen:
            continue
        seen.add(item.source_event_id)
        merged.append(item)

    recalled = 0
    for item in historical:
        if item.source_event_id in seen:
            continue
        seen.add(item.source_event_id)
        merged.append(item)
        recalled += 1
        if recalled == recalled_limit:
            break
    return merged


def _merge_historical_packets(
    packets: list[MemoryPacket],
    *,
    excluded_event_ids: set[uuid.UUID],
    limit: int,
) -> list[MemoryEvidence]:
    merged: list[MemoryEvidence] = []
    seen = set(excluded_event_ids)
    for packet in packets:
        for item in packet.items:
            if item.source_event_id in seen:
                continue
            seen.add(item.source_event_id)
            merged.append(item.model_copy(deep=True))
            if len(merged) == limit:
                return merged
    return merged


def _persist_packet(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_component: str,
    memory_request_id: uuid.UUID,
    packet: MemoryPacket,
) -> None:
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.MEMORY_PACKET,
        source=SOURCE,
        payload={"requesting_component": requesting_component, "packet": packet.model_dump(mode="json")},
        event_id=uuid.uuid5(memory_request_id, "memory-packet-event"),
    )


def _persist_request(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_component: str,
    memory_request_id: uuid.UUID,
    need: MemoryNeed,
    retrieval_role: str,
) -> None:
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.MEMORY_REQUEST,
        source=requesting_component,
        payload={
            "memory_request_id": str(memory_request_id),
            "origin": KnowledgeOrigin.INTERNAL_MEMORY.value,
            "retrieval_role": retrieval_role,
            "need": need.model_dump(mode="json"),
        },
        payload_text=need.query_text,
        event_id=uuid.uuid5(memory_request_id, "memory-request-event"),
    )


def request_attention_activation(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_component: str,
    need: MemoryNeed,
    before_global_seq: int | None,
    memory_request_id: uuid.UUID | None = None,
) -> MemoryPacket:
    """Return shallow, high-recall activation for every percept.

    All valid application-bounded WorkingState evidence is guaranteed exposure.
    ``need.limit`` bounds only additional baseline recall beyond that active state.
    No association expansion occurs at this level; association depth is reserved
    for explicit research.
    """

    memory_request_id = memory_request_id or uuid.uuid4()
    effective_need = need.model_copy(update={"source_types": list(_effective_source_types(need))})
    _persist_request(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=requesting_component,
        memory_request_id=memory_request_id,
        need=effective_need,
        retrieval_role="ATTENTION_ACTIVATION",
    )
    active_evidence = _active_working_state_evidence(
        conn,
        effective_need,
        before_global_seq=before_global_seq,
        max_items=None,
    )
    historical: list[MemoryEvidence] = []
    kernel_trace: dict[str, object] | None = None
    if effective_need.include_persisted_history:
        _ensure_projection_fresh(conn, before_global_seq=before_global_seq)
        kernel_packet = _activation_recall(
            conn,
            need=effective_need,
            before_global_seq=before_global_seq,
        )
        kernel_result = _packet_from_activation_kernel(
            memory_request_id,
            effective_need,
            kernel_packet,
        )
        active_ids = {item.source_event_id for item in active_evidence}
        historical = [
            item for item in kernel_result.items if item.source_event_id not in active_ids
        ]
        kernel_trace = kernel_result.retrieval_trace

    merged = _compose_attention_activation(
        active_evidence,
        historical,
        recalled_limit=effective_need.limit,
    )
    packet = MemoryPacket(
        memory_request_id=memory_request_id,
        need=effective_need,
        supported=bool(merged),
        items=merged,
        retrieval_trace={
            "retrieval_role": "ATTENTION_ACTIVATION",
            "depth": "BROAD_SHALLOW",
            "candidate_limit": ATTENTION_ACTIVATION_CANDIDATE_LIMIT,
            "association_hops": 0,
            "query_strategy": "working_state_plus_baseline_activation",
            "working_state_event_ids": [str(item.source_event_id) for item in active_evidence],
            "working_state_item_count": len(active_evidence),
            "baseline_recall_limit": effective_need.limit,
            "packet_item_limit": len(active_evidence) + effective_need.limit,
            "activation_kernel": kernel_trace,
        },
    )
    _persist_packet(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=requesting_component,
        memory_request_id=memory_request_id,
        packet=packet,
    )
    return packet


def request_memory(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_component: str,
    need: MemoryNeed,
    before_global_seq: int | None,
    memory_request_id: uuid.UUID | None = None,
    recall_profile: MemoryRecallProfile = MemoryRecallProfile.STANDARD,
) -> MemoryPacket:
    """Persist and satisfy one conservative evidence request.

    Research profiles require application-resolved ``focus_event_ids`` selected
    from a prior MemoryPacket. ``DEEPER_RESEARCH`` expands each selected candidate
    with a moderate graph budget. ``CROSS_REFERENCE`` investigates 2-4 selected
    candidates jointly with a larger graph budget. ``FOCUSED_RECALL`` expands
    exactly one candidate with the deepest bounded graph budget. The current
    percept supplies semantic/relationship cues while selected canonical events
    supply the focused association frontier. The evidence admission threshold
    remains unchanged across all profiles.
    """

    memory_request_id = memory_request_id or uuid.uuid4()
    effective_need = need.model_copy(update={"source_types": list(_effective_source_types(need))})
    if recall_profile is MemoryRecallProfile.DEEPER_RESEARCH and not effective_need.focus_event_ids:
        raise ValueError("DEEPER_RESEARCH requires selected focus_event_ids")
    if recall_profile is MemoryRecallProfile.CROSS_REFERENCE and not 2 <= len(effective_need.focus_event_ids) <= 4:
        raise ValueError("CROSS_REFERENCE requires two to four focus_event_ids")
    if recall_profile is MemoryRecallProfile.FOCUSED_RECALL and len(effective_need.focus_event_ids) != 1:
        raise ValueError("FOCUSED_RECALL requires exactly one focus_event_id")

    retrieval_role = (
        "EVIDENCE"
        if recall_profile is MemoryRecallProfile.STANDARD
        else recall_profile.value
    )
    _persist_request(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=requesting_component,
        memory_request_id=memory_request_id,
        need=effective_need,
        retrieval_role=retrieval_role,
    )

    active_evidence = _active_working_state_evidence(
        conn,
        effective_need,
        before_global_seq=before_global_seq,
        max_items=effective_need.limit,
    )

    if not effective_need.include_persisted_history:
        packet = MemoryPacket(
            memory_request_id=memory_request_id,
            need=effective_need,
            supported=bool(active_evidence),
            items=active_evidence[: effective_need.limit],
            retrieval_trace={
                "kernel": None,
                "retrieval_role": retrieval_role,
                "query_strategy": "working_state_only",
                "working_state_event_ids": [str(item.source_event_id) for item in active_evidence],
                "query_attempts": [],
            },
        )
        _persist_packet(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            requesting_component=requesting_component,
            memory_request_id=memory_request_id,
            packet=packet,
        )
        return packet

    _ensure_projection_fresh(conn, before_global_seq=before_global_seq)
    policy = _RECALL_POLICIES[recall_profile]

    if effective_need.focus_event_ids:
        focus_sources = _focus_source_events(
            conn,
            effective_need,
            before_global_seq=before_global_seq,
        )
        excluded_ids = set(effective_need.focus_event_ids) | {
            item.source_event_id for item in active_evidence
        }

        if recall_profile is MemoryRecallProfile.CROSS_REFERENCE:
            kernel_packet = _recall_for_query(
                conn,
                need=effective_need,
                query_text=effective_need.query_text,
                before_global_seq=before_global_seq,
                recall_profile=recall_profile,
                seed_event_ids=tuple(effective_need.focus_event_ids),
            )
            translated = _packet_from_kernel(
                memory_request_id,
                effective_need,
                kernel_packet,
            )
            historical_evidence = [
                item for item in translated.items if item.source_event_id not in excluded_ids
            ][: effective_need.limit]
            merged = _compose_evidence(
                active_evidence,
                historical_evidence,
                limit=effective_need.limit,
            )
            packet = MemoryPacket(
                memory_request_id=memory_request_id,
                need=effective_need,
                supported=bool(merged),
                items=merged,
                retrieval_trace={
                    "kernel": "associative_recall_from_postgres",
                    "retrieval_role": retrieval_role,
                    "depth": "MULTI_CANDIDATE_JOINT",
                    "recall_profile": recall_profile.value,
                    "candidate_limit": policy.candidate_limit,
                    "association_limit": policy.association_limit,
                    "association_hops": policy.max_hops,
                    "association_decay": policy.decay,
                    "semantic_query_text": effective_need.query_text,
                    "focus_event_ids": [str(value) for value in effective_need.focus_event_ids],
                    "kernel_trace": asdict(kernel_packet.trace),
                },
            )
            _persist_packet(
                conn,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                requesting_component=requesting_component,
                memory_request_id=memory_request_id,
                packet=packet,
            )
            return packet

        focus_packets: list[MemoryPacket] = []
        attempts: list[dict[str, object]] = []
        for focus_event_id, _focus_text in focus_sources:
            kernel_packet = _recall_for_query(
                conn,
                need=effective_need,
                query_text=effective_need.query_text,
                before_global_seq=before_global_seq,
                recall_profile=recall_profile,
                seed_event_ids=(focus_event_id,),
            )
            translated = _packet_from_kernel(
                memory_request_id,
                effective_need,
                kernel_packet,
            )
            focus_packets.append(translated)
            attempts.append(
                {
                    "focus_event_id": str(focus_event_id),
                    "semantic_query_text": effective_need.query_text,
                    "supported": bool(translated.items),
                    "kernel_trace": asdict(kernel_packet.trace),
                }
            )
        historical_evidence = _merge_historical_packets(
            focus_packets,
            excluded_event_ids=excluded_ids,
            limit=effective_need.limit,
        )
        merged = _compose_evidence(
            active_evidence,
            historical_evidence,
            limit=effective_need.limit,
        )
        packet = MemoryPacket(
            memory_request_id=memory_request_id,
            need=effective_need,
            supported=bool(merged),
            items=merged,
            retrieval_trace={
                "kernel": "associative_recall_from_postgres",
                "retrieval_role": retrieval_role,
                "depth": (
                    "CANDIDATE_FOCUSED"
                    if recall_profile is MemoryRecallProfile.DEEPER_RESEARCH
                    else "SINGLE_CANDIDATE_DEEPEST"
                ),
                "recall_profile": recall_profile.value,
                "candidate_limit": policy.candidate_limit,
                "association_limit": policy.association_limit,
                "association_hops": policy.max_hops,
                "association_decay": policy.decay,
                "semantic_query_text": effective_need.query_text,
                "focus_event_ids": [str(value) for value in effective_need.focus_event_ids],
                "focus_attempts": attempts,
            },
        )
        _persist_packet(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            requesting_component=requesting_component,
            memory_request_id=memory_request_id,
            packet=packet,
        )
        return packet

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
            recall_profile=recall_profile,
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
    kernel_result = _packet_from_kernel(memory_request_id, effective_need, selected_kernel_packet)
    active_ids = {item.source_event_id for item in active_evidence}
    historical_evidence = [
        item for item in kernel_result.items if item.source_event_id not in active_ids
    ]
    merged = _compose_evidence(
        active_evidence,
        historical_evidence,
        limit=effective_need.limit,
    )

    packet = kernel_result.model_copy(
        update={
            "supported": bool(merged),
            "items": merged,
            "retrieval_trace": {
                **kernel_result.retrieval_trace,
                "retrieval_role": retrieval_role,
                "recall_profile": recall_profile.value,
                "candidate_limit": policy.candidate_limit,
                "association_limit": policy.association_limit,
                "association_hops": policy.max_hops,
                "association_decay": policy.decay,
                "query_strategy": "working_state_plus_history",
                "working_state_event_ids": [str(item.source_event_id) for item in active_evidence],
                "selected_query_role": selected_role,
                "selected_query_text": selected_query_text,
                "query_attempts": attempts,
            },
        }
    )

    _persist_packet(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=requesting_component,
        memory_request_id=memory_request_id,
        packet=packet,
    )
    return packet
