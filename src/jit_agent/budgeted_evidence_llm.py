"""Production Ollama client with fail-closed model-facing evidence bounds."""
from __future__ import annotations

from typing import Any

from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.evidence_bound_llm import EvidenceBoundOllamaClient
from jit_agent.interaction_policy import CapabilityResultSummary, InteractionDecision
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
        return super().respond(prompt, memory_packet, capability_results)

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
