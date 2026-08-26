"""Reusable deterministic interaction policy for the attention-centric path."""
from __future__ import annotations

import re
from enum import Enum
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, field_validator

from jit_agent.models import AgentAction, AgentDecision


INTERACTION_PROTOCOL_VERSION = "v0.7-g-interaction-v1"
CONTINUITY_POLICY_VERSION = "REFERENTIAL_CONTINUITY_REQUIRES_MEMORY_V1"
INTERACTION_CAPABILITIES = (
    "interaction.resolve_references",
    "interaction.classify",
    "memory.retrieve",
    "interaction.respond",
    "interaction.persist_result",
)

_CONTEXT_REFERENCE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:this\s+(?:one|ones)|that\s+(?:one|ones|option|approach|plan|rule|choice|step|item|idea))\b",
        r"\b(?:these|those)\s+(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b",
        r"\b(?:we|you|i)\s+(?:just|previously|earlier)\s+(?:said|mentioned|decided|chose|selected|ruled|discussed|called|named|agreed)\b",
        r"\b(?:did|do|have|are|were)\s+(?:we|you|i)\s+(?:(?:just|previously|earlier)\s+)?(?:say|mention|decide|choose|select|rule|discuss|call|calling|name|naming|agree|use|using)\b",
    )
)
_INLINE_ANTECEDENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        r"\b(?:between|compare)\b.{1,240}\band\b.{0,160}\b(?:which|what)\s+of\s+those\s+(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b",
        r"\bthese\s+(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\s+(?:are|include)\b.{1,240}\band\b.{0,160}\b(?:which|what)\s+of\s+those\s+(?:options?|approaches?|plans?|rules?|choices?|steps?|items?|ideas?)\b",
    )
)


class InteractionStage(str, Enum):
    RESOLVE_REFERENCES = "RESOLVE_REFERENCES"
    CLASSIFY = "CLASSIFY"
    RETRIEVE = "RETRIEVE"
    RESPOND = "RESPOND"
    PERSIST_RESULT = "PERSIST_RESULT"

    @property
    def capability(self) -> str:
        return {
            InteractionStage.RESOLVE_REFERENCES: INTERACTION_CAPABILITIES[0],
            InteractionStage.CLASSIFY: INTERACTION_CAPABILITIES[1],
            InteractionStage.RETRIEVE: INTERACTION_CAPABILITIES[2],
            InteractionStage.RESPOND: INTERACTION_CAPABILITIES[3],
            InteractionStage.PERSIST_RESULT: INTERACTION_CAPABILITIES[4],
        }[self]


INTERACTION_STAGES = tuple(InteractionStage)


class ReferenceAnalysis(BaseModel):
    policy_version: str = CONTINUITY_POLICY_VERSION
    requires_persisted_context: bool


class DurableInteraction(BaseModel):
    protocol_version: str = INTERACTION_PROTOCOL_VERSION
    interaction_id: UUID
    conversation_id: UUID
    correlation_id: UUID
    user_prompt_event_id: UUID
    before_global_seq: int = Field(ge=1)
    task_id: UUID
    assignment_id: UUID
    user_text: str = Field(min_length=1)

    @field_validator("user_text")
    @classmethod
    def normalize_user_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("user_text must not be empty")
        return normalized


def requires_persisted_context(user_text: str) -> bool:
    """Detect bounded references whose antecedent is outside this message."""

    remaining = user_text
    for pattern in _INLINE_ANTECEDENT_PATTERNS:
        remaining = pattern.sub(" ", remaining)
    return any(pattern.search(remaining) for pattern in _CONTEXT_REFERENCE_PATTERNS)


def apply_continuity_policy(
    user_text: str,
    decision: AgentDecision,
    analysis: ReferenceAnalysis,
) -> tuple[AgentDecision, str | None]:
    """Move the v0.6 continuity behavior out of Primary-Agent ownership."""

    if not analysis.requires_persisted_context:
        return decision, None
    if decision.action is AgentAction.RETRIEVE_CONTEXT:
        return decision, CONTINUITY_POLICY_VERSION
    return (
        AgentDecision(action=AgentAction.RETRIEVE_CONTEXT, query_text=user_text),
        CONTINUITY_POLICY_VERSION,
    )


def deterministic_interaction_id(conversation_id: UUID, correlation_id: UUID) -> UUID:
    return uuid5(conversation_id, f"interaction:{correlation_id}")


def deterministic_interaction_task_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "attention-task")


def deterministic_interaction_event_id(interaction_id: UUID, role: str) -> UUID:
    return uuid5(interaction_id, f"event:{role}")


def deterministic_memory_request_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "memory-request")
