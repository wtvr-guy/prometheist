"""Application-owned execution bindings for selected v0.7 capabilities."""
from __future__ import annotations

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
from jit_agent.interaction_working_state import load_working_state
from jit_agent.models import EventType, MemoryNeedDecision, MemoryPacket


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v1"
SOURCE = "capability_runtime"


class CapabilityExecutionLLM(Protocol):
    """Fresh stateless semantic planning used to formulate historical needs."""

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


def _merge_entities(*groups: list[str] | tuple[str, ...]) -> list[str]:
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
    """Execute selected memory bindings through working state + JIT Memory.

    Interaction continuity does not depend on a hand-maintained vocabulary of
    phrase, entity, or recency rules. Durable working state supplies bounded
    canonical event IDs already active in the situation. A fresh stateless
    semantic planner formulates any unresolved historical need; deterministic
    JIT Memory then retrieves and validates canonical evidence.
    """

    discovery_packet = _load_discovery_packet(conn, capability_request_id)
    if discovery_packet.requester_task_id != requester_task_id:
        raise RuntimeError("capability discovery task does not match execution task")

    working_state = load_working_state(conn, conversation_id)
    active_event_ids = working_state.active_event_ids if working_state is not None else []
    discovery_supplemental = discovery_packet.need.supplemental_query_texts
    planned = llm.plan_memory(capability_input or task_text)
    planned_queries = [planned.query_text] if planned.query_text != task_text else []

    # Conversation/session identifiers remain provenance, not memory walls.
    need = jit_memory.build_memory_need(
        task_text,
        supplemental_query_texts=_supplemental_queries(
            planned_queries,
            discovery_supplemental,
        ),
        entities=_merge_entities(planned.entities),
        active_event_ids=active_event_ids,
        conversation_id=None,
    )

    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=f"task:{requester_task_id}/worker-step:{requester_step_id}",
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
