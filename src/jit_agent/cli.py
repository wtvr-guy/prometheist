"""First-party Prometheist CLI.

The interactive chat REPL is intentionally thin: it owns presentation only and
passes each user percept through the current percept-to-response runtime. It does
not retain or replay an LLM transcript. Each interaction uses guarded disposable
worker processes, deterministic work control, Composer-driven Adaptive Recall,
and the final response boundary documented in PERCEPT_TO_RESPONSE_PIPELINE.md.

`--once` remains available for scripting. Each invocation is a fresh process with
zero in-memory conversational state. `inspect --latest` exposes the append-only
response evidence trace so the exact memory/work bundle used for a response can
be audited after the fact.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

from psycopg.rows import dict_row

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
_RESPONSE_TRACE_SOURCE = "percept_response_v2/response_input_trace"


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


def _latest_response_trace(conn, conversation_id: uuid.UUID | None) -> dict | None:
    """Load the newest permanent FINAL_RESPONSE_INPUT_V1 audit event."""

    with conn.cursor(row_factory=dict_row) as cur:
        if conversation_id is None:
            cur.execute(
                """
                SELECT event_id, conversation_id, correlation_id, global_seq,
                       conversation_seq, created_at, payload
                FROM events
                WHERE event_type = 'SYSTEM_EVENT' AND source = %s
                ORDER BY global_seq DESC
                LIMIT 1
                """,
                (_RESPONSE_TRACE_SOURCE,),
            )
        else:
            cur.execute(
                """
                SELECT event_id, conversation_id, correlation_id, global_seq,
                       conversation_seq, created_at, payload
                FROM events
                WHERE event_type = 'SYSTEM_EVENT' AND source = %s
                  AND conversation_id = %s
                ORDER BY global_seq DESC
                LIMIT 1
                """,
                (_RESPONSE_TRACE_SOURCE, conversation_id),
            )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "event_id": str(row["event_id"]),
        "conversation_id": str(row["conversation_id"]),
        "correlation_id": str(row["correlation_id"]),
        "global_seq": int(row["global_seq"]),
        "conversation_seq": int(row["conversation_seq"]),
        "created_at": row["created_at"].isoformat(),
        "payload": row["payload"],
    }


def _run_inspect(conversation_id: uuid.UUID | None) -> None:
    with db.get_connection() as conn:
        trace = _latest_response_trace(conn, conversation_id)
    if trace is None:
        scope = f" for conversation {conversation_id}" if conversation_id else ""
        raise RuntimeError(f"no persisted response trace found{scope}")
    print(json.dumps(trace, indent=2, sort_keys=True, default=str))


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
        choices=("chat", "inspect"),
        default="chat",
        help="Run chat (default) or inspect a persisted response trace.",
    )
    parser.add_argument(
        "--once",
        help="Handle a single percept non-interactively and print the response.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="With inspect, show the latest permanent response-input trace.",
    )
    parser.add_argument(
        "--conversation-id",
        type=uuid.UUID,
        help="Conversation id to use/resume, or to filter inspection.",
    )
    args = parser.parse_args()

    if args.command == "inspect":
        if args.once is not None:
            parser.error("--once cannot be combined with inspect")
        if not args.latest:
            parser.error("inspect currently requires --latest")
        _run_inspect(args.conversation_id)
        return

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
