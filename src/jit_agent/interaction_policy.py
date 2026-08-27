"""Reusable deterministic interaction policy for the attention-centric path."""
from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


INTERACTION_PROTOCOL_VERSION = "v0.7-interaction-v6"
CONTINUITY_POLICY_VERSION = "ATTENTION_APERTURE_V1"
INTERACTION_CAPABILITIES = (
    "interaction.resolve_references",
    "capability.discover",
    "capability.execute",
    "interaction.respond",
    "interaction.persist_result",
)
_MAX_SELECTED_CAPABILITIES = 4
_MAX_CAPABILITY_CATALOG_INDEX = 63


class InteractionAction(str, Enum):
    """Derived view of the post-aperture routing decision."""

    RESPOND_DIRECTLY = "RESPOND_DIRECTLY"
    REQUEST_CAPABILITIES = "REQUEST_CAPABILITIES"


class InteractionDecision(BaseModel):
    """Constrained post-aperture routing intent.

    The model never writes a capability name, query, entity, explanation, or
    other natural-language control value. It receives an application-owned
    deterministic catalog and may select zero or more entries by integer index.

    An empty selection means "respond now." A non-empty selection means "invoke
    these capabilities before responding." Order is preserved so future
    capability dependencies can be represented without free-form planning text.
    """

    model_config = ConfigDict(extra="forbid")
    capability_indices: list[int] = Field(
        default_factory=list,
        max_length=_MAX_SELECTED_CAPABILITIES,
    )

    @field_validator("capability_indices")
    @classmethod
    def validate_capability_indices(cls, values: list[int]) -> list[int]:
        if any(index < 0 or index > _MAX_CAPABILITY_CATALOG_INDEX for index in values):
            raise ValueError("capability_indices must be between 0 and 63")
        if len(values) != len(set(values)):
            raise ValueError("capability_indices must not contain duplicates")
        return values

    @property
    def action(self) -> InteractionAction:
        if not self.capability_indices:
            return InteractionAction.RESPOND_DIRECTLY
        return InteractionAction.REQUEST_CAPABILITIES


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
    """Bounded durable-state signal retained for stage compatibility.

    ``requires_persisted_context`` is retained only so pre-pivot worker payloads
    and tests remain readable. Live phrase detection is disabled; every percept
    receives an attention aperture independently of this flag.
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


def requires_persisted_context(user_text: str) -> bool:
    """Deprecated compatibility hook; phrase-based continuity is disabled."""

    del user_text
    return False


def apply_continuity_policy(
    user_text: str,
    decision: InteractionDecision,
    analysis: ReferenceAnalysis,
) -> tuple[InteractionDecision, str | None]:
    """Deprecated no-op retained for readable pre-aperture tests/payloads."""

    del user_text, analysis
    return decision, None


def deterministic_interaction_id(conversation_id: UUID, correlation_id: UUID) -> UUID:
    return uuid5(conversation_id, f"interaction:{correlation_id}")


def deterministic_interaction_task_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "attention-task")


def deterministic_interaction_event_id(interaction_id: UUID, role: str) -> UUID:
    return uuid5(interaction_id, f"event:{role}")


def deterministic_memory_request_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "memory-request")


def deterministic_capability_memory_request_id(
    interaction_id: UUID,
    catalog_index: int,
    capability_id: str,
) -> UUID:
    if catalog_index < 0:
        raise ValueError("catalog_index must be >= 0")
    normalized = capability_id.strip()
    if not normalized:
        raise ValueError("capability_id must not be empty")
    return uuid5(
        interaction_id,
        f"capability-memory-request:{catalog_index}:{normalized}",
    )


def deterministic_aperture_request_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "attention-aperture-memory-request")
