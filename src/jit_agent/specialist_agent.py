"""Generic executor for stateless specialist-agent capabilities.

Specialists receive only their role instruction and current task. If additional
functionality or information is needed, they emit ``REQUEST_CAPABILITY`` and use
the same deterministic registry/dispatcher path as the Primary Agent.
"""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

import psycopg

from jit_agent import capability_dispatcher, capability_registry, event_store
from jit_agent.capability_registry import CapabilityRegistry, RegisteredCapability
from jit_agent.models import (
    AgentAction,
    AgentDecision,
    AgentResult,
    CapabilityNeed,
    EventType,
    MemoryPacket,
)

logger = logging.getLogger(__name__)


class SpecialistLLM(Protocol):
    """Each method represents a fresh, disposable specialist model invocation."""

    def decide_specialist_action(
        self,
        specialist_instruction: str,
        task: str,
    ) -> AgentDecision: ...

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket | None,
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
    registry: CapabilityRegistry = capability_registry.DEFAULT_REGISTRY,
    depth: int = 0,
) -> AgentResult:
    """Run one registered specialist with no inherited transcript or hidden state."""
    specialist = registration.descriptor.capability_id
    if registration.executor != "stateless_specialist":
        raise ValueError(
            f"Capability {specialist!r} is not executable by the specialist executor"
        )
    if not registration.instruction:
        raise ValueError(f"Specialist capability {specialist!r} has no role instruction")

    try:
        decision = llm.decide_specialist_action(registration.instruction, task)
    except Exception as exc:
        _record_error(
            conn,
            specialist=specialist,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            stage="specialist_decision",
            exc=exc,
        )
        raise

    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.AGENT_DECISION,
        source=specialist,
        payload=decision.model_dump(mode="json"),
    )

    memory_request_ids: list[uuid.UUID] = []
    evidence_event_ids: list[uuid.UUID] = []

    if decision.action == AgentAction.REQUEST_CAPABILITY:
        # A specialist's canonical capability cue is its explicit description of
        # the missing functionality. Excluding itself prevents trivial recursion.
        need = CapabilityNeed(
            query_text=decision.capability_query or "",
            exclude_capability_ids=[specialist],
            limit=1,
        )
        try:
            capability_packet = capability_registry.request_capability(
                conn,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                requesting_agent=specialist,
                need=need,
                registry=registry,
            )
        except Exception as exc:
            _record_error(
                conn,
                specialist=specialist,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                stage="specialist_capability_discovery",
                exc=exc,
            )
            raise

        if not capability_packet.matches:
            text = "No registered capability can satisfy the specialist's additional need."
        else:
            selected_id = capability_packet.matches[0].descriptor.capability_id
            selected = registry.get(selected_id)
            supplemental = [decision.capability_query] if decision.capability_query else []
            try:
                output = capability_dispatcher.invoke_capability(
                    conn,
                    llm,
                    registration=selected,
                    task=task,
                    conversation_id=conversation_id,
                    correlation_id=correlation_id,
                    before_global_seq=before_global_seq,
                    requesting_agent=specialist,
                    capability_request_id=capability_packet.capability_request_id,
                    supplemental_query_texts=supplemental,
                    registry=registry,
                    depth=depth,
                )
            except Exception as exc:
                _record_error(
                    conn,
                    specialist=specialist,
                    conversation_id=conversation_id,
                    correlation_id=correlation_id,
                    stage="specialist_capability_invoke",
                    exc=exc,
                )
                raise

            if isinstance(output, MemoryPacket):
                memory_request_ids.append(output.memory_request_id)
                evidence_event_ids.extend(item.source_event_id for item in output.items)
                if output.supported:
                    try:
                        text = llm.answer_specialist_task(
                            registration.instruction,
                            task,
                            output,
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
            else:
                # Nested agent capabilities already return a bounded textual result.
                text = output.text
                memory_request_ids.extend(output.memory_request_ids)
                evidence_event_ids.extend(output.evidence_event_ids)
    else:
        try:
            text = llm.answer_specialist_task(
                registration.instruction,
                task,
                None,
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

    result = AgentResult(
        specialist=specialist,
        task=task,
        text=text,
        memory_request_ids=memory_request_ids,
        evidence_event_ids=evidence_event_ids,
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
