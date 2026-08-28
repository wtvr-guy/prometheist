"""Ollama client adapter for robust closed pre-cognitive control output.

Small local models can occasionally repeat a value inside a list even when the
semantic result is unambiguous. Claim scopes, requirement flags, and selected
capability indices are set-like control fields, so production canonicalizes only
exact duplicates before applying the strict Pydantic contract. Unknown values,
extra fields, invalid phases, illegal dispositions, and out-of-range indices
continue to fail closed.

A second native failure mode is a syntactically valid but internally inconsistent
sufficiency judgment. The adapter rejects impossible terminal-state pairings and,
when a model proposes terminal abstention despite a non-empty supported evidence
packet, permits one fresh narrow reconsideration call. The reconsideration does
not force a response or reinterpret evidence in deterministic code; it asks the
semantic worker to re-read the exact admitted evidence before terminal abstention
is accepted.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.interaction_policy import CapabilityResultSummary
from jit_agent.models import MemoryPacket
from jit_agent.pre_cognitive_workers import (
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    PreCognitiveAssessment,
    _PRE_COGNITIVE_SYSTEM_PROMPT,
    _format_capability_result_data,
    _format_catalog,
    _format_completed_results,
    _format_memory_for_cognition,
)


_SET_LIKE_ASSESSMENT_FIELDS = (
    "claim_scopes",
    "requirement_flags",
    "capability_indices",
)

_RECONSIDERATION_PROMPT = """\

[Terminal-abstention reconsideration]
Your prior assessment chose ABSTAIN even though the activated evidence packet is
non-empty and marked supported. Re-read the exact activated evidence literally.
Do not assume that supported means sufficient: ABSTAIN remains correct if those
items genuinely do not supply the facts or relationships the user requested and
no listed capability can resolve the gap. If the activated evidence already
contains the requested answer components, choose RESPOND with
ACTIVATED_MEMORY_SUFFICIENT and the appropriate claim scope(s). If evidence is
still insufficient but a listed capability could resolve the gap, choose
ACQUIRE_CAPABILITIES. Produce only the closed assessment.
"""


def _dedupe_preserving_order(values: list[Any]) -> list[Any]:
    canonical: list[Any] = []
    for value in values:
        if value not in canonical:
            canonical.append(value)
    return canonical


def canonicalize_pre_cognitive_payload(payload: Any) -> Any:
    """Remove only exact duplicate members from registered set-like fields."""

    if not isinstance(payload, dict):
        return payload
    canonical = dict(payload)
    for field in _SET_LIKE_ASSESSMENT_FIELDS:
        values = canonical.get(field)
        if isinstance(values, list):
            canonical[field] = _dedupe_preserving_order(values)
    return canonical


def validate_native_assessment_consistency(assessment: PreCognitiveAssessment) -> None:
    """Reject logically impossible terminal sufficiency/disposition pairings."""

    terminal_insufficient = (
        assessment.evidence_state is EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK
    )
    if terminal_insufficient and assessment.disposition is not CognitiveDisposition.ABSTAIN:
        raise ValueError(
            "INSUFFICIENT_AFTER_AVAILABLE_WORK requires terminal ABSTAIN disposition"
        )


def needs_supported_evidence_reconsideration(
    assessment: PreCognitiveAssessment,
    memory_packet: MemoryPacket,
) -> bool:
    """Return whether one semantic re-read is warranted before terminal abstention."""

    return bool(
        assessment.disposition is CognitiveDisposition.ABSTAIN
        and memory_packet.supported
        and memory_packet.items
    )


class PreCognitiveDurableResponseOllamaClient(DurableResponseBudgetedOllamaClient):
    """Production Ollama client with deterministic pre-validation canonicalization."""

    def _parse_assessment(
        self,
        content: str,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        *,
        phase: CognitivePhase,
    ) -> PreCognitiveAssessment:
        payload = canonicalize_pre_cognitive_payload(json.loads(content))
        assessment = PreCognitiveAssessment.model_validate(payload)
        if assessment.phase is not phase:
            raise ValueError("pre-cognitive assessment returned the wrong phase")
        assessment.validate_catalog(capability_catalog)
        validate_native_assessment_consistency(assessment)
        return assessment

    def assess_pre_cognition(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        *,
        phase: CognitivePhase,
        completed_results: tuple[CapabilityResultSummary, ...] = (),
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> PreCognitiveAssessment:
        user = (
            f"phase: {phase.value}\n"
            + prompt
            + _format_memory_for_cognition(memory_packet)
            + _format_completed_results(completed_results)
            + _format_capability_result_data(capability_results)
            + _format_catalog(capability_catalog)
        )
        last_error: Exception | None = None
        for token_cap in (96, 192):
            try:
                content = self._structured(
                    f"PRE_COGNITIVE_{phase.value}",
                    _PRE_COGNITIVE_SYSTEM_PROMPT,
                    user,
                    PreCognitiveAssessment.model_json_schema(),
                    token_cap,
                )
                assessment = self._parse_assessment(
                    content,
                    capability_catalog,
                    phase=phase,
                )
                if not needs_supported_evidence_reconsideration(
                    assessment,
                    memory_packet,
                ):
                    return assessment

                # One fresh semantic re-read only. The application does not
                # override the judgment; a second valid ABSTAIN is accepted.
                reconsidered_content = self._structured(
                    f"PRE_COGNITIVE_{phase.value}_RECONSIDER",
                    _PRE_COGNITIVE_SYSTEM_PROMPT,
                    user + _RECONSIDERATION_PROMPT,
                    PreCognitiveAssessment.model_json_schema(),
                    token_cap,
                )
                try:
                    return self._parse_assessment(
                        reconsidered_content,
                        capability_catalog,
                        phase=phase,
                    )
                except (json.JSONDecodeError, ValidationError, ValueError):
                    # The first assessment was valid. A malformed optional
                    # reconsideration must not convert safe abstention into an
                    # interaction crash.
                    return assessment
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"pre-cognitive assessment failed to validate: {last_error}")
