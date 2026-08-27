"""Reusable deterministic interaction policy for the attention-centric path."""
from __future__ import annotations

import re
from enum import Enum
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, field_validator, model_validator


INTERACTION_PROTOCOL_VERSION = "v0.7-interaction-v3"
CONTINUITY_POLICY_VERSION = "ACTIVE_WORKING_STATE_REQUIRES_MEMORY_V1"
INTERACTION_CAPABILITIES = (
    "interaction.resolve_references",
    "capability.discover",
    "capability.execute",
    "interaction.respond",
    "interaction.persist_result",
)

_EXPLICIT_CAPABILITY_REQUEST_PATTERN = re.compile(
    r"\b(?:use|ask|delegate\s+to)\s+(?:a\s+|an\s+|the\s+)?"
    r"(?:[a-z][\w-]*\s+){0,2}(?:service|workflow|tool|model|specialist|agent)\b",
    re.IGNORECASE,
)
_MEMORY_CAPABILITY_PATTERN = re.compile(
    r"\b(?:memory|history|historical|persisted|recall|retrieve)\b",
    re.IGNORECASE,
)


class InteractionAction(str, Enum):
    RESPOND_DIRECTLY = "RESPOND_DIRECTLY"
    REQUEST_CAPABILITY = "REQUEST_CAPABILITY"


class InteractionDecision(BaseModel):
    """Model-proposed intent; discovery and execution remain system-owned."""

    action: InteractionAction
    capability_query: str | None = None
    capability_input: str | None = None

    @field_validator("capability_query", "capability_input", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def require_capability_query(self) -> "InteractionDecision":
        if self.action is InteractionAction.REQUEST_CAPABILITY and self.capability_query is None:
            raise ValueError("REQUEST_CAPABILITY requires capability_query")
        return self


class InteractionStage(str, Enum):
    RESOLVE_REFERENCES = "RESOLVE_REFERENCES"
    SELECT_CAPABILITY = "SELECT_CAPABILITY"
    EXECUTE_CAPABILITY = "EXECUTE_CAPABILITY"
    RESPOND = "RESPOND"
    PERSIST_RESULT = "PERSIST_RESULT"

    @property
    def capability(self) -> str:
        return {
            InteractionStage.RESOLVE_REFERENCES: INTERACTION_CAPABILITIES[0],
            InteractionStage.SELECT_CAPABILITY: INTERACTION_CAPABILITIES[1],
            InteractionStage.EXECUTE_CAPABILITY: INTERACTION_CAPABILITIES[2],
            InteractionStage.RESPOND: INTERACTION_CAPABILITIES[3],
            InteractionStage.PERSIST_RESULT: INTERACTION_CAPABILITIES[4],
        }[self]


INTERACTION_STAGES = tuple(InteractionStage)


class ReferenceAnalysis(BaseModel):
    """Continuity signal with a temporary compatibility field.

    ``requires_persisted_context`` is retained only so pre-pivot worker payloads
    and tests remain readable. Live phrase detection is disabled; new code should
    set ``working_state_available`` from durable WorkingState instead.
    """

    policy_version: str = CONTINUITY_POLICY_VERSION
    working_state_available: bool = False
    requires_persisted_context: bool | None = None

    @model_validator(mode="after")
    def accept_legacy_signal(self) -> "ReferenceAnalysis":
        if self.requires_persisted_context is not None and not self.working_state_available:
            self.working_state_available = self.requires_persisted_context
        return self


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
    """Deprecated compatibility hook; phrase-based continuity is disabled."""

    del user_text
    return False


def apply_continuity_policy(
    user_text: str,
    decision: InteractionDecision,
    analysis: ReferenceAnalysis,
) -> tuple[InteractionDecision, str | None]:
    """Use durable active state rather than surface wording as continuity signal."""

    if not analysis.working_state_available:
        return decision, None
    normalized_capability_query = re.sub(r"[_-]+", " ", decision.capability_query or "")
    requests_memory = (
        decision.action is InteractionAction.REQUEST_CAPABILITY
        and _MEMORY_CAPABILITY_PATTERN.search(normalized_capability_query) is not None
    )
    if (
        decision.action is InteractionAction.REQUEST_CAPABILITY
        and not requests_memory
        and _EXPLICIT_CAPABILITY_REQUEST_PATTERN.search(user_text)
    ):
        return decision, None
    if requests_memory:
        return decision, CONTINUITY_POLICY_VERSION
    return (
        InteractionDecision(
            action=InteractionAction.REQUEST_CAPABILITY,
            capability_query="internal_memory",
        ),
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
