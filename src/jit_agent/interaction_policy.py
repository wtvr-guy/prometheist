"""Reusable deterministic interaction policy for the attention-centric path."""
from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, model_validator


INTERACTION_PROTOCOL_VERSION = "v0.7-interaction-v4"
CONTINUITY_POLICY_VERSION = "ACTIVE_WORKING_STATE_REQUIRES_MEMORY_V2"
INTERACTION_CAPABILITIES = (
    "interaction.resolve_references",
    "capability.discover",
    "capability.execute",
    "interaction.respond",
    "interaction.persist_result",
)


class InteractionAction(str, Enum):
    """Derived compatibility view of the categorical capability requirement."""

    RESPOND_DIRECTLY = "RESPOND_DIRECTLY"
    REQUEST_CAPABILITY = "REQUEST_CAPABILITY"


class CapabilityRequirement(str, Enum):
    """Finite functionality classes the interaction model may request."""

    NONE = "NONE"
    INTERNAL_MEMORY = "INTERNAL_MEMORY"
    MEMORY_ANALYSIS = "MEMORY_ANALYSIS"

    @property
    def capability_id(self) -> str | None:
        return {
            CapabilityRequirement.NONE: None,
            CapabilityRequirement.INTERNAL_MEMORY: "internal_memory",
            CapabilityRequirement.MEMORY_ANALYSIS: "memory_analysis",
        }[self]


class InteractionDecision(BaseModel):
    """Constrained model-proposed routing intent.

    The model chooses one enum only. It never writes a capability query,
    capability id, or natural-language capability input.
    """

    required_capability: CapabilityRequirement = CapabilityRequirement.NONE

    @property
    def action(self) -> InteractionAction:
        if self.required_capability is CapabilityRequirement.NONE:
            return InteractionAction.RESPOND_DIRECTLY
        return InteractionAction.REQUEST_CAPABILITY

    @property
    def capability_id(self) -> str | None:
        return self.required_capability.capability_id


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

    del user_text
    if not analysis.working_state_available:
        return decision, None
    if decision.required_capability is not CapabilityRequirement.NONE:
        return decision, CONTINUITY_POLICY_VERSION
    return (
        InteractionDecision(required_capability=CapabilityRequirement.INTERNAL_MEMORY),
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