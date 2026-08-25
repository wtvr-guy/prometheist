"""Primary Agent orchestration for the stateless Prometheist MAS.

The Primary Agent has no privileged memory path and no hard-coded specialist
catalog. It can either respond with supplied context or emit REQUEST_CAPABILITY;
deterministic application code resolves and invokes the selected capability.
"""
from __future__ import annotations

import logging
import re
import uuid

import psycopg

from jit_agent import capability_dispatcher, capability_registry, event_store
from jit_agent.llm import LLMClient
from jit_agent.models import (
    AgentAction,
    AgentDecision,
    AgentResult,
    CapabilityKind,
    CapabilityNeed,
    EventType,
    MemoryPacket,
    RetrievalRequest,
    SemanticRetrievalIntentV1,
)
from jit_agent.semantic_memory import EmbeddingProvider

logger = logging.getLogger(__name__)
SOURCE = "primary_agent"
CONTINUITY_POLICY = "REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1"
_CONTEXT_REFERENCE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        (
            r"\b(?:this\s+(?:one|ones)|that\s+"
            r"(?:one|ones|option|approach|plan|rule|choice|step|item|idea))\b"
        ),
        r"\b(?:these|those)\s+(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b",
        (
            r"\b(?:we|you|i)\s+(?:just|previously|earlier)\s+"
            r"(?:said|mentioned|decided|chose|selected|ruled|discussed|called|named|agreed)\b"
        ),
        (
            r"\b(?:did|do|have|are|were)\s+(?:we|you|i)\s+"
            r"(?:(?:just|previously|earlier)\s+)?"
            r"(?:say|mention|decide|choose|select|rule|discuss|call|calling|name|naming|agree|use|using)\b"
        ),
    )
)
_INLINE_ANTECEDENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        (
            r"\b(?:between|compare)\b.{1,240}\band\b.{0,160}"
            r"\b(?:which|what)\s+of\s+those\s+"
            r"(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b"
        ),
        (
            r"\bthese\s+(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\s+"
            r"(?:are|include)\b.{1,240}\band\b.{0,160}"
            r"\b(?:which|what)\s+of\s+those\s+"
            r"(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b"
        ),
    )
)
_INLINE_DEICTIC_PATTERN = re.compile(
    r"\b(?:which|what)\s+of\s+those\s+"
    r"(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b",
    re.IGNORECASE,
)
_INLINE_ASSIGNMENT_SUBJECT_PATTERN = re.compile(
    r"^\s*these\s+"
    r"(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b",
    re.IGNORECASE,
)
_EXPLICIT_CAPABILITY_REQUEST_PATTERN = re.compile(
    r"\b(?:use|ask|delegate\s+to)\s+(?:a\s+|an\s+|the\s+)?"
    r"(?:[a-z][\w-]*\s+){0,2}(?:specialist|agent|tool)\b",
    re.IGNORECASE,
)
_MEMORY_CAPABILITY_PATTERN = re.compile(
    r"\b(?:memory|history|historical|persisted|recall|retrieve)\b",
    re.IGNORECASE,
)


def _requires_persisted_context(user_text: str) -> bool:
    """Detect explicit references whose antecedent is outside the current message."""
    remaining = user_text
    for inline_pattern in _INLINE_ANTECEDENT_PATTERNS:
        remaining = inline_pattern.sub(
            lambda match: _INLINE_ASSIGNMENT_SUBJECT_PATTERN.sub(
                " ",
                _INLINE_DEICTIC_PATTERN.sub(" ", match.group(0)),
                count=1,
            ),
            remaining,
        )
    return any(pattern.search(remaining) for pattern in _CONTEXT_REFERENCE_PATTERNS)


def _decision_requests_memory(decision: AgentDecision) -> bool:
    return _MEMORY_CAPABILITY_PATTERN.search(decision.capability_query or "") is not None


def _apply_continuity_policy(
    user_text: str,
    decision: AgentDecision,
) -> tuple[AgentDecision, str | None]:
    """Route unresolved dialogue references through persisted-context access."""
    if not _requires_persisted_context(user_text):
        return decision, None
    if (
        decision.action == AgentAction.REQUEST_CAPABILITY
        and not _decision_requests_memory(decision)
        and _EXPLICIT_CAPABILITY_REQUEST_PATTERN.search(user_text)
    ):
        # Preserve an explicit non-memory operation. Its stateless specialist can
        # discover persisted context through the same capability boundary.
        return decision, None
    return (
        AgentDecision(
            action=AgentAction.REQUEST_CAPABILITY,
            capability_query="persisted internal history access",
            capability_input=(
                decision.capability_input if _decision_requests_memory(decision) else None
            ),
            retrieval_intent=decision.retrieval_intent or SemanticRetrievalIntentV1(),
        ),
        CONTINUITY_POLICY,
    )


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

    decision, policy_override = _apply_continuity_policy(user_text, decision)
    decision_payload = decision.model_dump(mode="json")
    if policy_override is not None:
        decision_payload["policy_override"] = policy_override
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.AGENT_DECISION,
        source=SOURCE,
        payload=decision_payload,
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
            kinds=[CapabilityKind.SERVICE] if policy_override is not None else None,
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
