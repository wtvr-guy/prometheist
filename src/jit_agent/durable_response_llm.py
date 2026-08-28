"""Production response client with application-owned durable policy provenance."""
from __future__ import annotations

from collections.abc import Callable

from jit_agent.budgeted_evidence_llm import BudgetedEvidenceBoundOllamaClient
from jit_agent.response_policy import ResponsePolicy


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
