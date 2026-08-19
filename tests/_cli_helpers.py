"""Shared helpers for subprocess-based CLI acceptance tests."""
from __future__ import annotations

import subprocess
import sys
import uuid

import httpx


def ollama_available() -> bool:
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return True
    except httpx.HTTPError:
        return False


def run_once(prompt: str, conversation_id: uuid.UUID, timeout: int = 300) -> str:
    """Runs the CLI's --once mode as a brand-new process with zero shared
    in-memory state, and returns its printed response.
    """
    result = subprocess.run(
        [sys.executable, "-m", "jit_agent.cli", "--once", prompt, "--conversation-id", str(conversation_id)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()
