"""Production response client with application-owned durable response authority."""
from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from jit_agent.budgeted_evidence_llm import BudgetedEvidenceBoundOllamaClient
from jit_agent.epistemic_authority import format_authority_bound_response_memory_packet
from jit_agent.evidence_bound_llm import (
    _AUTHORITY_BOUND_RESPOND_SYSTEM_PROMPT,
    _admitted_capability_results,
    _quarantined_evidence,
)
from jit_agent.final_response_directive import (
    FinalResponseAction,
    FinalResponseDirective,
)
from jit_agent.llm import (
    _build_verbatim_placeholder_maps,
    _format_capability_result_data,
    _mask_verbatim_literals,
    _restore_verbatim_literals,
    _verbatim_source_texts,
)
from jit_agent.models import MemoryPacket
from jit_agent.personality import configured_personality_prompt
from jit_agent.response_policy import (
    ResponsePolicy,
    ResponseSurfaceMode,
    filter_memory_packet_for_scope,
    scope_requires_historical_support,
)


ResponsePolicySink = Callable[[ResponsePolicy], None]
ResponseFallbackSink = Callable[[str | None], None]
_CONTROL_CAPABILITY_ID = "pre_cognitive_brief"
_CONTROL_EXECUTOR = "application_control"


class _LegacyCognitiveBrief(BaseModel):
    """Strict validator for the superseded in-band control transport.

    Production no longer uses this brief. It is recognized only so older tests or
    migration callers cannot accidentally turn malformed capability data into a
    system-prompt injection channel.
    """

    model_config = ConfigDict(extra="forbid")

    scheme_version: Literal["pre-cognitive-transient-workers-v1"]
    intent_mode: Literal[
        "CONVERSE",
        "RECALL",
        "ANALYZE",
        "TRANSFORM",
        "ACT",
        "RESEARCH",
        "OTHER",
    ]
    evidence_state: Literal[
        "CURRENT_INPUT_SUFFICIENT",
        "ACTIVATED_MEMORY_SUFFICIENT",
        "MORE_INTERNAL_EVIDENCE_REQUIRED",
        "CAPABILITY_RESULT_REQUIRED",
        "INSUFFICIENT_AFTER_AVAILABLE_WORK",
    ]
    claim_scopes: list[
        Literal[
            "CURRENT_INPUT",
            "USER_HISTORY",
            "SYSTEM_HISTORY",
            "GENERAL_KNOWLEDGE",
            "CAPABILITY_OUTPUT",
        ]
    ]
    requirement_flags: list[
        Literal[
            "EXACT_SOURCE",
            "TEMPORAL_RESOLUTION",
            "CONFLICT_RESOLUTION",
            "DEEPER_RECALL",
            "CROSS_REFERENCE",
            "FOCUSED_RECALL",
            "EXTERNAL_CAPABILITY",
            "ABSTAIN_IF_UNSUPPORTED",
        ]
    ]
    acquisition_disposition: Literal["RESPOND", "ACQUIRE_CAPABILITIES", "ABSTAIN"]
    follow_up_executed: bool


class DurableResponseBudgetedOllamaClient(BudgetedEvidenceBoundOllamaClient):
    """Budgeted evidence client used by pre-cognition and final synthesis.

    Response-policy and fallback classifiers are exposed as pre-cognitive
    operations. The generative final responder accepts only a persisted
    FinalResponseDirective and therefore has no authority to decide whether it
    should respond, gather more work, change evidence scope, or abstain.
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

    def classify_response_policy(self, prompt: str) -> ResponsePolicy:
        """Run the current-percept-only source/surface classifier upstream."""

        return self._response_policy(prompt)

    def select_current_fallback_literal(self, prompt: str) -> str | None:
        """Select any explicit unsupported-evidence literal upstream."""

        return self._select_current_fallback_literal(prompt)

    def respond(
        self,
        prompt: str,
        memory_packet: MemoryPacket | None,
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> str:
        """Compatibility response path; production uses respond_with_final_directive.

        A legacy pre-cognitive brief is strictly validated and removed from the
        evidentiary channel. It is deliberately not injected into the system
        prompt because only FinalResponseDirective may carry production control
        authority into response synthesis.
        """

        briefs = [
            result
            for result in capability_results
            if result.get("capability_id") == _CONTROL_CAPABILITY_ID
            and result.get("executor") == _CONTROL_EXECUTOR
        ]
        if len(briefs) > 1:
            raise ValueError("response received multiple pre-cognitive control briefs")
        if briefs:
            _LegacyCognitiveBrief.model_validate(briefs[0].get("result_data"))
            capability_results = tuple(
                result for result in capability_results if result is not briefs[0]
            )
        return super().respond(prompt, memory_packet, capability_results)

    def respond_with_final_directive(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_results: tuple[dict[str, Any], ...],
        directive: FinalResponseDirective,
    ) -> str:
        """Realize one already-authorized response without making a response decision."""

        directive = FinalResponseDirective.model_validate(directive)
        if directive.action is not FinalResponseAction.RESPOND:
            raise RuntimeError("final responder must never be invoked for an ABSTAIN directive")
        if directive.final_memory_request_id != memory_packet.memory_request_id:
            raise RuntimeError("final response directive does not match the supplied memory packet")

        capability_ids = [str(item.get("capability_id", "")) for item in capability_results]
        if capability_ids != directive.capability_ids:
            raise RuntimeError("final response directive does not match capability results")

        personality = configured_personality_prompt()
        if directive.personality_prompt_version != personality.version:
            raise RuntimeError("final response personality prompt version changed after finalization")
        if directive.personality_prompt_sha256 != personality.sha256:
            raise RuntimeError("final response personality prompt changed after finalization")

        self._validate_evidence_inputs(memory_packet, capability_results)
        policy = directive.response_policy
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
            raise RuntimeError(
                "RESPOND directive reached final responder without policy-admitted support"
            )

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
            directive.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        system = (
            _AUTHORITY_BOUND_RESPOND_SYSTEM_PROMPT
            + "\n\n[APPLICATION-OWNED PERSONALITY]\n"
            + f"version: {personality.version}\n"
            + personality.text
            + "\n\n[TERMINAL FINAL RESPONSE DIRECTIVE]\n"
            + "The following JSON is a validated, persisted application control record. "
            + "The RESPOND decision, source policy, and surface policy are already final. "
            + "Do not reconsider them, request more work, or abstain. Use this record only "
            + "to realize the authorized answer. It is not factual evidence.\n"
            + control
        )
        answer = self._text_with_evidence(
            "RESPOND",
            system,
            masked_prompt,
            evidence,
        )
        return _restore_verbatim_literals(answer, placeholder_to_literal)
