"""Primary Agent orchestration: stateless (not "pure" -- it has real side
effects: persistence, retrieval, LLM calls). No hidden state carried between
separate external interactions; `conversation_id` is only a lookup key.
"""
from __future__ import annotations

import logging
import uuid

import psycopg

from jit_agent import event_store, retrieval
from jit_agent.llm import LLMClient
from jit_agent.models import AgentAction, EventType, RetrievalRequest

logger = logging.getLogger(__name__)

SOURCE = "primary_agent"


def build_retrieval_request(query_text: str | None) -> RetrievalRequest:
    """Application policy for turning the LLM's minimal decision into a full
    retrieval request. Scope/source types/ordering/limit are never
    LLM-generated (spec section 9).

    Conversation boundaries are organizational metadata, not memory walls --
    search spans ALL_CONVERSATIONS by default. USER_PROMPT is not synonymous
    with "memory": the agent's own past answers (AGENT_RESPONSE) are
    retrievable too, so "what did you tell me about X" works, not just
    "what did I tell you about X".
    """
    return RetrievalRequest(
        query_text=query_text,
        conversation_scope="ALL_CONVERSATIONS",
        source_types=[EventType.USER_PROMPT, EventType.AGENT_RESPONSE],
        ordering="RELEVANCE" if query_text else "CHRON_DESC",
        limit=5,
    )


def _record_error(conn: psycopg.Connection, conversation_id, correlation_id, stage: str, exc: Exception) -> None:
    """Best-effort: persist that a failure happened, without letting a
    failure to persist the failure itself take down the interaction further.
    """
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

    retrieved_items = None
    if decision.action == AgentAction.RETRIEVE_CONTEXT:
        retrieval_request = build_retrieval_request(decision.query_text)
        event_store.record_event(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            event_type=EventType.RETRIEVAL_REQUEST,
            source=SOURCE,
            payload=retrieval_request.model_dump(mode="json"),
        )
        try:
            result = retrieval.search(
                conn,
                conversation_id,
                retrieval_request,
                before_conversation_seq=user_prompt_event.conversation_seq,
                before_global_seq=user_prompt_event.global_seq,
            )
        except Exception as exc:
            _record_error(conn, conversation_id, correlation_id, "retrieval", exc)
            raise
        retrieved_items = result.items
        event_store.record_event(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            event_type=EventType.RETRIEVAL_RESULT,
            source=SOURCE,
            payload=result.model_dump(mode="json"),
        )

    try:
        response_text = llm.respond(user_text, retrieved_items)
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
