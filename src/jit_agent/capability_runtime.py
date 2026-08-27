"""Application-owned execution bindings for selected v0.7 capabilities."""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID, uuid5

import psycopg
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jit_agent import event_store, jit_memory
from jit_agent.capability_registry import RegisteredCapability
from jit_agent.interaction_policy import (
    deterministic_interaction_event_id,
    deterministic_interaction_id,
)
from jit_agent.interaction_working_state import activate_working_state
from jit_agent.models import (
    CrossReferenceCandidateSelection,
    EventType,
    FocusedMemoryCandidateSelection,
    MemoryCandidateSelection,
    MemoryPacket,
)


CAPABILITY_EXECUTION_VERSION = "v0.7-capability-execution-v5"
SOURCE = "capability_runtime"
_DEEPER_RESEARCH_LIMIT = 10
_CROSS_REFERENCE_LIMIT = 10
_FOCUSED_RECALL_LIMIT = 8
_STANDARD_MEMORY_LIMIT = 5
_MEMORY_EVIDENCE_EXECUTORS = {
    "jit_memory",
    "deeper_research",
    "cross_reference",
    "focused_recall",
}


class CapabilityExecutionLLM(Protocol):
    def select_research_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> MemoryCandidateSelection: ...

    def select_cross_reference_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> CrossReferenceCandidateSelection: ...

    def select_focused_candidate(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> FocusedMemoryCandidateSelection: ...


class CapabilityExecution(BaseModel):
    """Immutable structured result of one capability invocation in one round."""

    model_config = ConfigDict(extra="forbid")
    execution_version: str = CAPABILITY_EXECUTION_VERSION
    capability_execution_id: UUID
    requester_task_id: UUID
    requester_step_id: UUID
    round_index: int = Field(ge=0)
    plan_position: int = Field(ge=0)
    capability_id: str = Field(min_length=1)
    executor: str = Field(min_length=1)
    memory_packet: MemoryPacket | None = None
    result_data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_execution(self) -> "CapabilityExecution":
        if self.execution_version != CAPABILITY_EXECUTION_VERSION:
            raise ValueError("capability execution version is unsupported")
        if self.executor in _MEMORY_EVIDENCE_EXECUTORS and self.memory_packet is None:
            raise ValueError("memory-evidence capability execution requires a MemoryPacket")
        return self


def _candidate_event_ids(
    packet: MemoryPacket,
    indices: list[int],
) -> list[UUID]:
    if any(index < 0 or index >= len(packet.items) for index in indices):
        raise RuntimeError("memory capability selected a candidate outside the supplied packet")
    return [packet.items[index].source_event_id for index in indices]


def _existing_execution(
    conn: psycopg.Connection,
    capability_execution_id: UUID,
) -> CapabilityExecution | None:
    event = event_store.get_event_by_id(
        conn,
        uuid5(capability_execution_id, "event:result"),
    )
    if event is None:
        return None
    payload = event.payload.get("execution")
    if not isinstance(payload, dict):
        raise RuntimeError("persisted capability result has invalid execution payload")
    return CapabilityExecution.model_validate(payload)


def execute_registered_capability(
    conn: psycopg.Connection,
    llm: CapabilityExecutionLLM,
    *,
    registration: RegisteredCapability,
    capability_execution_id: UUID,
    requester_task_id: UUID,
    requester_step_id: UUID,
    round_index: int,
    plan_position: int,
    conversation_id: UUID,
    correlation_id: UUID,
    task_text: str,
    before_global_seq: int,
    memory_request_id: UUID,
    candidate_packet: MemoryPacket,
) -> CapabilityExecution:
    """Execute one Attention-ordered capability and return structured evidence.

    Models never author retrieval text or event IDs. Research capabilities select
    canonical MemoryPacket candidates by bounded integer index; Prometheist
    resolves those indices to event IDs and applies a deterministic recall profile.
    The current task text remains the semantic cue for every research profile;
    selected canonical IDs narrow the graph topology rather than replacing the
    meaning of the current percept.
    """

    existing = _existing_execution(conn, capability_execution_id)
    if existing is not None:
        return existing

    executor = registration.executor
    selection_payload: dict[str, Any] = {}
    if executor == "jit_memory":
        need = jit_memory.build_memory_need(
            task_text,
            include_persisted_history=True,
            conversation_id=None,
            limit=_STANDARD_MEMORY_LIMIT,
        )
        recall_profile = jit_memory.MemoryRecallProfile.STANDARD
    elif executor == "deeper_research":
        if not candidate_packet.items:
            raise RuntimeError("deeper_research requires at least one current memory candidate")
        selection = llm.select_research_candidates(task_text, candidate_packet)
        focus_event_ids = _candidate_event_ids(
            candidate_packet,
            list(selection.candidate_indices),
        )
        need = jit_memory.build_memory_need(
            task_text,
            focus_event_ids=focus_event_ids,
            include_persisted_history=True,
            conversation_id=None,
            limit=_DEEPER_RESEARCH_LIMIT,
        )
        recall_profile = jit_memory.MemoryRecallProfile.DEEPER_RESEARCH
        selection_payload = {
            "candidate_indices": list(selection.candidate_indices),
            "focus_event_ids": [str(value) for value in focus_event_ids],
        }
    elif executor == "cross_reference":
        if len(candidate_packet.items) < 2:
            raise RuntimeError("cross_reference requires at least two current memory candidates")
        selection = llm.select_cross_reference_candidates(task_text, candidate_packet)
        focus_event_ids = _candidate_event_ids(
            candidate_packet,
            list(selection.candidate_indices),
        )
        need = jit_memory.build_memory_need(
            task_text,
            focus_event_ids=focus_event_ids,
            include_persisted_history=True,
            conversation_id=None,
            limit=_CROSS_REFERENCE_LIMIT,
        )
        recall_profile = jit_memory.MemoryRecallProfile.CROSS_REFERENCE
        selection_payload = {
            "candidate_indices": list(selection.candidate_indices),
            "focus_event_ids": [str(value) for value in focus_event_ids],
        }
    elif executor == "focused_recall":
        if not candidate_packet.items:
            raise RuntimeError("focused_recall requires a non-empty broader-research packet")
        selection = llm.select_focused_candidate(task_text, candidate_packet)
        focus_event_ids = _candidate_event_ids(
            candidate_packet,
            [selection.candidate_index],
        )
        need = jit_memory.build_memory_need(
            task_text,
            focus_event_ids=focus_event_ids,
            include_persisted_history=True,
            conversation_id=None,
            limit=_FOCUSED_RECALL_LIMIT,
        )
        recall_profile = jit_memory.MemoryRecallProfile.FOCUSED_RECALL
        selection_payload = {
            "candidate_index": selection.candidate_index,
            "focus_event_ids": [str(value) for value in focus_event_ids],
        }
    else:
        raise NotImplementedError(
            f"capability executor {executor!r} has no v0.7 execution binding"
        )

    packet = jit_memory.request_memory(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_component=(
            f"task:{requester_task_id}/round:{round_index}/"
            f"capability:{registration.descriptor.capability_id}/step:{requester_step_id}"
        ),
        need=need,
        before_global_seq=before_global_seq,
        memory_request_id=memory_request_id,
        recall_profile=recall_profile,
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
        activation_key=f"capability:{round_index}:{registration.descriptor.capability_id}",
    )

    execution = CapabilityExecution(
        capability_execution_id=capability_execution_id,
        requester_task_id=requester_task_id,
        requester_step_id=requester_step_id,
        round_index=round_index,
        plan_position=plan_position,
        capability_id=registration.descriptor.capability_id,
        executor=executor,
        memory_packet=packet,
        result_data={
            "supported": packet.supported,
            "item_count": len(packet.items),
            "recall_profile": recall_profile.value,
            **selection_payload,
        },
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.CAPABILITY_RESULT,
        source=SOURCE,
        payload={"execution": execution.model_dump(mode="json")},
        event_id=uuid5(capability_execution_id, "event:result"),
    )
    return execution
