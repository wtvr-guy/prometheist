"""CLI entry point: interactive REPL, or --once for scripting/tests.

Each invocation of `--once` is a fresh process with zero in-memory state,
which is what makes the cross-process restart acceptance test meaningful.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from jit_agent import db
from jit_agent.admission_diagnostics import (
    RESOURCE_ADMISSION_DIAGNOSTIC_PREFIX,
    build_resource_admission_diagnostics,
)
from jit_agent.attention_store import load_scheduler
from jit_agent.interaction_runtime import handle_interaction_in_worker_processes
from jit_agent.worker_runtime import WorkerLaunchDenied


_INTERACTION_ADMISSION_FAILURE = (
    "interaction was not safely admitted to one assignment"
)


def _configure_utf8_streams() -> None:
    """Make Windows subprocess output deterministic before argument parsing."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _emit_admission_diagnostics(diagnostics: dict) -> None:
    print(
        RESOURCE_ADMISSION_DIAGNOSTIC_PREFIX
        + json.dumps(diagnostics, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
    )


def _handle_with_admission_diagnostics(
    conn,
    user_text: str,
    conversation_id: uuid.UUID,
) -> str:
    """Run one interaction and expose the authoritative denial envelope on failure."""

    try:
        return handle_interaction_in_worker_processes(
            conn,
            user_text,
            conversation_id,
        )
    except WorkerLaunchDenied as exc:
        _emit_admission_diagnostics(
            {
                "kind": "WORKER_CLAIM_DENIED",
                "worker_claim_observation": exc.observation.model_dump(mode="json"),
            }
        )
        raise
    except RuntimeError as exc:
        if str(exc) != _INTERACTION_ADMISSION_FAILURE:
            raise
        try:
            scheduler = load_scheduler(conn)
            diagnostics = build_resource_admission_diagnostics(scheduler)
            diagnostics["kind"] = "SCHEDULER_ADMISSION_DENIED"
        except Exception as diagnostic_exc:  # never mask the original runtime failure
            diagnostics = {
                "kind": "SCHEDULER_ADMISSION_DIAGNOSTIC_ERROR",
                "diagnostic_error": (
                    f"{type(diagnostic_exc).__name__}: {diagnostic_exc}"
                ),
            }
        _emit_admission_diagnostics(diagnostics)
        raise


def main() -> None:
    _configure_utf8_streams()
    parser = argparse.ArgumentParser(prog="jit-agent")
    parser.add_argument(
        "--once",
        help="Handle a single message non-interactively and print the response.",
    )
    parser.add_argument(
        "--conversation-id",
        type=uuid.UUID,
        help=(
            "Conversation id to use/resume. Required with --once; optional otherwise."
        ),
    )
    args = parser.parse_args()

    if args.once is not None:
        conversation_id = args.conversation_id or uuid.uuid4()
        with db.get_connection() as conn:
            response = _handle_with_admission_diagnostics(
                conn,
                args.once,
                conversation_id,
            )
        print(response)
        return

    conversation_id = args.conversation_id or uuid.uuid4()
    print(f"conversation_id: {conversation_id}")
    print("Type 'exit' or 'quit' to stop.")
    with db.get_connection() as conn:
        while True:
            try:
                user_text = input("> ").strip()
            except EOFError:
                break
            if user_text.lower() in {"exit", "quit"}:
                break
            if not user_text:
                continue
            response = _handle_with_admission_diagnostics(
                conn,
                user_text,
                conversation_id,
            )
            print(response)


if __name__ == "__main__":
    main()
