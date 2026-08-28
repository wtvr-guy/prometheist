"""Atomic contracts for demand-driven pre-cognitive specialist workers.

The production acquisition path has only two LLM-powered semantic stations:
1. evidence sufficiency; and
2. capability selection, invoked only after insufficiency is established.

No specialist can authorize a response, execute work, or author the aggregate
``PreCognitiveAssessment``. Deterministic application code derives the control
state from the specialists' closed outputs.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jit_agent.capability_registry import CapabilityDescriptor


class EvidenceSufficiency(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceSufficiencyDecision(BaseModel):
    """Whether the supplied percept/evidence can support the requested answer."""

    model_config = ConfigDict(extra="forbid")
    sufficiency: EvidenceSufficiency


class CapabilitySelectionDecision(BaseModel):
    """Application-catalog indices that could close an established evidence gap."""

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


_EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist evidence-sufficiency specialist. Your sole
responsibility is to decide whether the current percept together with the exact
supplied activated evidence and completed capability results contains enough
support to answer the user's requested task without inventing facts.

Return SUFFICIENT when the requested factual values, identifiers, relationships,
or other necessary answer components are directly present, directly derivable
from the supplied material, or when the task can be answered from the current
percept without additional internal evidence. Exact opaque identifiers and tokens
present in admitted evidence count as support. Return INSUFFICIENT when a required
answer component is absent or genuinely unresolved.

Do not classify intent or source scope, infer auxiliary metadata, select
capabilities, plan work, decide RESPOND/ABSTAIN, or draft an answer. Return only
the EvidenceSufficiencyDecision schema.
"""

_CAPABILITY_SELECTOR_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist capability-selection specialist. A
separate evidence specialist has already determined that the currently supplied
material is insufficient. Your sole responsibility is to select the smallest set
of indices from the supplied application-owned capability catalog whose work
could materially close the remaining evidence/result gap. Return an empty list
when none of the supplied capabilities can do so.

Do not reassess evidence sufficiency, classify intent or source scope, author
capability names or queries, decide response readiness, plan execution order,
call tools, or draft an answer. Return only the CapabilitySelectionDecision
schema.
"""
