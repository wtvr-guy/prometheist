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
from jit_agent.interaction_working_state import activate_working_state, load_working_state
from jit_agent.memory_kernel import tokenize
from jit_agent.models import (
    EventType,
    MemoryNeedDecision,
    MemoryPacket,
    MemoryRetrievalScope,
)


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v1"
SOURCE = "capability_runtime"
_MAX_PLANNER_CONTEXT_EVENTS = 12
_MAX_ANCHOR_CATALOG = 48
_PLANNER_CONTEXT_EVENT_TYPES = {
    EventType.USER_PROMPT,
    EventType.INTERACTION_RESPONSE,
    EventType.AGENT_RESPONSE,
    EventType.AGENT_RESULT,
    EventType.TOOL_RESULT,
    EventType.SYSTEM_EVENT,
}


class CapabilityExecutionLLM(Protocol):
    """Fresh stateless categorical planning used to route memory access."""

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision: ...


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


def _active_planner_context(
    conn: psycopg.Connection,
    active_event_ids: list[UUID],
    *,
    before_global_seq: int,
) -> tuple[str, ...]:
    """Rehydrate bounded canonical active text for one fresh routing call."""

    texts: list[str] = []
    for event_id in active_event_ids:
        event = event_store.get_event_by_id(conn, event_id)
        if event is None or event.global_seq >= before_global_seq:
            continue
        if event.event_type not in _PLANNER_CONTEXT_EVENT_TYPES:
            continue
        text = event.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        texts.append(" ".join(text.split()))
        if len(texts) == _MAX_PLANNER_CONTEXT_EVENTS:
            break
    return tuple(texts)


def _anchor_catalog(task_text: str, active_context: tuple[str, ...]) -> tuple[str, ...]:
    """Build a bounded deterministic catalog; the model may only select indices."""

    anchors: list[str] = []
    seen: set[str] = set()
    for text in (task_text, *active_context):
        for token in tokenize(text):
            if token in seen:
                continue
            seen.add(token)
            anchors.append(token)
            if len(anchors) == _MAX_ANCHOR_CATALOG:
                return tuple(anchors)
    return tuple(anchors)


def _memory_planner_task(
    *,
    task_text: str,
    active_context: tuple[str, ...],
    anchor_catalog: tuple[str, ...],
) -> str:
    """Render semantic input while keeping the model output non-generative."""

    sections = [f"[Current task]\n{task_text.strip()}"]
    if active_context:
        rendered_context = "\n".join(
            f"{index}: {text}" for index, text in enumerate(active_context)
        )
        sections.append(f"[Active canonical context]\n{rendered_context}")
    rendered_catalog = "\n".join(
        f"{index}: {anchor}" for index, anchor in enumerate(anchor_catalog)
    )
    sections.append(f"[Anchor catalog]\n{rendered_catalog}")
    return "\n\n".join(sections)


def _resolve_memory_plan(
    plan: MemoryNeedDecision,
    *,
    active_event_ids: list[UUID],
    anchor_catalog: tuple[str, ...],
) -> tuple[list[UUID], bool, list[str]]:
    """Validate categorical model output against application-owned state."""

    if any(index >= len(anchor_catalog) for index in plan.anchor_indices):
        raise RuntimeError("memory routing selected an anchor outside the supplied catalog")
    anchors = [anchor_catalog[index] for index in plan.anchor_indices]

    if plan.scope is MemoryRetrievalScope.ACTIVE_ONLY:
        if not active_event_ids:
            raise RuntimeError("ACTIVE_ONLY memory routing requires active working state")
        return list(active_event_ids), False, []
    if plan.scope is MemoryRetrievalScope.HISTORY_ONLY:
        return [], True, anchors
    return list(active_event_ids), True, anchors


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
    before_global_seq: int,
    memory_request_id: UUID,
) -> CapabilityExecution:
    """Execute selected memory bindings through WorkingState + JIT Memory.

    The model chooses only values that are legal for the current application
    state. Without active WorkingState, Prometheist owns HISTORY_ONLY and the
    model schema contains only bounded anchor indices. With active state, the
    model may additionally choose among active/history scope enums. The model
    never generates a search query, entity string, capability id, or
    phrase-specific continuity cue.
    """

    discovery_packet = _load_discovery_packet(conn, capability_request_id)
    if discovery_packet.requester_task_id != requester_task_id:
        raise RuntimeError("capability discovery task does not match execution task")

    working_state = load_working_state(conn, conversation_id)
    available_active_ids = (
        list(working_state.active_event_ids) if working_state is not None else []
    )
    active_context = _active_planner_context(
        conn,
        available_active_ids,
        before_global_seq=before_global_seq,
    )
    catalog = _anchor_catalog(task_text, active_context)
    plan = llm.plan_memory(
        _memory_planner_task(
            task_text=task_text,
            active_context=active_context,
            anchor_catalog=catalog,
        ),
        active_state_available=bool(active_context),
    )
    active_event_ids, include_history, anchors = _resolve_memory_plan(
        plan,
        active_event_ids=available_active_ids,
        anchor_catalog=catalog,
    )

    need = jit_memory.build_memory_need(
        task_text,
        entities=anchors,
        active_event_ids=active_event_ids,
        include_persisted_history=include_history,
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
            "memory_scope": plan.scope.value,
            "anchor_indices": list(plan.anchor_indices),
        },
        event_id=uuid5(capability_request_id, "event:result"),
    )
    return execution
