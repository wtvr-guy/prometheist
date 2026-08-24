"""Primary Agent orchestration for the stateless Prometheist MAS.

The Primary Agent has no privileged memory path and no hard-coded specialist
catalog. It can either respond with supplied context or emit REQUEST_CAPABILITY;
deterministic application code resolves and invokes the selected capability.
"""
from __future__ import annotations

import logging
import uuid

import psycopg

from jit_agent import capability_dispatcher, capability_registry, event_store
from jit_agent.llm import LLMClient
from jit_agent.models import (
    AgentAction,
    AgentResult,
    CapabilityNeed,
    EventType,
    MemoryPacket,
    RetrievalRequest,
)
from jit_agent.semantic_memory import EmbeddingProvider

logger = logging.getLogger(__name__)
SOURCE = "primary_agent"


def build_retrieval_request(query_text: str | None) -> RetrievalRequest:
    """Legacy request builder retained for old Retrieval Service regressions."""
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
    *,
    embedding_provider: EmbeddingProvider | None = None,
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

    if decision.action == AgentAction.RESPOND_DIRECTLY:
        try:
            response_text = llm.respond(user_text, None)
        except Exception as exc:
            _record_error(conn, conversation_id, correlation_id, "respond", exc)
            raise
    else:
        discovery_supplemental = [decision.capability_query] if decision.capability_query else []
        need = CapabilityNeed(
            query_text=user_text,
            supplemental_query_texts=discovery_supplemental,
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
            response_text = "No registered capability matches that request."
        else:
            capability_id = capability_packet.matches[0].descriptor.capability_id
            registration = capability_registry.DEFAULT_REGISTRY.get(capability_id)
            capability_input_supplemental = [decision.capability_input] if decision.capability_input else []
            try:
                output = capability_dispatcher.invoke_capability(
                    conn,
                    llm,
                    registration=registration,
                    task=user_text,
                    conversation_id=conversation_id,
                    correlation_id=correlation_id,
                    before_global_seq=user_prompt_event.global_seq,
                    requesting_agent=SOURCE,
                    capability_request_id=capability_packet.capability_request_id,
                    supplemental_query_texts=capability_input_supplemental,
                    semantic_intent=decision.retrieval_intent,
                    embedding_provider=embedding_provider,
                )
            except Exception as exc:
                _record_error(conn, conversation_id, correlation_id, "capability_invoke", exc)
                raise

            if isinstance(output, MemoryPacket):
                try:
                    response_text = llm.respond(user_text, output)
                except Exception as exc:
                    _record_error(conn, conversation_id, correlation_id, "respond", exc)
                    raise
            elif isinstance(output, AgentResult):
                response_text = output.text
            else:  # pragma: no cover
                raise TypeError(f"unsupported capability output: {type(output).__name__}")

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
