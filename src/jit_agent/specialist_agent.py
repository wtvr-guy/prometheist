"""Generic executor for stateless memory-grounded specialist capabilities.

Specialist identity and role instructions come from the deterministic capability
registry. The executor itself is capability-agnostic: every model call is fresh,
and any required persisted history is obtained through shared JIT Memory.
"""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

import psycopg

from jit_agent import event_store, jit_memory
from jit_agent.capability_registry import RegisteredCapability
from jit_agent.models import AgentResult, EventType, MemoryNeedDecision, MemoryPacket

logger = logging.getLogger(__name__)


class SpecialistLLM(Protocol):
    """Each method represents a fresh, disposable specialist model invocation."""

    def plan_specialist_memory(
        self,
        specialist_instruction: str,
        task: str,
    ) -> MemoryNeedDecision: ...

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket,
    ) -> str: ...


def _record_error(
    conn: psycopg.Connection,
    *,
    specialist: str,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    stage: str,
    exc: Exception,
) -> None:
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        event_store.record_event(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            event_type=EventType.ERROR,
            source=specialist,
            payload={"stage": stage, "error_type": type(exc).__name__, "message": str(exc)},
        )
    except Exception:
        logger.exception(
            "failed to persist specialist ERROR event specialist=%s stage=%s",
            specialist,
            stage,
        )


def handle_task(
    conn: psycopg.Connection,
    llm: SpecialistLLM,
    *,
    registration: RegisteredCapability,
    task: str,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    before_global_seq: int,
) -> AgentResult:
    """Run one registered specialist with no inherited transcript or hidden state."""
    specialist = registration.descriptor.capability_id
    if registration.executor != "memory_grounded_specialist":
        raise ValueError(
            f"Capability {specialist!r} is not executable by the specialist executor"
        )

    try:
        decision = llm.plan_specialist_memory(registration.specialist_instruction, task)
    except Exception as exc:
        _record_error(
            conn,
            specialist=specialist,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            stage="specialist_plan_memory",
            exc=exc,
        )
        raise

    need = jit_memory.build_memory_need(
        decision.query_text,
        entities=decision.entities,
        conversation_id=conversation_id,
    )
    try:
        packet = jit_memory.request_memory(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            requesting_agent=specialist,
            need=need,
            before_global_seq=before_global_seq,
        )
    except Exception as exc:
        _record_error(
            conn,
            specialist=specialist,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            stage="specialist_memory",
            exc=exc,
        )
        raise

    if packet.supported:
        try:
            text = llm.answer_specialist_task(
                registration.specialist_instruction,
                task,
                packet,
            )
        except Exception as exc:
            _record_error(
                conn,
                specialist=specialist,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                stage="specialist_answer",
                exc=exc,
            )
            raise
    else:
        text = "I do not have supporting persisted evidence for that."

    result = AgentResult(
        specialist=specialist,
        task=task,
        text=text,
        memory_request_ids=[packet.memory_request_id],
        evidence_event_ids=[item.source_event_id for item in packet.items],
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.AGENT_RESULT,
        source=specialist,
        payload=result.model_dump(mode="json"),
        payload_text=text,
    )
    return result
