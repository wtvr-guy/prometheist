from __future__ import annotations

from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.response_policy import HistoricalEvidenceScope, ResponseSurfaceMode


class _FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message": {
                "content": (
                    '{"evidence_scope":"USER_AUTHORED",'
                    '"surface_mode":"NATURAL_LANGUAGE",'
                    '"insufficient_literal":"INSUFFICIENT"}'
                )
            }
        }


class _FakeHTTPClient:
    def __init__(self):
        self.calls = []

    def post(self, path, *, json):
        self.calls.append((path, json))
        return _FakeResponse()


def test_successful_response_policy_is_published_to_application_sink():
    published = []
    client = DurableResponseBudgetedOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
        response_policy_sink=published.append,
    )
    fake_http = _FakeHTTPClient()
    client._client = fake_http

    policy = client._response_policy(
        "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT."
    )

    assert published == [policy]
    assert policy.evidence_scope is HistoricalEvidenceScope.USER_AUTHORED
    assert policy.surface_mode is ResponseSurfaceMode.NATURAL_LANGUAGE
    assert policy.insufficient_literal == "INSUFFICIENT"
    assert len(fake_http.calls) == 1
    messages = fake_http.calls[0][1]["messages"]
    assert "Favorite color?" in messages[2]["content"]
    assert "retrieved memory" not in messages[2]["content"].casefold()
