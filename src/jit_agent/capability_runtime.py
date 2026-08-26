"""Application-owned execution bindings for selected v0.7 capabilities."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID, uuid5

import psycopg
from pydantic import BaseModel, Field, model_validator

from jit_agent import event_store, jit_memory
from jit_agent.capability_registry import RegisteredCapability
from jit_agent.models import EventType, MemoryNeedDecision, MemoryPacket


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v1"
SOURCE = "capability_runtime"


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

    # Conversation/session identifiers are provenance, not memory boundaries.
    # Internal persisted memory must be able to recover evidence written in any
    # earlier conversation while ``before_global_seq`` remains the hard current-
    # turn leakage boundary.
    memory_scope_conversation_id = None

    if registration.executor == "jit_memory":
        supplemental = [capability_input] if capability_input else []
        need = jit_memory.build_memory_need(
            task_text,
            supplemental_query_texts=supplemental,
            conversation_id=memory_scope_conversation_id,
        )
    elif registration.executor == "memory_analysis":
        planned = llm.plan_memory(capability_input or task_text)
        supplemental = [planned.query_text] if planned.query_text != task_text else []
        need = jit_memory.build_memory_need(
            task_text,
            supplemental_query_texts=supplemental,
            entities=planned.entities,
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
