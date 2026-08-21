"""Primary Agent orchestration for the stateless Prometheist MAS.

No hidden model state survives between calls. Persistent internal context is
obtained only through shared JIT Memory, while specialist identity is resolved
just in time through deterministic capability discovery rather than being
embedded in the Primary Agent's permanent prompt.
"""
from __future__ import annotations

import logging
import uuid

import psycopg

from jit_agent import capability_registry, event_store, jit_memory, specialist_agent
from jit_agent.llm import LLMClient
from jit_agent.models import (
    AgentAction,
    AgentDelegation,
    CapabilityKind,
    CapabilityNeed,
    EventType,
    RetrievalRequest,
)

logger = logging.getLogger(__name__)
SOURCE = "primary_agent"


def build_retrieval_request(query_text: str | None) -> RetrievalRequest:
    """Legacy request builder retained for old Retrieval Service regressions.

    The live Primary Agent no longer calls ``jit_agent.retrieval`` in v0.6.
    New agent code should use ``jit_memory.build_memory_need`` instead.
    """
    return RetrievalRequest(
        query_text=query_text,
        conversation_scope="ALL_CONVERSATIONS",
        source_types=[EventType.USER_PROMPT, EventType.AGENT_RESPONSE],
        ordering="RELEVANCE" if query_text else "CHRON_DESC",
        limit=5,
    )


def _record_error(
    conn: psycopg.Connection,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    stage: str,
    exc: Exception,
) -> None:
    """Best-effort persistence of orchestration failures."""
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
        logger.exception("failed to persist ERROR event for stage=%s", stage)


def handle_interaction(
    conn: psycopg.Connection,
    llm: LLMClient,
    user_text: str,
    conversation_id: uuid.UUID,
) -> str:
    """Handle one external interaction using only fresh model invocations."""
    event_store.start_conversation(conn, conversation_id)
    correlation_id = uuid.uuid4()

    user_prompt_event = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": user_text},
        payload_text=user_text,
    )

    try:
        decision = llm.classify(user_text)
    except Exception as exc:
        _record_error(conn, conversation_id, correlation_id, "classify", exc)
        raise
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.AGENT_DECISION,
        source=SOURCE,
        payload=decision.model_dump(mode="json"),
    )

    if decision.action == AgentAction.DELEGATE:
        task = decision.delegation_task or user_text
        need = CapabilityNeed(
            query_text=task,
            kinds=[CapabilityKind.AGENT],
            limit=1,
        )
        try:
            capability_packet = capability_registry.request_capability(
                conn,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                requesting_agent=SOURCE,
                need=need,
            )
        except Exception as exc:
            _record_error(conn, conversation_id, correlation_id, "capability_discovery", exc)
            raise

        if not capability_packet.matches:
            response_text = "No registered specialist capability matches that task."
        else:
            capability_id = capability_packet.matches[0].descriptor.capability_id
            registration = capability_registry.DEFAULT_REGISTRY.get(capability_id)
            delegation = AgentDelegation(
                specialist=capability_id,
                task=task,
                capability_request_id=capability_packet.capability_request_id,
            )
            event_store.record_event(
                conn,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                event_type=EventType.AGENT_DELEGATION,
                source=SOURCE,
                payload=delegation.model_dump(mode="json"),
                payload_text=task,
            )
            try:
                result = specialist_agent.handle_task(
                    conn,
                    llm,
                    registration=registration,
                    task=task,
                    conversation_id=conversation_id,
                    correlation_id=correlation_id,
                    before_global_seq=user_prompt_event.global_seq,
                )
            except Exception:
                # The specialist persists stage-specific ERROR events itself.
                raise
            response_text = result.text

    else:
        packet = None
        if decision.action == AgentAction.RETRIEVE_CONTEXT:
            # The current user message is the canonical recall cue. The
            # classifier's semantic compression is retained only as a bounded
            # fallback and can never override evidence already found by the
            # exact user wording.
            supplemental_queries = [decision.query_text] if decision.query_text else []
            need = jit_memory.build_memory_need(
                user_text,
                supplemental_query_texts=supplemental_queries,
                conversation_id=conversation_id,
            )
            try:
                packet = jit_memory.request_memory(
                    conn,
                    conversation_id=conversation_id,
                    correlation_id=correlation_id,
                    requesting_agent=SOURCE,
                    need=need,
                    before_global_seq=user_prompt_event.global_seq,
                )
            except Exception as exc:
                _record_error(conn, conversation_id, correlation_id, "memory", exc)
                raise

        try:
            response_text = llm.respond(user_text, packet)
        except Exception as exc:
            _record_error(conn, conversation_id, correlation_id, "respond", exc)
            raise

    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.AGENT_RESPONSE,
        source=SOURCE,
        payload={"text": response_text},
        payload_text=response_text,
    )
    return response_text
