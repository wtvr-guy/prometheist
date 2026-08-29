"""First-party Prometheist CLI.

The interactive chat REPL is intentionally thin: it owns presentation only and
passes each user percept through the current percept-to-response runtime. It does
not retain or replay an LLM transcript. Each interaction uses guarded disposable
worker processes, deterministic work control, Composer-driven Adaptive Recall,
and the final response boundary documented in PERCEPT_TO_RESPONSE_PIPELINE.md.

`--once` remains available for scripting. Each invocation is a fresh process with
zero in-memory conversational state.
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
from jit_agent.percept_response_runtime import handle_percept_in_worker_processes
from jit_agent.worker_runtime import WorkerLaunchDenied

# Compatibility symbol retained so existing diagnostic tests and downstream callers
# patch the authoritative v2 path rather than importing the superseded runtime.
handle_interaction_in_worker_processes = handle_percept_in_worker_processes

_INTERACTION_ADMISSION_FAILURE = "interaction was not safely admitted to one assignment"
_EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit"}


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
) -> str | None:
    """Run one percept and expose the authoritative denial envelope on failure."""

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
                "diagnostic_error": f"{type(diagnostic_exc).__name__}: {diagnostic_exc}",
            }
        _emit_admission_diagnostics(diagnostics)
        raise


def _run_chat(conversation_id: uuid.UUID) -> None:
    """Run the lightweight terminal UI over the authoritative percept path."""

    print("Prometheist")
    print(f"conversation_id: {conversation_id}")
    print("Type /exit or /quit to stop.")

    with db.get_connection() as conn:
        while True:
            try:
                user_text = input("\nYou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_text.lower() in _EXIT_COMMANDS:
                break
            if not user_text:
                continue

            response = _handle_with_admission_diagnostics(
                conn,
                user_text,
                conversation_id,
            )
            if response is not None:
                print(f"\nPrometheist > {response}")


def main() -> None:
    _configure_utf8_streams()
    parser = argparse.ArgumentParser(prog="prometheist")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("chat",),
        default="chat",
        help="Run the lightweight interactive terminal chat (default).",
    )
    parser.add_argument(
        "--once",
        help="Handle a single percept non-interactively and print a response only if required.",
    )
    parser.add_argument(
        "--conversation-id",
        type=uuid.UUID,
        help="Conversation id to use/resume. Optional; a fresh provenance id is created by default.",
    )
    args = parser.parse_args()

    conversation_id = args.conversation_id or uuid.uuid4()

    if args.once is not None:
        with db.get_connection() as conn:
            response = _handle_with_admission_diagnostics(
                conn,
                args.once,
                conversation_id,
            )
        if response is not None:
            print(response)
        return

    _run_chat(conversation_id)


if __name__ == "__main__":
    main()
