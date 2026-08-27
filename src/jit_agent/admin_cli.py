"""First-class LLM-free administrative CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from jit_agent import db
from jit_agent.admin import (
    ERASE_ALL_CONFIRMATION,
    RESTORE_CONFIRMATION,
    erase_all_user_data,
    export_bundle,
    inspect_history,
    inspect_state,
    inspect_unfinished_work,
    rebuild_derived_state,
    restore_bundle,
    verify_state,
)


def _print(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prometheist-admin",
        description="Inspect and administer Prometheist durable state without an LLM runtime.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect", help="summarize durable state")

    history = sub.add_parser("history", help="read canonical event history")
    history.add_argument("--rows", type=int, default=50)
    history.add_argument("--conversation-id", type=UUID)

    unfinished = sub.add_parser("unfinished", help="enumerate unfinished durable work")
    unfinished.add_argument("--rows", type=int, default=100)

    sub.add_parser("verify", help="verify the canonical-event integrity chain")
    sub.add_parser("rebuild", help="rebuild disposable memory-kernel state")

    export = sub.add_parser("export", help="write a portable JSON backup/export")
    export.add_argument("path", type=Path)

    restore = sub.add_parser("restore", help="restore an export into an empty Prometheist store")
    restore.add_argument("path", type=Path)
    restore.add_argument("--confirm", required=True, help=f"must exactly equal {RESTORE_CONFIRMATION}")

    erase = sub.add_parser("erase-all", help="irreversibly erase all Prometheist data")
    erase.add_argument("--confirm", required=True, help=f"must exactly equal {ERASE_ALL_CONFIRMATION}")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with db.get_connection() as conn:
        if args.command == "inspect":
            result = inspect_state(conn)
        elif args.command == "history":
            result = inspect_history(conn, rows=args.rows, conversation_id=args.conversation_id)
        elif args.command == "unfinished":
            result = inspect_unfinished_work(conn, rows=args.rows)
        elif args.command == "verify":
            result = verify_state(conn)
        elif args.command == "rebuild":
            result = rebuild_derived_state(conn)
        elif args.command == "export":
            result = export_bundle(conn, args.path)
        elif args.command == "restore":
            result = restore_bundle(conn, args.path, confirmation=args.confirm)
        elif args.command == "erase-all":
            result = erase_all_user_data(conn, confirmation=args.confirm)
        else:  # pragma: no cover
            raise AssertionError(f"unknown command: {args.command}")
    _print(result)


if __name__ == "__main__":
    main()
