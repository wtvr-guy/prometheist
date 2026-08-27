"""Production response client with application-owned durable policy provenance."""
from __future__ import annotations

from collections.abc import Callable

from jit_agent.budgeted_evidence_llm import BudgetedEvidenceBoundOllamaClient
from jit_agent.response_policy import ResponsePolicy


ResponsePolicySink = Callable[[ResponsePolicy], None]


class DurableResponseBudgetedOllamaClient(BudgetedEvidenceBoundOllamaClient):
    """Budgeted evidence client that publishes each successful response policy.

    The sink is application-owned and supplied by the worker entry point. The
    LLM adapter never receives a database connection or persistence capability;
    it can only report the constrained policy it actually selected.
    """

    def __init__(
        self,
        *args,
        response_policy_sink: ResponsePolicySink | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._response_policy_sink = response_policy_sink

    def _response_policy(self, prompt: str) -> ResponsePolicy:
        policy = super()._response_policy(prompt)
        if self._response_policy_sink is not None:
            self._response_policy_sink(policy)
        return policy
