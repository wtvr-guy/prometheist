"""Reusable deterministic interaction policy for the attention-centric path."""
from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator


INTERACTION_PROTOCOL_VERSION = "v0.7-interaction-v5"
CONTINUITY_POLICY_VERSION = "ATTENTION_APERTURE_V1"
INTERACTION_CAPABILITIES = (
    "interaction.resolve_references",
    "capability.discover",
    "capability.execute",
    "interaction.respond",
    "interaction.persist_result",
)


class InteractionAction(str, Enum):
    """Derived compatibility view of the post-aperture routing decision."""

    RESPOND_DIRECTLY = "RESPOND_DIRECTLY"
    REQUEST_CAPABILITY = "REQUEST_CAPABILITY"


class CapabilityRequirement(str, Enum):
    """Optional functionality a model may request after default memory exposure.

    Basic internal-memory access is intentionally absent. Every percept receives
    a bounded JIT Memory attention aperture before this decision is made. The
    model may only decide whether that default aperture is sufficient or whether
    focused memory analysis is warranted.
    """

    NONE = "NONE"
    MEMORY_ANALYSIS = "MEMORY_ANALYSIS"

    @property
    def capability_id(self) -> str | None:
        return {
            CapabilityRequirement.NONE: None,
            CapabilityRequirement.MEMORY_ANALYSIS: "memory_analysis",
        }[self]


class InteractionDecision(BaseModel):
    """Constrained post-aperture routing intent.

    The model chooses one enum only. It never writes a capability query,
    capability id, search query, entity, explanation, or other natural-language
    control value.
    """

    model_config = ConfigDict(extra="forbid")
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
    """Deprecated no-op retained for readable pre-aperture tests/payloads.

    Continuity is no longer implemented by rewriting a model decision. The
    interaction runtime opens a bounded memory aperture before the model makes
    this decision at all.
    """

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


def deterministic_aperture_request_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "attention-aperture-memory-request")
