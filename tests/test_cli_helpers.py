from __future__ import annotations

import io
import subprocess
import sys
import uuid

import pytest

from tests import _cli_helpers


class _TagsResponse:
    def __init__(self, models: list[str]) -> None:
        self._models = models

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"models": [{"name": model} for model in self._models]}


@pytest.fixture(autouse=True)
def _clear_ollama_preflight_cache():
    _cli_helpers.ollama_unavailable_reason.cache_clear()
    yield
    _cli_helpers.ollama_unavailable_reason.cache_clear()


def test_run_once_decodes_the_cli_utf8_stream_explicitly(monkeypatch):
    """Windows locale decoding must not corrupt or drop model output."""
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="Unicode: \u2603\n", stderr="")

    monkeypatch.setattr(_cli_helpers.subprocess, "run", fake_run)
    conversation_id = uuid.uuid4()

    answer = _cli_helpers.run_once("hello", conversation_id)

    assert answer == "Unicode: \u2603"
    assert captured["text"] is True
    assert captured["encoding"] == "utf-8"
    assert "errors" not in captured


def test_print_transcript_replaces_characters_the_stream_cannot_encode():
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252")

    _cli_helpers.print_transcript("Status: \u2705", stream=stream)
    stream.flush()

    assert raw.getvalue().decode("cp1252").strip() == "Status: ?"


def test_utf8_subprocess_contract_round_trips_non_ascii_output():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.stdout.reconfigure(encoding='utf-8', errors='replace'); "
                "print('Status: \\u2705')"
            ),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    assert result.stdout.strip() == "Status: \u2705"


def test_ollama_preflight_uses_configured_endpoint_and_models(monkeypatch):
    requested: dict[str, object] = {}

    def fake_get(url: str, *, timeout: float):
        requested.update(url=url, timeout=timeout)
        return _TagsResponse(["chat:test", "embed:test"])

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:1234/")
    monkeypatch.setenv("OLLAMA_MODEL", "chat:test")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "embed:test")
    monkeypatch.setattr(_cli_helpers.httpx, "get", fake_get)

    assert _cli_helpers.ollama_available()
    assert requested == {"url": "http://ollama.test:1234/api/tags", "timeout": 2.0}


def test_required_ollama_preflight_fails_instead_of_skipping(monkeypatch):
    monkeypatch.setenv(_cli_helpers.REQUIRE_OLLAMA_ENV, "1")
    monkeypatch.setenv("OLLAMA_MODEL", "chat:test")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "embed:missing")
    monkeypatch.setattr(
        _cli_helpers.httpx,
        "get",
        lambda *args, **kwargs: _TagsResponse(["chat:test"]),
    )

    with pytest.raises(RuntimeError, match="embed:missing"):
        _cli_helpers.ollama_available()


@pytest.mark.parametrize("payload", [[], {"models": None}, {"unexpected": []}])
def test_ollama_preflight_rejects_malformed_success_payloads(monkeypatch, payload):
    class _MalformedResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    monkeypatch.setattr(
        _cli_helpers.httpx,
        "get",
        lambda *args, **kwargs: _MalformedResponse(),
    )

    assert _cli_helpers.ollama_unavailable_reason() == (
        "Ollama returned an invalid /api/tags payload"
    )
