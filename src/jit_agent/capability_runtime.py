"""Application-owned execution bindings for selected v0.7 capabilities."""
from __future__ import annotations

import re
from typing import Protocol
from uuid import UUID, uuid5

import psycopg
from pydantic import BaseModel, Field, model_validator

from jit_agent import event_store, jit_memory
from jit_agent.capability_registry import (
    CapabilityPacket,
    RegisteredCapability,
    deterministic_capability_event_id,
)
from jit_agent.models import EventType, MemoryNeedDecision, MemoryPacket


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v1"
SOURCE = "capability_runtime"
_ENTITY_SPAN_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9_-]*(?:\s+[A-Z][A-Za-z0-9_-]*)+\b"
)


class CapabilityExecutionLLM(Protocol):
    """Fresh model call used only by the memory-analysis execution profile."""

    def plan_memory(self, task: str) -> MemoryNeedDecision: ...


class CapabilityExecution(BaseModel):
    """Immutable structured result of one selected capability invocation."""

    execution_version: str = CAPABILITY_EXECUTION_VERSION
    capability_request_id: UUID
    requester_task_id: UUID
    requester_step_id: UUID
    capability_id: str = Field(min_length=1)
    executor: str = Field(min_length=1)
    memory_packet: MemoryPacket | None = None

    @model_validator(mode="after")
    def validate_execution(self) -> "CapabilityExecution":
        if self.execution_version != CAPABILITY_EXECUTION_VERSION:
            raise ValueError("capability execution version is unsupported")
        if self.executor in {"jit_memory", "memory_analysis"} and self.memory_packet is None:
            raise ValueError("memory capability execution requires a MemoryPacket")
        return self


def _load_discovery_packet(
    conn: psycopg.Connection,
    capability_request_id: UUID,
) -> CapabilityPacket:
    """Reconstruct the authoritative discovery handoff from durable history."""

    event = event_store.get_event_by_id(
        conn,
        deterministic_capability_event_id(capability_request_id, "packet"),
    )
    if event is None:
        raise RuntimeError("selected capability has no durable discovery packet")
    if event.event_type is not EventType.CAPABILITY_PACKET:
        raise RuntimeError("capability discovery event has the wrong event type")
    try:
        return CapabilityPacket.model_validate(event.payload["packet"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("capability discovery packet is invalid") from exc


def _supplemental_queries(*groups: list[str] | tuple[str, ...]) -> list[str]:
    """Merge bounded equivalent cues without changing deterministic ordering."""

    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            normalized = value.strip()
            if not normalized:
                continue
            key = " ".join(normalized.split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
            if len(merged) == 3:
                return merged
    return merged


def _deterministic_entity_cues(*texts: str | None) -> list[str]:
    """Extract bounded explicit multi-token names without model-owned identity inference.

    The memory kernel deliberately admits entity-anchored evidence under a
    stricter direct-support policy.  The v0.7 worker path therefore preserves
    obvious names already present in the interaction/planning text instead of
    forcing every natural-language query to satisfy lexical coverage alone.
    This is syntax-only cue extraction: no entity meaning or identity is
    inferred, and canonical events remain the sole evidence source.
    """

    entities: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in _ENTITY_SPAN_RE.finditer(text):
            value = " ".join(match.group(0).split())
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            entities.append(value)
            if len(entities) == 8:
                return entities
    return entities


def _merge_entities(*groups: list[str] | tuple[str, ...]) -> list[str]:
    """Merge bounded entity cues while preserving first-seen spelling/order."""

    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            normalized = value.strip()
            if not normalized:
                continue
            key = " ".join(normalized.split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
            if len(merged) == 8:
                return merged
    return merged


def execute_registered_capability(
    conn: psycopg.Connection,
    llm: CapabilityExecutionLLM,
    *,
    registration: RegisteredCapability,
    capability_request_id: UUID,
    requester_task_id: UUID,
    requester_step_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_text: str,
    capability_input: str | None,
    before_global_seq: int,
    memory_request_id: UUID,
) -> CapabilityExecution:
    """Execute a selected binding without granting policy authority to a worker."""

    discovery_packet = _load_discovery_packet(conn, capability_request_id)
    if discovery_packet.requester_task_id != requester_task_id:
        raise RuntimeError("capability discovery task does not match execution task")

    # Conversation/session identifiers are provenance, not memory boundaries.
    # Internal persisted memory must be able to recover evidence written in any
    # earlier conversation while ``before_global_seq`` remains the hard current-
    # turn leakage boundary.
    memory_scope_conversation_id = None
    discovery_supplemental = discovery_packet.need.supplemental_query_texts

    if registration.executor == "jit_memory":
        explicit_input = [capability_input] if capability_input else []
        supplemental = _supplemental_queries(
            discovery_supplemental,
            explicit_input,
        )
        entities = _deterministic_entity_cues(
            task_text,
            capability_input,
            *discovery_supplemental,
        )
        need = jit_memory.build_memory_need(
            task_text,
            supplemental_query_texts=supplemental,
            entities=entities,
            conversation_id=memory_scope_conversation_id,
        )
    elif registration.executor == "memory_analysis":
        planned = llm.plan_memory(capability_input or task_text)
        planned_queries = [planned.query_text] if planned.query_text != task_text else []
        supplemental = _supplemental_queries(
            discovery_supplemental,
            planned_queries,
        )
        entities = _merge_entities(
            planned.entities,
            _deterministic_entity_cues(
                task_text,
                capability_input,
                planned.query_text,
                *discovery_supplemental,
            ),
        )
        need = jit_memory.build_memory_need(
            task_text,
            supplemental_query_texts=supplemental,
            entities=entities,
            conversation_id=memory_scope_conversation_id,
        )
    else:
        raise ValueError(
            f"Capability {registration.descriptor.capability_id!r} has unsupported "
            f"executor {registration.executor!r}"
        )

    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=(
            f"task:{requester_task_id}/worker-step:{requester_step_id}"
        ),
        need=need,
        before_global_seq=before_global_seq,
        memory_request_id=memory_request_id,
    )
    execution = CapabilityExecution(
        capability_request_id=capability_request_id,
        requester_task_id=requester_task_id,
        requester_step_id=requester_step_id,
        capability_id=registration.descriptor.capability_id,
        executor=registration.executor,
        memory_packet=packet,
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.CAPABILITY_RESULT,
        source=SOURCE,
        payload={
            "execution_version": execution.execution_version,
            "capability_request_id": str(capability_request_id),
            "requester_task_id": str(requester_task_id),
            "requester_step_id": str(requester_step_id),
            "capability_id": execution.capability_id,
            "executor": execution.executor,
            "memory_request_id": str(packet.memory_request_id),
        },
        event_id=uuid5(capability_request_id, "event:result"),
    )
    return execution
