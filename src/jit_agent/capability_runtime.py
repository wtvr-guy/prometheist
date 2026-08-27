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
from jit_agent.interaction_policy import (
    deterministic_interaction_event_id,
    deterministic_interaction_id,
)
from jit_agent.interaction_working_state import (
    activate_working_state,
    load_working_state,
)
from jit_agent.models import EventType, MemoryNeedDecision, MemoryPacket


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v1"
SOURCE = "capability_runtime"
_MAX_PLANNER_CONTEXT_EVENTS = 12
_PLANNER_CONTEXT_EVENT_TYPES = {
    EventType.USER_PROMPT,
    EventType.INTERACTION_RESPONSE,
    EventType.AGENT_RESPONSE,
    EventType.AGENT_RESULT,
    EventType.TOOL_RESULT,
    EventType.SYSTEM_EVENT,
}


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


def _active_planner_context(
    conn: psycopg.Connection,
    active_event_ids: list[UUID],
    *,
    before_global_seq: int,
) -> str:
    """Render bounded canonical active events for one fresh semantic planner.

    WorkingState stores only event IDs. The planner receives canonical source
    text just in time so it can resolve the current utterance against the active
    situation without inheriting a transcript or relying on application-owned
    phrase rules.
    """

    blocks: list[str] = []
    for event_id in active_event_ids:
        event = event_store.get_event_by_id(conn, event_id)
        if event is None:
            continue
        if event.global_seq >= before_global_seq:
            continue
        if event.event_type not in _PLANNER_CONTEXT_EVENT_TYPES:
            continue
        text = event.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        normalized = " ".join(text.split())
        blocks.append(f"- {event.event_type.value}: {normalized}")
        if len(blocks) == _MAX_PLANNER_CONTEXT_EVENTS:
            break
    return "\n".join(blocks)


def _memory_planner_task(
    *,
    task_text: str,
    capability_input: str | None,
    active_context: str,
) -> str:
    """Build a bounded semantic-planning input from system-owned current state."""

    sections = [f"[Current task]\n{task_text.strip()}"]
    if capability_input and capability_input.strip() and capability_input.strip() != task_text.strip():
        sections.append(f"[Capability narrowing]\n{capability_input.strip()}")
    if active_context:
        sections.append(f"[Active canonical context]\n{active_context}")
    sections.append(
        "[Planning objective]\n"
        "Resolve references using the active canonical context, then describe the older "
        "persisted evidence still needed to answer the current task. Return a self-contained "
        "historical information need; do not answer the task."
    )
    return "\n\n".join(sections)


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
    semantic planner sees those canonical events just in time and formulates any
    unresolved historical need; deterministic JIT Memory then retrieves and
    validates canonical evidence.
    """

    discovery_packet = _load_discovery_packet(conn, capability_request_id)
    if discovery_packet.requester_task_id != requester_task_id:
        raise RuntimeError("capability discovery task does not match execution task")

    working_state = load_working_state(conn, conversation_id)
    active_event_ids = working_state.active_event_ids if working_state is not None else []
    active_context = _active_planner_context(
        conn,
        active_event_ids,
        before_global_seq=before_global_seq,
    )
    discovery_supplemental = discovery_packet.need.supplemental_query_texts
    planned = llm.plan_memory(
        _memory_planner_task(
            task_text=task_text,
            capability_input=capability_input,
            active_context=active_context,
        )
    )
    planned_queries = [planned.query_text] if planned.query_text != task_text else []

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

    interaction_id = deterministic_interaction_id(conversation_id, correlation_id)
    prompt_event_id = deterministic_interaction_event_id(interaction_id, "user-prompt")
    activate_working_state(
        conn,
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        activated_event_ids=[
            *[item.source_event_id for item in packet.items],
            prompt_event_id,
        ],
        activation_key="memory",
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