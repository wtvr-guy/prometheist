"""Ollama adapter that composes pre-cognition from atomic transient specialists.

No LLM invocation authors the aggregate ``PreCognitiveAssessment``. Independent,
stateless specialists classify intent, evidence sufficiency, claim scope, task
requirements, and (only when needed) legal capability indices. Deterministic
application code then derives disposition/evidence state and builds the durable
assessment.

Set-like specialist outputs are canonicalized only for exact duplicate members
before strict Pydantic validation. Unknown enums, extra fields, malformed JSON,
invalid indices, and other contract violations continue to fail closed.
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
    ClaimScopeClassification,
    EvidenceSufficiency,
    EvidenceSufficiencyDecision,
    IntentClassification,
    RequirementClassification,
    _CAPABILITY_SELECTOR_SYSTEM_PROMPT,
    _CLAIM_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
    _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT,
    _INTENT_CLASSIFIER_SYSTEM_PROMPT,
    _REQUIREMENT_CLASSIFIER_SYSTEM_PROMPT,
)
from jit_agent.pre_cognitive_workers import (
    CognitiveDisposition,
    CognitivePhase,
    EvidenceState,
    PreCognitiveAssessment,
    _format_capability_result_data,
    _format_catalog,
    _format_completed_results,
    _format_memory_for_cognition,
)


_SET_LIKE_FIELDS_BY_SCHEMA = {
    "ClaimScopeClassification": ("claim_scopes",),
    "RequirementClassification": ("requirement_flags",),
    "CapabilitySelectionDecision": ("capability_indices",),
}


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
    """Production Ollama client implementing specialized ephemeral pre-cognition."""

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
        current_percept = f"[Current percept]\n{prompt}"
        evidence_context = (
            f"phase: {phase.value}\n"
            + current_percept
            + _format_memory_for_cognition(memory_packet)
            + _format_completed_results(completed_results)
            + _format_capability_result_data(capability_results)
        )

        intent = self._specialist(
            f"PRE_COGNITIVE_{phase.value}_INTENT",
            _INTENT_CLASSIFIER_SYSTEM_PROMPT,
            current_percept,
            IntentClassification,
        )
        sufficiency = self._specialist(
            f"PRE_COGNITIVE_{phase.value}_EVIDENCE_SUFFICIENCY",
            _EVIDENCE_SUFFICIENCY_SYSTEM_PROMPT,
            evidence_context,
            EvidenceSufficiencyDecision,
        )
        claim_scope = self._specialist(
            f"PRE_COGNITIVE_{phase.value}_CLAIM_SCOPE",
            _CLAIM_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
            evidence_context,
            ClaimScopeClassification,
        )
        requirements = self._specialist(
            f"PRE_COGNITIVE_{phase.value}_REQUIREMENTS",
            _REQUIREMENT_CLASSIFIER_SYSTEM_PROMPT,
            current_percept,
            RequirementClassification,
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
            intent_mode=intent.intent_mode,
            evidence_state=evidence_state,
            claim_scopes=list(claim_scope.claim_scopes),
            requirement_flags=list(requirements.requirement_flags),
            capability_indices=capability_indices,
        )
        assessment.validate_catalog(capability_catalog)
        return assessment
