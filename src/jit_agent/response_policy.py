"""Application-enforced response evidence and surface-form policy.

The semantic policy is inferred from the current user percept only. Retrieved
memory is never shown to that classifier, so persisted text cannot influence
which historical source roles become admissible for final answer synthesis.
Canonical events are unchanged; filtering applies only to the disposable
model-facing packet for one stateless response invocation.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jit_agent.models import EventType, MemoryPacket


RESPONSE_POLICY_VERSION = "response-source-authority-v5"


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
    EXACT_SOURCE_COMPOSITION = "EXACT_SOURCE_COMPOSITION"


class ResponsePolicy(BaseModel):
    """Closed current-percept-only policy used before exposing historical evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_scope: HistoricalEvidenceScope
    surface_mode: ResponseSurfaceMode
    insufficient_literal: str | None = None
    allowed_output_literals: list[str] = Field(
        default_factory=list,
        description=(
            "When the current user message explicitly enumerates a finite closed set of "
            "legal exact final outputs, copy each complete allowed output literal verbatim "
            "in user-specified order. Otherwise return an empty list."
        ),
    )

    @model_validator(mode="after")
    def validate_literals(self) -> "ResponsePolicy":
        if self.insufficient_literal is not None and not self.insufficient_literal:
            raise ValueError("insufficient_literal must not be empty")
        if any(not literal for literal in self.allowed_output_literals):
            raise ValueError("allowed_output_literals must not contain empty values")
        if len(set(self.allowed_output_literals)) != len(self.allowed_output_literals):
            raise ValueError("allowed_output_literals must not contain duplicates")
        if (
            self.allowed_output_literals
            and self.surface_mode is not ResponseSurfaceMode.EXACT_SOURCE_SUBSTRING
        ):
            raise ValueError(
                "allowed_output_literals are only valid for EXACT_SOURCE_SUBSTRING"
            )
        return self


class CurrentFallbackSelection(BaseModel):
    """Focused selection of a verbatim unsupported-history fallback from the current percept."""

    model_config = ConfigDict(extra="forbid")

    verbatim_value: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "CurrentFallbackSelection":
        if self.verbatim_value is not None and not self.verbatim_value:
            raise ValueError("verbatim_value must not be empty")
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


class ExactSourceComposition(BaseModel):
    """Ordered source-backed values joined only by current-authority formatting."""

    model_config = ConfigDict(extra="forbid")

    selections: list[ExactSourceSelection]
    separator: str

    @model_validator(mode="after")
    def validate_structure(self) -> "ExactSourceComposition":
        if not self.selections:
            raise ValueError("exact-source composition requires at least one selection")
        if any(character.isalnum() for character in self.separator):
            raise ValueError("exact-source composition separator must be formatting-only")
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


def validate_response_policy_current_authority(
    prompt: str,
    policy: ResponsePolicy,
) -> ResponsePolicy:
    """Validate every response-policy literal against current user authority."""

    validate_current_literal(prompt, policy.insufficient_literal)
    for literal in policy.allowed_output_literals:
        if literal not in prompt:
            raise ValueError(
                "allowed_output_literal must be an exact substring of the current prompt"
            )
    return policy


def validate_exact_source_selection(
    packet: MemoryPacket,
    selection: ExactSourceSelection,
    *,
    allowed_output_literals: tuple[str, ...] = (),
) -> str:
    """Return the exact canonical substring selected from admitted evidence.

    The model selects semantics, but application code validates the source index
    and substring membership and returns source bytes rather than generated prose.
    When current authority enumerates a closed exact-output set, the selected
    source substring must also equal one complete allowed literal.
    """

    if selection.source_index not in range(len(packet.items)):
        raise ValueError("exact-source selection referenced an item outside the admitted packet")
    content = packet.items[selection.source_index].content
    if selection.verbatim_value not in content:
        raise ValueError("exact-source value is not a verbatim substring of admitted evidence")
    if allowed_output_literals and selection.verbatim_value not in allowed_output_literals:
        raise ValueError("exact-source value is not one of the current-authority allowed outputs")
    return selection.verbatim_value


def validate_exact_source_composition(
    prompt: str,
    source_texts: tuple[str, ...],
    composition: ExactSourceComposition,
) -> str:
    """Compose exact output from admitted source bytes plus trusted formatting.

    Every semantic value must be a verbatim substring of the admitted evidence
    candidate it names. The only generated glue is a formatting-only separator
    copied from the current user percept. This permits exact multi-field answers
    without allowing free-form synthesis or historical text to define the output
    contract.
    """

    if composition.separator and composition.separator not in prompt:
        raise ValueError("exact-source composition separator is not current-prompt text")

    values: list[str] = []
    for selection in composition.selections:
        if selection.source_index not in range(len(source_texts)):
            raise ValueError("exact-source composition referenced an unknown candidate")
        source_text = source_texts[selection.source_index]
        if selection.verbatim_value not in source_text:
            raise ValueError(
                "exact-source composition value is not a verbatim substring of admitted evidence"
            )
        values.append(selection.verbatim_value)

    return composition.separator.join(values)
