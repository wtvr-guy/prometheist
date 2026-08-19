"""CLI entry point: interactive REPL, or --once for scripting/tests.

Each invocation of `--once` is a fresh process with zero in-memory state,
which is what makes the cross-process restart acceptance test meaningful.
"""
from __future__ import annotations

import argparse
import uuid

from jit_agent import db
from jit_agent.llm import OllamaClient
from jit_agent.primary_agent import handle_interaction


def main() -> None:
    parser = argparse.ArgumentParser(prog="jit-agent")
    parser.add_argument("--once", help="Handle a single message non-interactively and print the response.")
    parser.add_argument(
        "--conversation-id",
        type=uuid.UUID,
        help="Conversation id to use/resume. Required with --once; optional otherwise.",
    )
    args = parser.parse_args()

    llm = OllamaClient()

    if args.once is not None:
        conversation_id = args.conversation_id or uuid.uuid4()
        with db.get_connection() as conn:
            response = handle_interaction(conn, llm, args.once, conversation_id)
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
            response = handle_interaction(conn, llm, user_text, conversation_id)
            print(response)


if __name__ == "__main__":
    main()
