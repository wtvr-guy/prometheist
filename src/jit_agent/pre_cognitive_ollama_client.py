"""Ollama client adapter for robust closed pre-cognitive control output.

Small local models can occasionally repeat a value inside a list even when the
semantic result is unambiguous. Claim scopes, requirement flags, and selected
capability indices are set-like control fields, so production canonicalizes only
exact duplicates before applying the strict Pydantic contract. Unknown values,
extra fields, invalid phases, illegal dispositions, and out-of-range indices
continue to fail closed.
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
    CognitivePhase,
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


class PreCognitiveDurableResponseOllamaClient(DurableResponseBudgetedOllamaClient):
    """Production Ollama client with deterministic pre-validation canonicalization."""

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
                payload = canonicalize_pre_cognitive_payload(json.loads(content))
                assessment = PreCognitiveAssessment.model_validate(payload)
                if assessment.phase is not phase:
                    raise ValueError("pre-cognitive assessment returned the wrong phase")
                assessment.validate_catalog(capability_catalog)
                return assessment
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"pre-cognitive assessment failed to validate: {last_error}")
