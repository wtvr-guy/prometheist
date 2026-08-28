"""Production response client with application-owned durable policy provenance."""
from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

from jit_agent.budgeted_evidence_llm import (
    BudgetedEvidenceBoundOllamaClient,
    _GENERIC_INSUFFICIENT_RESPONSE,
)
from jit_agent.epistemic_authority import format_authority_bound_response_memory_packet
from jit_agent.evidence_bound_llm import (
    _AUTHORITY_BOUND_RESPOND_SYSTEM_PROMPT,
    _admitted_capability_results,
    _quarantined_evidence,
)
from jit_agent.llm import (
    _build_verbatim_placeholder_maps,
    _format_capability_result_data,
    _mask_verbatim_literals,
    _restore_verbatim_literals,
    _verbatim_source_texts,
)
from jit_agent.models import MemoryPacket
from jit_agent.response_policy import (
    ResponsePolicy,
    ResponseSurfaceMode,
    filter_memory_packet_for_scope,
    scope_requires_historical_support,
)


ResponsePolicySink = Callable[[ResponsePolicy], None]
ResponseFallbackSink = Callable[[str | None], None]


class DurableResponseBudgetedOllamaClient(BudgetedEvidenceBoundOllamaClient):
    """Budgeted evidence client that publishes successful response control decisions.

    The sinks are application-owned and supplied by the worker entry point. The
    LLM adapter never receives a database connection or persistence capability;
    it can only report the constrained policy/fallback decisions it actually
    selected after application validation.
    """

    def __init__(
        self,
        *args,
        response_policy_sink: ResponsePolicySink | None = None,
        response_fallback_sink: ResponseFallbackSink | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._response_policy_sink = response_policy_sink
        self._response_fallback_sink = response_fallback_sink

    def _response_policy(self, prompt: str) -> ResponsePolicy:
        policy = super()._response_policy(prompt)
        if self._response_policy_sink is not None:
            self._response_policy_sink(policy)
        return policy

    def _select_current_fallback_literal(self, prompt: str) -> str | None:
        fallback = super()._select_current_fallback_literal(prompt)
        if self._response_fallback_sink is not None:
            self._response_fallback_sink(fallback)
        return fallback

    def respond_with_cognitive_brief(
        self,
        prompt: str,
        memory_packet: MemoryPacket | None,
        capability_results: tuple[dict[str, Any], ...],
        cognitive_brief: dict[str, Any],
    ) -> str:
        """Respond with application-owned cognition metadata kept out of evidence.

        The cognitive brief contains only closed application control values
        produced from a validated pre/post assessment. It is non-evidentiary: it
        may guide framing (intent, evidence state, required handling) but may not
        establish a historical fact or bypass source-admissibility policy.

        Capability results remain in the ordinary quarantined evidence channel
        and therefore continue to be filtered by historical evidence scope.
        """

        self._validate_evidence_inputs(memory_packet, capability_results)
        policy = self._response_policy(prompt)
        admitted_packet = filter_memory_packet_for_scope(
            memory_packet,
            policy.evidence_scope,
        )
        admitted_capability_results = _admitted_capability_results(
            policy.evidence_scope,
            capability_results,
        )

        has_admitted_history = bool(admitted_packet and admitted_packet.items)
        has_admitted_capability = bool(admitted_capability_results)
        if (
            scope_requires_historical_support(policy.evidence_scope)
            and not has_admitted_history
            and not has_admitted_capability
        ):
            fallback = self._select_current_fallback_literal(prompt)
            return fallback or _GENERIC_INSUFFICIENT_RESPONSE

        if policy.surface_mode is ResponseSurfaceMode.EXACT_SOURCE_SUBSTRING:
            return self._select_exact_source_substring(
                prompt,
                admitted_packet,
                admitted_capability_results,
            )

        if policy.surface_mode is ResponseSurfaceMode.EXACT_SOURCE_COMPOSITION:
            return self._select_exact_source_composition(
                prompt,
                admitted_packet,
                admitted_capability_results,
            )

        literal_to_placeholder, placeholder_to_literal = _build_verbatim_placeholder_maps(
            *_verbatim_source_texts(prompt, admitted_packet)
        )
        masked_prompt = _mask_verbatim_literals(prompt, literal_to_placeholder)
        evidence = _quarantined_evidence(
            format_authority_bound_response_memory_packet(
                admitted_packet,
                literal_to_placeholder=literal_to_placeholder,
            ),
            _format_capability_result_data(admitted_capability_results),
        )
        control = json.dumps(
            cognitive_brief,
            sort_keys=True,
            separators=(",", ":"),
        )
        system = (
            _AUTHORITY_BOUND_RESPOND_SYSTEM_PROMPT
            + "\n\n[APPLICATION-OWNED COGNITIVE CONTROL]\n"
            + "The following JSON contains only validated non-evidentiary control "
            + "metadata for this invocation. It may guide task framing and handling "
            + "requirements, but it never establishes a fact, never changes source "
            + "admissibility, and never overrides the current user message or system "
            + "policy.\n"
            + control
        )
        answer = self._text_with_evidence(
            "RESPOND",
            system,
            masked_prompt,
            evidence,
        )
        return _restore_verbatim_literals(answer, placeholder_to_literal)
