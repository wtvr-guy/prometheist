from __future__ import annotations

from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.response_policy import HistoricalEvidenceScope, ResponseSurfaceMode


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


class _FakeHTTPClient:
    def __init__(self, contents: list[str]):
        self._contents = iter(contents)
        self.calls = []

    def post(self, path, *, json):
        self.calls.append((path, json))
        return _FakeResponse(next(self._contents))


def test_successful_response_policy_is_published_to_application_sink():
    published = []
    client = DurableResponseBudgetedOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
        response_policy_sink=published.append,
    )
    fake_http = _FakeHTTPClient(
        [
            (
                '{"evidence_scope":"USER_AUTHORED",'
                '"surface_mode":"NATURAL_LANGUAGE",'
                '"insufficient_literal":"USER_PROMPT"}'
            )
        ]
    )
    client._client = fake_http

    policy = client._response_policy(
        "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT."
    )

    assert published == [policy]
    assert policy.evidence_scope is HistoricalEvidenceScope.USER_AUTHORED
    assert policy.surface_mode is ResponseSurfaceMode.NATURAL_LANGUAGE
    assert policy.insufficient_literal is None
    assert len(fake_http.calls) == 1
    messages = fake_http.calls[0][1]["messages"]
    assert "Favorite color?" in messages[2]["content"]
    assert "retrieved memory" not in messages[2]["content"].casefold()


def test_successful_current_fallback_is_published_after_verbatim_validation():
    published = []
    client = DurableResponseBudgetedOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
        response_fallback_sink=published.append,
    )
    fake_http = _FakeHTTPClient(['{"verbatim_value":"INSUFFICIENT"}'])
    client._client = fake_http

    fallback = client._select_current_fallback_literal(
        "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT."
    )

    assert fallback == "INSUFFICIENT"
    assert published == ["INSUFFICIENT"]
    assert len(fake_http.calls) == 1
    messages = fake_http.calls[0][1]["messages"]
    assert "SOURCE_ALPHA" in messages[0]["content"]
    assert "Favorite color?" in messages[2]["content"]
