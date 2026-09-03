"""First-party Prometheist CLI.

The chat REPL owns presentation only.  Artifact inspection and verification do not
require PostgreSQL; recovery and event restoration use the independent JSON
journal as durable checkpoints/reconstruction input.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid

from jit_agent import artifact_journal, artifact_recovery, db
from jit_agent.admission_diagnostics import (
    RESOURCE_ADMISSION_DIAGNOSTIC_PREFIX,
    build_resource_admission_diagnostics,
)
from jit_agent.attention_store import load_scheduler
from jit_agent.chat_startup import reset_chat_execution_state
from jit_agent.percept_response_runtime import handle_percept_in_worker_processes
from jit_agent.worker_runtime import WorkerLaunchDenied

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
        return handle_percept_in_worker_processes(
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


def _resolve_artifact_interaction_id(
    interaction_id: uuid.UUID | None,
    *,
    latest: bool,
    complete: bool | None = None,
) -> uuid.UUID:
    if interaction_id is not None:
        return interaction_id
    if not latest:
        raise RuntimeError("specify --interaction-id or --latest")
    resolved = artifact_journal.latest_interaction_id(complete=complete)
    if resolved is None:
        qualifier = " incomplete" if complete is False else ""
        raise RuntimeError(f"no{qualifier} interaction artifacts found")
    return resolved


def _run_inspect(interaction_id: uuid.UUID | None, *, latest: bool) -> None:
    resolved = _resolve_artifact_interaction_id(interaction_id, latest=latest)
    print(
        json.dumps(
            artifact_journal.inspect_interaction(resolved),
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


def _run_verify(interaction_id: uuid.UUID | None, *, latest: bool) -> None:
    resolved = _resolve_artifact_interaction_id(interaction_id, latest=latest)
    report = artifact_journal.verify_interaction_chain(resolved)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if not report["valid"]:
        raise RuntimeError("artifact chain verification failed")


def _run_recover(interaction_id: uuid.UUID | None, *, latest: bool) -> None:
    resolved = _resolve_artifact_interaction_id(
        interaction_id,
        latest=latest,
        complete=False if interaction_id is None else None,
    )
    with db.get_connection() as conn:
        response = artifact_recovery.resume_interaction_from_artifacts(conn, resolved)
    if response is not None:
        print(response)


def _run_restore_events() -> None:
    with db.get_connection() as conn:
        result = artifact_recovery.restore_event_store_from_artifacts(conn)
    print(json.dumps(result, indent=2, sort_keys=True))


def _reset_failed_turn(conn, exc: BaseException) -> None:
    """Release replaceable execution state after one failed interactive turn."""

    try:
        reset_chat_execution_state(conn)
    except Exception as reset_exc:
        print(
            "PROMETHEIST_TURN_RECOVERY_FAILED="
            f"{type(reset_exc).__name__}: {reset_exc}",
            file=sys.stderr,
        )
        raise exc from reset_exc


def _run_chat(conversation_id: uuid.UUID) -> None:
    """Run the lightweight terminal UI over the authoritative percept path.

    Starting an interactive chat is a clean execution boundary.  Replaceable
    scheduler/worker state from an earlier CLI process is cleared automatically
    before the first prompt, so Ctrl+C or a killed process cannot strand the
    single LLM reservation across sessions.  Canonical memory and JSON artifacts
    are preserved.

    A failed turn is also an execution boundary. The error remains durably
    inspectable in artifacts/events, but replaceable scheduler state is reset so
    one malformed model output or worker failure cannot terminate the REPL or
    poison the next prompt.
    """

    with db.get_connection() as conn:
        reset_chat_execution_state(conn)

        print("Prometheist")
        print(f"conversation_id: {conversation_id}")
        print("Type /exit or /quit to stop.")
        incomplete = artifact_journal.latest_interaction_id(complete=False)
        if incomplete is not None:
            print(
                "Recoverable incomplete interaction retained in artifacts: "
                f"{incomplete} (optional: `prometheist recover --latest`)."
            )

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

            try:
                response = _handle_with_admission_diagnostics(
                    conn,
                    user_text,
                    conversation_id,
                )
            except KeyboardInterrupt as exc:
                _reset_failed_turn(conn, exc)
                print("\nTurn interrupted; execution state reset.", file=sys.stderr)
                continue
            except Exception as exc:
                traceback.print_exc()
                _reset_failed_turn(conn, exc)
                latest = artifact_journal.latest_interaction_id(complete=False)
                suffix = f" interaction_id={latest}" if latest is not None else ""
                print(
                    "PROMETHEIST_TURN_FAILED="
                    f"{type(exc).__name__}: {exc}{suffix}\n"
                    "Execution state reset; chat remains available.",
                    file=sys.stderr,
                )
                continue

            if response is not None:
                print(f"\nPrometheist > {response}")


def main() -> None:
    _configure_utf8_streams()
    parser = argparse.ArgumentParser(prog="prometheist")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("chat", "inspect", "verify", "recover", "restore-events"),
        default="chat",
        help=(
            "Run chat (default), inspect/verify artifact chains, resume an incomplete "
            "interaction, or restore canonical events from artifacts."
        ),
    )
    parser.add_argument(
        "--once",
        help="Handle a single percept non-interactively and print the response.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the latest applicable artifact interaction.",
    )
    parser.add_argument(
        "--interaction-id",
        type=uuid.UUID,
        help="Specific artifact interaction id for inspect/verify/recover.",
    )
    parser.add_argument(
        "--conversation-id",
        type=uuid.UUID,
        help="Conversation id to use/resume for chat/--once.",
    )
    args = parser.parse_args()

    if args.command in {"inspect", "verify", "recover", "restore-events"}:
        if args.once is not None:
            parser.error("--once is only valid with chat")
        if args.conversation_id is not None:
            parser.error("--conversation-id is only valid with chat")
        if args.command == "inspect":
            _run_inspect(args.interaction_id, latest=args.latest)
            return
        if args.command == "verify":
            _run_verify(args.interaction_id, latest=args.latest)
            return
        if args.command == "recover":
            _run_recover(args.interaction_id, latest=args.latest)
            return
        if args.interaction_id is not None or args.latest:
            parser.error("restore-events takes no interaction selector")
        _run_restore_events()
        return

    if args.interaction_id is not None or args.latest:
        parser.error("--interaction-id/--latest are not valid with chat")
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
