"""Terminal application-owned contract between pre-cognition and response synthesis."""
from __future__ import annotations

from enum import Enum
import hashlib
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from jit_agent.response_policy import ResponsePolicy


FINAL_RESPONSE_DIRECTIVE_VERSION = "final-response-directive-v1"
FINAL_READINESS_VERSION = "final-readiness-v1"

IntentModeValue = Literal[
    "CONVERSE",
    "RECALL",
    "ANALYZE",
    "TRANSFORM",
    "ACT",
    "RESEARCH",
    "OTHER",
]
EvidenceStateValue = Literal[
    "CURRENT_INPUT_SUFFICIENT",
    "ACTIVATED_MEMORY_SUFFICIENT",
    "MORE_INTERNAL_EVIDENCE_REQUIRED",
    "CAPABILITY_RESULT_REQUIRED",
    "INSUFFICIENT_AFTER_AVAILABLE_WORK",
]
ClaimScopeValue = Literal[
    "CURRENT_INPUT",
    "USER_HISTORY",
    "SYSTEM_HISTORY",
    "GENERAL_KNOWLEDGE",
    "CAPABILITY_OUTPUT",
]
RequirementFlagValue = Literal[
    "EXACT_SOURCE",
    "TEMPORAL_RESOLUTION",
    "CONFLICT_RESOLUTION",
    "DEEPER_RECALL",
    "CROSS_REFERENCE",
    "FOCUSED_RECALL",
    "EXTERNAL_CAPABILITY",
    "ABSTAIN_IF_UNSUPPORTED",
]


class FinalResponseAction(str, Enum):
    RESPOND = "RESPOND"
    ABSTAIN = "ABSTAIN"


class FinalAbstainReason(str, Enum):
    PRE_COGNITIVE_INSUFFICIENT = "PRE_COGNITIVE_INSUFFICIENT"
    SOURCE_POLICY_UNSUPPORTED = "SOURCE_POLICY_UNSUPPORTED"


class FinalReadinessDecision(BaseModel):
    """Closed terminal cognition result used only after additional work has ended.

    ``version`` is application-owned protocol metadata. It remains part of the
    validated/persisted object for restart compatibility, but is intentionally
    omitted from the model-facing JSON Schema so a stateless LLM is never asked
    to author or guess infrastructure versioning.
    """

    model_config = ConfigDict(extra="forbid")

    version: SkipJsonSchema[str] = FINAL_READINESS_VERSION
    action: FinalResponseAction
    evidence_state: EvidenceStateValue

    @model_validator(mode="after")
    def validate_terminal_state(self) -> "FinalReadinessDecision":
        if self.version != FINAL_READINESS_VERSION:
            raise ValueError("unsupported final readiness version")
        if (
            self.action is FinalResponseAction.ABSTAIN
            and self.evidence_state != "INSUFFICIENT_AFTER_AVAILABLE_WORK"
        ):
            raise ValueError("ABSTAIN requires terminal insufficient-evidence state")
        if self.action is FinalResponseAction.RESPOND and self.evidence_state in {
            "MORE_INTERNAL_EVIDENCE_REQUIRED",
        }:
            raise ValueError("RESPOND cannot leave unresolved internal evidence requirements")
        return self


class FinalResponseDirective(BaseModel):
    """Terminal, persisted authority handed to the final response stage.

    The response worker may realize language only when ``action`` is RESPOND. It
    must never reinterpret this object into a different respond/abstain decision.
    Closed enum element types plus duplicate rejection bound the classification
    lists by construction rather than by an independent numeric policy knob.
    """

    model_config = ConfigDict(extra="forbid")

    version: str = FINAL_RESPONSE_DIRECTIVE_VERSION
    action: FinalResponseAction
    abstain_reason: FinalAbstainReason | None = None
    intent_mode: IntentModeValue
    evidence_state: EvidenceStateValue
    claim_scopes: list[ClaimScopeValue] = Field(default_factory=list)
    requirement_flags: list[RequirementFlagValue] = Field(default_factory=list)
    response_policy: ResponsePolicy
    fallback_literal: str | None = None
    final_memory_request_id: UUID
    capability_ids: list[str] = Field(default_factory=list)
    follow_up_executed: bool = False
    personality_prompt_version: str = Field(min_length=1)
    personality_prompt_sha256: str

    @field_validator("claim_scopes", "requirement_flags", "capability_ids")
    @classmethod
    def unique_lists(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("final response directive lists must not contain duplicates")
        return values

    @field_validator("capability_ids")
    @classmethod
    def nonblank_capability_ids(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("capability_ids must not contain blanks")
        return values

    @field_validator("personality_prompt_sha256")
    @classmethod
    def validate_personality_digest(cls, value: str) -> str:
        normalized = value.casefold()
        expected_width = len(hashlib.sha256().hexdigest())
        if len(normalized) != expected_width:
            raise ValueError("personality_prompt_sha256 must be a SHA-256 hex digest")
        if any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("personality_prompt_sha256 must be lowercase hexadecimal")
        return normalized

    @model_validator(mode="after")
    def validate_terminal_contract(self) -> "FinalResponseDirective":
        if self.version != FINAL_RESPONSE_DIRECTIVE_VERSION:
            raise ValueError("unsupported final response directive version")
        if self.action is FinalResponseAction.RESPOND:
            if self.abstain_reason is not None:
                raise ValueError("RESPOND must not contain an abstain reason")
            if self.fallback_literal is not None:
                raise ValueError("RESPOND must not contain an abstain fallback literal")
        else:
            if self.abstain_reason is None:
                raise ValueError("ABSTAIN requires a closed abstain reason")
            if self.fallback_literal is not None and not self.fallback_literal:
                raise ValueError("fallback_literal must not be empty")
        return self
