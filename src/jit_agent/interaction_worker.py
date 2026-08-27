"""Fresh-process entry point for one already-guarded interaction worker step."""
from __future__ import annotations

import os
import sys
from uuid import UUID

from jit_agent import db
from jit_agent.interaction_runtime import execute_claimed_interaction_step
from jit_agent.llm import OllamaClient


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing guarded worker environment value: {name}")
    return value


def main() -> None:
    _configure_utf8_streams()
    claim_id = UUID(_required_environment("PROMETHEIST_WORKER_CLAIM_ID"))
    worker_id = _required_environment("PROMETHEIST_WORKER_ID")
    scheduler_key = _required_environment("PROMETHEIST_WORKER_SCHEDULER_KEY")
    with db.get_connection() as conn:
        execute_claimed_interaction_step(
            conn,
            OllamaClient(),
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )


if __name__ == "__main__":
    main()
