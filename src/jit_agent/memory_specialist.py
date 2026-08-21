"""A specialized stateless agent that independently consumes shared JIT Memory."""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

import psycopg

from jit_agent import event_store, jit_memory
from jit_agent.models import AgentResult, EventType, MemoryNeedDecision, MemoryPacket

logger = logging.getLogger(__name__)
SOURCE = "memory_specialist"


class MemorySpecialistLLM(Protocol):
    """Each method represents a fresh, disposable model invocation."""

    def plan_memory(self, task: str) -> MemoryNeedDecision: ...

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str: ...


def _record_error(
    conn: psycopg.Connection,
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
            source=SOURCE,
            payload={"stage": stage, "error_type": type(exc).__name__, "message": str(exc)},
        )
    except Exception:
        logger.exception("failed to persist specialist ERROR event for stage=%s", stage)


def handle_task(
    conn: psycopg.Connection,
    llm: MemorySpecialistLLM,
    *,
    task: str,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    before_global_seq: int,
) -> AgentResult:
    """Complete a bounded delegated task with no inherited transcript state."""
    try:
        decision = llm.plan_memory(task)
    except Exception as exc:
        _record_error(conn, conversation_id, correlation_id, "specialist_plan_memory", exc)
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
            requesting_agent=SOURCE,
            need=need,
            before_global_seq=before_global_seq,
        )
    except Exception as exc:
        _record_error(conn, conversation_id, correlation_id, "specialist_memory", exc)
        raise

    if packet.supported:
        try:
            text = llm.answer_memory_task(task, packet)
        except Exception as exc:
            _record_error(conn, conversation_id, correlation_id, "specialist_answer", exc)
            raise
    else:
        # Hard guardrail: topical near-matches are not permission to fabricate a
        # memory-grounded answer. The specialist abstains before generation.
        text = "I do not have supporting persisted evidence for that."

    result = AgentResult(
        specialist=SOURCE,
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
        source=SOURCE,
        payload=result.model_dump(mode="json"),
        payload_text=text,
    )
    return result
