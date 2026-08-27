"""Application-enforced response evidence and surface-form policy.

The semantic policy is inferred from the current user percept only. Retrieved
memory is never shown to that classifier, so persisted text cannot influence
which historical source roles become admissible for final answer synthesis.
Canonical events are unchanged; filtering applies only to the disposable
model-facing packet for one stateless response invocation.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

from jit_agent.models import EventType, MemoryPacket


RESPONSE_POLICY_VERSION = "response-source-authority-v1"


class HistoricalEvidenceScope(str, Enum):
    """The historical source role allowed to establish the requested claim."""

    USER_AUTHORED = "USER_AUTHORED"
    MODEL_OUTPUT = "MODEL_OUTPUT"
    EXTERNAL_TOOL = "EXTERNAL_TOOL"
    SYSTEM_RECORD = "SYSTEM_RECORD"
    DERIVED_INTERNAL = "DERIVED_INTERNAL"
    MIXED_CONVERSATION = "MIXED_CONVERSATION"
    GENERAL_OR_CURRENT = "GENERAL_OR_CURRENT"


class ResponseSurfaceMode(str, Enum):
    """Whether final text may be generated freely or must be source-extractive."""

    NATURAL_LANGUAGE = "NATURAL_LANGUAGE"
    EXACT_SOURCE_SUBSTRING = "EXACT_SOURCE_SUBSTRING"


class ResponsePolicy(BaseModel):
    """Closed current-percept-only policy used before exposing historical evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_scope: HistoricalEvidenceScope
    surface_mode: ResponseSurfaceMode
    insufficient_literal: str | None = None

    @model_validator(mode="after")
    def validate_insufficient_literal(self) -> "ResponsePolicy":
        if self.insufficient_literal is not None and not self.insufficient_literal:
            raise ValueError("insufficient_literal must not be empty")
        return self


class ExactSourceSelection(BaseModel):
    """Constrained semantic selection of one exact substring from admitted evidence."""

    model_config = ConfigDict(extra="forbid")

    source_index: int
    verbatim_value: str

    @model_validator(mode="after")
    def validate_value(self) -> "ExactSourceSelection":
        if not self.verbatim_value:
            raise ValueError("verbatim_value must not be empty")
        return self


_MODEL_OUTPUT_TYPES = frozenset(
    {
        EventType.INTERACTION_RESPONSE,
        EventType.AGENT_RESPONSE,
        EventType.AGENT_RESULT,
    }
)
_EXTERNAL_TOOL_TYPES = frozenset({EventType.TOOL_RESULT})
_SYSTEM_RECORD_TYPES = frozenset(
    {
        EventType.SYSTEM_EVENT,
        EventType.ERROR,
        EventType.INTERACTION_WORKING_STATE,
    }
)
_DERIVED_INTERNAL_TYPES = frozenset(
    {
        EventType.AGENT_DECISION,
        EventType.RETRIEVAL_REQUEST,
        EventType.RETRIEVAL_RESULT,
        EventType.MEMORY_REQUEST,
        EventType.MEMORY_PACKET,
        EventType.AGENT_DELEGATION,
        EventType.TOOL_REQUEST,
        EventType.CAPABILITY_REQUEST,
        EventType.CAPABILITY_PACKET,
        EventType.CAPABILITY_RESULT,
    }
)


def allowed_event_types(scope: HistoricalEvidenceScope) -> frozenset[EventType] | None:
    """Map semantic scope to application-owned canonical event admissibility."""

    if scope is HistoricalEvidenceScope.USER_AUTHORED:
        return frozenset({EventType.USER_PROMPT})
    if scope is HistoricalEvidenceScope.MODEL_OUTPUT:
        return _MODEL_OUTPUT_TYPES
    if scope is HistoricalEvidenceScope.EXTERNAL_TOOL:
        return _EXTERNAL_TOOL_TYPES
    if scope is HistoricalEvidenceScope.SYSTEM_RECORD:
        return _SYSTEM_RECORD_TYPES
    if scope is HistoricalEvidenceScope.DERIVED_INTERNAL:
        return _DERIVED_INTERNAL_TYPES
    if scope is HistoricalEvidenceScope.MIXED_CONVERSATION:
        return frozenset({EventType.USER_PROMPT}) | _MODEL_OUTPUT_TYPES
    if scope is HistoricalEvidenceScope.GENERAL_OR_CURRENT:
        return None
    raise ValueError(f"unsupported historical evidence scope: {scope.value}")


def filter_memory_packet_for_scope(
    packet: MemoryPacket | None,
    scope: HistoricalEvidenceScope,
) -> MemoryPacket | None:
    """Physically remove event roles that cannot establish the current claim."""

    if packet is None:
        return None
    allowed = allowed_event_types(scope)
    if allowed is None:
        return packet
    items = [item for item in packet.items if item.event_type in allowed]
    return packet.model_copy(update={"items": items, "supported": bool(items)})


def scope_requires_historical_support(scope: HistoricalEvidenceScope) -> bool:
    """Return whether absence of admitted history means the requested claim is unsupported."""

    return scope is not HistoricalEvidenceScope.GENERAL_OR_CURRENT


def validate_current_literal(prompt: str, literal: str | None) -> str | None:
    """Accept a model-selected fallback only when it is verbatim current-user text."""

    if literal is None:
        return None
    if literal not in prompt:
        raise ValueError("insufficient_literal must be an exact substring of the current prompt")
    return literal


def validate_exact_source_selection(
    packet: MemoryPacket,
    selection: ExactSourceSelection,
) -> str:
    """Return the exact canonical substring selected from admitted evidence.

    The model selects semantics, but application code validates the source index
    and substring membership and returns source bytes rather than generated prose.
    """

    if selection.source_index not in range(len(packet.items)):
        raise ValueError("exact-source selection referenced an item outside the admitted packet")
    content = packet.items[selection.source_index].content
    if selection.verbatim_value not in content:
        raise ValueError("exact-source value is not a verbatim substring of admitted evidence")
    return selection.verbatim_value
