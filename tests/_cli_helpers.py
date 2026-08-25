"""Shared helpers for subprocess-based CLI acceptance tests."""
from __future__ import annotations

from functools import lru_cache
import os
import subprocess
import sys
from typing import TextIO
import uuid

import httpx


REQUIRE_OLLAMA_ENV = "REQUIRE_OLLAMA_ACCEPTANCE"
DEFAULT_CHAT_MODEL = "qwen3:4b"
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:4b-q4_K_M"


@lru_cache(maxsize=1)
def ollama_unavailable_reason() -> str | None:
    """Return a concrete local-runtime preflight failure, if any."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return f"Ollama is unavailable: {type(exc).__name__}"

    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        return "Ollama returned an invalid /api/tags payload"
    models = payload["models"]
    installed = {
        value
        for item in models
        if isinstance(item, dict)
        for value in (item.get("name"), item.get("model"))
        if isinstance(value, str)
    }
    required = {
        os.environ.get("OLLAMA_MODEL", DEFAULT_CHAT_MODEL),
        os.environ.get("OLLAMA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    }
    missing = sorted(required - installed)
    if missing:
        return f"Ollama is missing required model(s): {', '.join(missing)}"
    return None


def ollama_available() -> bool:
    reason = ollama_unavailable_reason()
    if reason is not None and ollama_required():
        raise RuntimeError(f"{REQUIRE_OLLAMA_ENV}=1 but {reason}")
    return reason is None


def ollama_required() -> bool:
    return os.environ.get(REQUIRE_OLLAMA_ENV, "").casefold() in {"1", "true", "yes"}


def run_once(prompt: str, conversation_id: uuid.UUID, timeout: int = 300) -> str:
    """Runs the CLI's --once mode as a brand-new process with zero shared
    in-memory state, and returns its printed response.
    """
    result = subprocess.run(
        [sys.executable, "-m", "jit_agent.cli", "--once", prompt, "--conversation-id", str(conversation_id)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def print_transcript(text: str, *, stream: TextIO | None = None) -> None:
    """Print model text without failing on a legacy Windows console encoding."""
    output = stream or sys.stdout
    encoding = getattr(output, "encoding", None) or "utf-8"
    safe_text = text.encode(encoding, errors="replace").decode(encoding)
    print(safe_text, file=output)
