"""Application-owned execution bindings for selected v0.7 capabilities."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid5

import psycopg
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jit_agent import event_store, jit_memory
from jit_agent.capability_registry import RegisteredCapability
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


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v2"
SOURCE = "capability_runtime"
_MAX_PLANNER_CONTEXT_EVENTS = 12
_MAX_ANCHOR_CATALOG = 48
_BASE_HISTORICAL_EVIDENCE_BUDGET = 5
_MAX_MEMORY_PACKET_LIMIT = 20
_MEMORY_EVIDENCE_EXECUTORS = {"jit_memory", "deeper_research"}
_PLANNER_CONTEXT_EVENT_TYPES = {
    EventType.USER_PROMPT,
    EventType.INTERACTION_RESPONSE,
    EventType.AGENT_RESPONSE,
    EventType.AGENT_RESULT,
    EventType.TOOL_RESULT,
    EventType.SYSTEM_EVENT,
}


class CapabilityExecutionLLM(Protocol):
    """Fresh stateless categorical planning used by deeper internal research."""

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision: ...


class CapabilityExecution(BaseModel):
    """Immutable structured result of one selected capability invocation.

    Capability execution produces machine-consumable evidence/state. It does not
    produce an intermediate prose answer. The interaction response worker is
    summoned only after all selected executions have durable results.
    """

    model_config = ConfigDict(extra="forbid")
    execution_version: str = CAPABILITY_EXECUTION_VERSION
    capability_execution_id: UUID
    requester_task_id: UUID
    requester_step_id: UUID
    capability_id: str = Field(min_length=1)
    executor: str = Field(min_length=1)
    memory_packet: MemoryPacket | None = None

    @model_validator(mode="after")
    def validate_execution(self) -> "CapabilityExecution":
        if self.execution_version != CAPABILITY_EXECUTION_VERSION:
            raise ValueError("capability execution version is unsupported")
        if self.executor in _MEMORY_EVIDENCE_EXECUTORS and self.memory_packet is None:
            raise ValueError("memory-evidence capability execution requires a MemoryPacket")
        return self


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
    """Render semantic input while keeping model output non-generative."""

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


def _memory_packet_limit(
    *,
    active_event_ids: list[UUID],
    include_history: bool,
) -> int:
    """Size one bounded packet without silently truncating active WorkingState."""

    active_count = len(active_event_ids)
    if not include_history:
        return min(_MAX_MEMORY_PACKET_LIMIT, max(1, active_count))
    return min(
        _MAX_MEMORY_PACKET_LIMIT,
        max(
            _BASE_HISTORICAL_EVIDENCE_BUDGET,
            active_count + _BASE_HISTORICAL_EVIDENCE_BUDGET,
        ),
    )


def execute_registered_capability(
    conn: psycopg.Connection,
    llm: CapabilityExecutionLLM,
    *,
    registration: RegisteredCapability,
    capability_execution_id: UUID,
    requester_task_id: UUID,
    requester_step_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_text: str,
    before_global_seq: int,
    memory_request_id: UUID,
) -> CapabilityExecution:
    """Execute one scheduler-selected capability and return structured evidence.

    v0.7 supports the internal-memory evidence executors ``jit_memory`` and
    ``deeper_research``. Both use the same categorical/index-only memory-planning
    boundary. The final user-facing response is generated later by the response
    stage after every selected capability has completed.
    """

    if registration.executor not in _MEMORY_EVIDENCE_EXECUTORS:
        raise NotImplementedError(
            f"capability executor {registration.executor!r} has no v0.7 execution binding"
        )

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
    packet_limit = _memory_packet_limit(
        active_event_ids=active_event_ids,
        include_history=include_history,
    )

    need = jit_memory.build_memory_need(
        task_text,
        entities=anchors,
        active_event_ids=active_event_ids,
        include_persisted_history=include_history,
        conversation_id=None,
        limit=packet_limit,
    )
    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=(
            f"task:{requester_task_id}/capability:{registration.descriptor.capability_id}/"
            f"step:{requester_step_id}"
        ),
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
        activation_key=f"capability:{registration.descriptor.capability_id}",
    )

    execution = CapabilityExecution(
        capability_execution_id=capability_execution_id,
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
            "execution": execution.model_dump(mode="json"),
            "memory_scope": plan.scope.value,
            "anchor_indices": list(plan.anchor_indices),
        },
        event_id=uuid5(capability_execution_id, "event:result"),
    )
    return execution