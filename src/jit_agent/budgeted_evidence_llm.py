"""Production Ollama client with fail-closed model-facing evidence bounds."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.evidence_bound_llm import (
    EvidenceBoundOllamaClient,
    _base_text_max_tokens,
    _quarantined_evidence,
)
from jit_agent.interaction_policy import CapabilityResultSummary, InteractionDecision
from jit_agent.llm import _retry_token_caps
from jit_agent.model_evidence_budget import (
    configured_model_evidence_budget,
    memory_packet_content_bytes,
    validate_capability_result_content,
    validate_memory_packet_content,
    validate_rendered_evidence,
)
from jit_agent.models import (
    CrossReferenceCandidateSelection,
    FocusedMemoryCandidateSelection,
    MemoryCandidateSelection,
    MemoryPacket,
)
from jit_agent.response_policy import (
    CurrentFallbackSelection,
    ResponsePolicy,
    validate_current_literal,
)


_GENERIC_INSUFFICIENT_RESPONSE = "Persisted evidence is insufficient."
_CURRENT_FALLBACK_SELECTION_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist current-fallback selector. You receive
only the current user message and no retrieved memory, prior transcript,
capability result, or historical model output.

Your only task is to identify an explicit literal that the CURRENT message says
must be returned specifically when required historical evidence is absent or
unsupported. Select the consequence of the no-evidence condition, not text that
names an evidence source, event type, field, format, or restriction.

For example:
- "Use SOURCE_ALPHA only; if no qualifying evidence exists, return NO_DATA."
  selects NO_DATA, not SOURCE_ALPHA.
- "Use SOURCE_ALPHA only; otherwise answer UNKNOWN."
  selects UNKNOWN, not SOURCE_ALPHA.
- "Use SOURCE_ALPHA only."
  has no explicit fallback and selects null.

If the current message explicitly supplies such a fallback literal, copy that
literal verbatim into verbatim_value. Preserve its spelling, case, spacing, and
internal punctuation. Do not include sentence punctuation that merely terminates
the instruction unless the message clearly makes that punctuation part of the
literal itself.

If the current message does not explicitly supply such a fallback literal,
return null for verbatim_value. Never invent, normalize, paraphrase, or infer a
fallback that does not occur verbatim in the current message.
"""


class BudgetedEvidenceBoundOllamaClient(EvidenceBoundOllamaClient):
    """Evidence-bound Ollama transport with bounded disposable evidence payloads.

    Canonical memory is never truncated here. An invocation that cannot represent
    its selected evidence inside the configured safety budget fails closed before
    model inference. Future chunking/summarization mechanisms may provide a
    different bounded derived view, but they must preserve canonical provenance.
    """

    def _validate_evidence_inputs(
        self,
        packet: MemoryPacket | None,
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> None:
        budget = configured_model_evidence_budget()
        validate_memory_packet_content(packet, budget=budget)
        validate_capability_result_content(
            capability_results,
            budget=budget,
            prior_evidence_bytes=memory_packet_content_bytes(packet),
        )

    def _structured_with_evidence(
        self,
        kind: str,
        system: str,
        current_user: str,
        evidence: str,
        schema: dict,
        max_tokens: int,
    ) -> str:
        validate_rendered_evidence(
            (evidence,),
            budget=configured_model_evidence_budget(),
        )
        return super()._structured_with_evidence(
            kind,
            system,
            current_user,
            evidence,
            schema,
            max_tokens,
        )

    def _response_policy(self, prompt: str) -> ResponsePolicy:
        """Keep source/surface classification separate from fallback selection.

        The base response-policy schema still carries the legacy optional fallback
        field for compatibility, but production response execution deliberately
        strips it. Unsupported-history fallback semantics belong exclusively to
        the focused current-percept-only selector below, so two model calls cannot
        independently control the same application consequence.
        """

        policy = super()._response_policy(prompt)
        return policy.model_copy(update={"insufficient_literal": None})

    def _select_current_fallback_literal(self, prompt: str) -> str | None:
        """Select an explicit no-support literal from current authority only.

        This is intentionally separate from the broad response-policy classifier.
        The model may identify the semantic span, but application code accepts it
        only when it is a verbatim substring of the current user percept.
        """

        for token_cap in _retry_token_caps(_base_text_max_tokens()):
            try:
                content = self._structured_with_evidence(
                    "CURRENT_FALLBACK_SELECTION",
                    _CURRENT_FALLBACK_SELECTION_SYSTEM_PROMPT,
                    prompt,
                    _quarantined_evidence(),
                    CurrentFallbackSelection.model_json_schema(),
                    token_cap,
                )
                selection = CurrentFallbackSelection.model_validate_json(content)
                return validate_current_literal(prompt, selection.verbatim_value)
            except (ValidationError, ValueError):
                continue
        return None

    def classify(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        completed_results: tuple[CapabilityResultSummary, ...] = (),
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> InteractionDecision:
        self._validate_evidence_inputs(memory_packet, capability_results)
        return super().classify(
            prompt,
            memory_packet,
            capability_catalog,
            completed_results,
            capability_results,
        )

    def respond(
        self,
        prompt: str,
        memory_packet: MemoryPacket | None,
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> str:
        self._validate_evidence_inputs(memory_packet, capability_results)
        answer = super().respond(prompt, memory_packet, capability_results)
        if answer != _GENERIC_INSUFFICIENT_RESPONSE:
            return answer
        fallback = self._select_current_fallback_literal(prompt)
        return fallback or answer

    def select_research_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> MemoryCandidateSelection:
        self._validate_evidence_inputs(packet)
        return super().select_research_candidates(task, packet)

    def select_cross_reference_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> CrossReferenceCandidateSelection:
        self._validate_evidence_inputs(packet)
        return super().select_cross_reference_candidates(task, packet)

    def select_focused_candidate(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> FocusedMemoryCandidateSelection:
        self._validate_evidence_inputs(packet)
        return super().select_focused_candidate(task, packet)
