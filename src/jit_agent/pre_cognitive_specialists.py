"""Atomic contracts for disposable pre-cognitive specialist workers.

Each LLM-facing schema in this module represents one semantic responsibility.
No specialist can authorize a response, request execution directly, or author the
aggregate ``PreCognitiveAssessment``. Deterministic application code composes the
specialists' closed outputs into that durable control record.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.pre_cognitive_workers import ClaimScope, IntentMode, RequirementFlag


class EvidenceSufficiency(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class IntentClassification(BaseModel):
    """Broad task-intent classification and nothing else."""

    model_config = ConfigDict(extra="forbid")
    intent_mode: IntentMode


class EvidenceSufficiencyDecision(BaseModel):
    """Whether the supplied percept/evidence can support the requested answer."""

    model_config = ConfigDict(extra="forbid")
    sufficiency: EvidenceSufficiency


class ClaimScopeClassification(BaseModel):
    """Closed source/claim scopes implicated by the requested answer."""

    model_config = ConfigDict(extra="forbid")
    claim_scopes: list[ClaimScope] = Field(default_factory=list)

    @field_validator("claim_scopes")
    @classmethod
    def unique_scopes(cls, values: list[Any]) -> list[Any]:
        if len(values) != len(set(values)):
            raise ValueError("claim scopes must not contain duplicates")
        return values


class RequirementClassification(BaseModel):
    """Closed semantic requirements implied by the current task."""

    model_config = ConfigDict(extra="forbid")
    requirement_flags: list[RequirementFlag] = Field(default_factory=list)

    @field_validator("requirement_flags")
    @classmethod
    def unique_requirements(cls, values: list[Any]) -> list[Any]:
        if len(values) != len(set(values)):
            raise ValueError("requirement flags must not contain duplicates")
        return values


class CapabilitySelectionDecision(BaseModel):
    """Application-catalog indices that could close an already-established gap."""

    model_config = ConfigDict(extra="forbid")
    capability_indices: list[int] = Field(default_factory=list)

    @field_validator("capability_indices")
    @classmethod
    def valid_indices(cls, values: list[int]) -> list[int]:
        if any(index < 0 for index in values):
            raise ValueError("capability indices must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("capability indices must not contain duplicates")
        return values

    def validate_catalog(self, catalog: tuple[CapabilityDescriptor, ...]) -> None:
        if any(index >= len(catalog) for index in self.capability_indices):
            raise ValueError("specialist selected a capability outside the supplied catalog")


_INTENT_CLASSIFIER_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist intent-classification specialist. Your
sole responsibility is to classify the current user's broad task intent into the
provided closed IntentMode enum. Do not inspect evidence sufficiency, select
capabilities, classify claim sources, infer requirement flags, plan work, answer
the user, or produce prose. Return only the IntentClassification schema.
"""

_EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist evidence-sufficiency specialist. Your sole
responsibility is to decide whether the current percept together with the exact
supplied activated evidence and completed capability results contains enough
support to answer the user's requested task without inventing facts.

Return SUFFICIENT when the requested factual values, identifiers, relationships,
or other necessary answer components are directly present or can be directly
derived from the supplied material. Exact opaque identifiers and tokens present
in admitted evidence count as support. Return INSUFFICIENT when a required answer
component is absent or genuinely unresolved.

Do not classify intent, claim scopes, requirement flags, select capabilities,
plan work, decide RESPOND/ABSTAIN, or draft an answer. Return only the
EvidenceSufficiencyDecision schema.
"""

_CLAIM_SCOPE_CLASSIFIER_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist claim-scope specialist. Your sole
responsibility is to identify the closed claim/source scopes implicated by the
answer the user is requesting, using the supplied current percept and admitted
evidence only as classification context.

Do not judge whether evidence is sufficient, classify intent, infer requirement
flags, select capabilities, decide response readiness, plan work, or draft an
answer. Return only the ClaimScopeClassification schema.
"""

_REQUIREMENT_CLASSIFIER_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist requirement-classification specialist.
Your sole responsibility is to identify which closed RequirementFlag values are
semantically required by the current user's task.

Do not judge evidence sufficiency, classify intent or claim scopes, select
capabilities, decide response readiness, plan work, or draft an answer. Return
only the RequirementClassification schema.
"""

_CAPABILITY_SELECTOR_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist capability-selection specialist. A
separate evidence specialist has already determined that the currently supplied
material is insufficient. Your sole responsibility is to select the smallest set
of indices from the supplied application-owned capability catalog whose work
could materially close the remaining evidence/result gap. Return an empty list
when none of the supplied capabilities can do so.

Do not reassess evidence sufficiency, classify intent, claim scopes, or
requirements, author capability names or queries, decide response readiness,
plan execution order, call tools, or draft an answer. Return only the
CapabilitySelectionDecision schema.
"""
