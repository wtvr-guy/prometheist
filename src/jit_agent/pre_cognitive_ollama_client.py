"""Demand-driven Ollama adapter for specialized ephemeral pre-cognition.

The fast path invokes exactly one semantic LLM station: evidence sufficiency.
Only when that station returns INSUFFICIENT and a legal catalog exists does a
second specialist select capability indices. When insufficiency would otherwise
be terminal because no useful capability was selected, one fresh bounded
confirmation pass must agree before Prometheist abstains. Deterministic
application code then derives disposition/evidence state and constructs the
durable ``PreCognitiveAssessment``.

Descriptive assessment fields that are not currently required for acquisition or
response-boundary enforcement remain neutral rather than forcing unnecessary LLM
stations onto every interaction.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.interaction_policy import CapabilityResultSummary
from jit_agent.models import MemoryPacket
from jit_agent.pre_cognitive_specialists import (
    CapabilitySelectionDecision,
    EvidenceSufficiency,
    EvidenceSufficiencyDecision,
    _CAPABILITY_SELECTOR_SYSTEM_PROMPT,
    _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT,
)
from jit_agent.pre_cognitive_workers import (
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    IntentMode,
    PreCognitiveAssessment,
    _format_capability_result_data,
    _format_catalog,
    _format_completed_results,
    _format_memory_for_cognition,
)


_SET_LIKE_FIELDS_BY_SCHEMA = {
    "CapabilitySelectionDecision": ("capability_indices",),
}
_TERMINAL_INSUFFICIENCY_CONFIRMATION_SYSTEM_PROMPT = (
    _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT
    + "\n\nThis is a fresh bounded confirmation pass used only because an earlier "
    "independent sufficiency pass returned INSUFFICIENT and no legal capability "
    "was selected to add useful evidence. Re-evaluate the supplied material from "
    "scratch. Do not preserve the earlier verdict merely for consistency. If every "
    "answer component requested by the current percept is already present or "
    "directly derivable from the supplied material, return SUFFICIENT. A historical "
    "source statement itself is valid support; the evidence does not need to be a "
    "previously phrased answer to the current question. Return INSUFFICIENT only if "
    "a required answer component is still absent or genuinely unresolved."
)


def _dedupe_preserving_order(values: list[Any]) -> list[Any]:
    canonical: list[Any] = []
    for value in values:
        if value not in canonical:
            canonical.append(value)
    return canonical


def canonicalize_specialist_payload(payload: Any, schema_name: str) -> Any:
    """Remove exact duplicate members only from registered set-like fields."""

    if not isinstance(payload, dict):
        return payload
    canonical = dict(payload)
    for field in _SET_LIKE_FIELDS_BY_SCHEMA.get(schema_name, ()):
        values = canonical.get(field)
        if isinstance(values, list):
            canonical[field] = _dedupe_preserving_order(values)
    return canonical


class PreCognitiveDurableResponseOllamaClient(DurableResponseBudgetedOllamaClient):
    """Production Ollama client implementing conditional specialist stations."""

    def _specialist(
        self,
        role: str,
        system_prompt: str,
        user: str,
        schema: Any,
    ) -> Any:
        last_error: Exception | None = None
        for token_cap in (96, 192):
            try:
                content = self._structured(
                    role,
                    system_prompt,
                    user,
                    schema.model_json_schema(),
                    token_cap,
                )
                payload = canonicalize_specialist_payload(
                    json.loads(content),
                    schema.__name__,
                )
                return schema.model_validate(payload)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"{role} specialist failed to validate: {last_error}")

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
        evidence_context = (
            f"phase: {phase.value}\n"
            f"[Current percept]\n{prompt}"
            + _format_memory_for_cognition(memory_packet)
            + _format_completed_results(completed_results)
            + _format_capability_result_data(capability_results)
        )

        sufficiency = self._specialist(
            f"PRE_COGNITIVE_{phase.value}_EVIDENCE_SUFFICIENCY",
            _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT,
            evidence_context,
            EvidenceSufficiencyDecision,
        )

        capability_indices: list[int] = []
        if (
            sufficiency.sufficiency is EvidenceSufficiency.INSUFFICIENT
            and capability_catalog
        ):
            selection = self._specialist(
                f"PRE_COGNITIVE_{phase.value}_CAPABILITY_SELECTION",
                _CAPABILITY_SELECTOR_SYSTEM_PROMPT,
                evidence_context + _format_catalog(capability_catalog),
                CapabilitySelectionDecision,
            )
            selection.validate_catalog(capability_catalog)
            capability_indices = list(selection.capability_indices)

        if (
            sufficiency.sufficiency is EvidenceSufficiency.INSUFFICIENT
            and not capability_indices
        ):
            sufficiency = self._specialist(
                f"PRE_COGNITIVE_{phase.value}_EVIDENCE_SUFFICIENCY_CONFIRMATION",
                _TERMINAL_INSUFFICIENCY_CONFIRMATION_SYSTEM_PROMPT,
                evidence_context,
                EvidenceSufficiencyDecision,
            )

        if sufficiency.sufficiency is EvidenceSufficiency.SUFFICIENT:
            disposition = CognitiveDisposition.RESPOND
            evidence_state = (
                EvidenceState.ACTIVATED_MEMORY_SUFFICIENT
                if memory_packet.items
                else EvidenceState.CURRENT_INPUT_SUFFICIENT
            )
            capability_indices = []
        elif capability_indices:
            disposition = CognitiveDisposition.ACQUIRE_CAPABILITIES
            evidence_state = EvidenceState.MORE_INTERNAL_EVIDENCE_REQUIRED
        else:
            disposition = CognitiveDisposition.ABSTAIN
            evidence_state = EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK

        assessment = PreCognitiveAssessment(
            phase=phase,
            disposition=disposition,
            intent_mode=IntentMode.OTHER,
            evidence_state=evidence_state,
            claim_scopes=[],
            requirement_flags=[],
            capability_indices=capability_indices,
        )
        assessment.validate_catalog(capability_catalog)
        return assessment
