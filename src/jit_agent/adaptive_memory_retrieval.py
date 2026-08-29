"""Parallel experimental retrieval boundary for adaptive memory attention.

This module deliberately does not replace ``jit_memory.request_memory``. It lets
benchmarks execute the adaptive controller against the same PostgreSQL Memory
Kernel, canonical events, leakage boundary, evidence threshold, and provenance
machinery as the frozen v0.7 recall profiles.
"""
from __future__ import annotations

from dataclasses import asdict
import uuid

import psycopg

from jit_agent import jit_memory, postgres_memory_kernel
from jit_agent.adaptive_memory_attention import (
    MemoryUncertainty,
    RetrievalTelemetry,
    derive_adaptive_recall_policy,
)
from jit_agent.memory_kernel import CueState
from jit_agent.models import MemoryPacket


RETRIEVAL_ROLE = "ADAPTIVE_MEMORY_ATTENTION"


def request_adaptive_memory(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_component: str,
    need,
    uncertainty: MemoryUncertainty,
    telemetry: RetrievalTelemetry,
    before_global_seq: int | None,
    memory_request_id: uuid.UUID | None = None,
) -> MemoryPacket:
    """Execute one deterministic adaptive memory-attention pass.

    Models may have selected the canonical ``need.focus_event_ids`` and a closed
    ``MemoryUncertainty`` value before this call. They cannot provide numeric
    kernel settings. The adaptive controller derives those settings solely from
    bounded telemetry and application-owned policy.
    """

    memory_request_id = memory_request_id or uuid.uuid4()
    effective_need = need.model_copy(
        update={"source_types": list(jit_memory._effective_source_types(need))}
    )

    focus_sources = jit_memory._focus_source_events(
        conn,
        effective_need,
        before_global_seq=before_global_seq,
    ) if effective_need.focus_event_ids else []
    policy = derive_adaptive_recall_policy(
        uncertainty=uncertainty,
        anchor_count=len(focus_sources),
        telemetry=telemetry,
    )
    seed_event_ids = (
        tuple(event_id for event_id, _text in focus_sources)
        if policy.use_focus_anchors
        else ()
    )

    jit_memory._persist_request(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=requesting_component,
        memory_request_id=memory_request_id,
        need=effective_need,
        retrieval_role=RETRIEVAL_ROLE,
    )

    active_evidence = jit_memory._active_working_state_evidence(
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
                "retrieval_role": RETRIEVAL_ROLE,
                "query_strategy": "working_state_only",
                "adaptive_policy": asdict(policy),
                "uncertainty": uncertainty.value,
                "telemetry": asdict(telemetry),
            },
        )
        jit_memory._persist_packet(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            requesting_component=requesting_component,
            memory_request_id=memory_request_id,
            packet=packet,
        )
        return packet

    jit_memory._ensure_projection_fresh(conn, before_global_seq=before_global_seq)
    cue = CueState(
        query_text=effective_need.query_text,
        entities=tuple(effective_need.entities),
        reference_time=effective_need.reference_time,
        conversation_id=(
            str(effective_need.conversation_id)
            if effective_need.conversation_id
            else None
        ),
        source_types=tuple(
            item.value for item in jit_memory._effective_source_types(effective_need)
        ),
        limit=effective_need.limit,
        minimum_score=policy.minimum_score,
    )
    kernel_packet = postgres_memory_kernel.associative_recall_from_postgres(
        conn,
        cue,
        before_global_seq=before_global_seq,
        candidate_limit=policy.candidate_limit,
        association_limit=policy.association_limit,
        max_hops=policy.max_hops,
        decay=policy.decay,
        seed_event_ids=tuple(str(value) for value in seed_event_ids),
    )
    translated = jit_memory._packet_from_kernel(
        memory_request_id,
        effective_need,
        kernel_packet,
    )

    excluded_ids = {
        *effective_need.focus_event_ids,
        *(item.source_event_id for item in active_evidence),
    }
    historical_evidence = [
        item for item in translated.items
        if item.source_event_id not in excluded_ids
    ]
    merged = jit_memory._compose_evidence(
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
            "retrieval_role": RETRIEVAL_ROLE,
            "semantic_query_text": effective_need.query_text,
            "focus_event_ids": [str(value) for value in effective_need.focus_event_ids],
            "used_focus_event_ids": [str(value) for value in seed_event_ids],
            "uncertainty": uncertainty.value,
            "telemetry": asdict(telemetry),
            "adaptive_policy": asdict(policy),
            "kernel_trace": asdict(kernel_packet.trace),
        },
    )
    jit_memory._persist_packet(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=requesting_component,
        memory_request_id=memory_request_id,
        packet=packet,
    )
    return packet
