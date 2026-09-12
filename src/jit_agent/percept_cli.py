"""Explicit local administration and one bounded cognition scheduler tick."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

from jit_agent import db
from jit_agent.cognitive_store import get_record, list_records, put_record, rebuild_heads
from jit_agent.consolidation import ConsolidationSchedule, emit_due_consolidations, schedule_consolidation
from jit_agent.expectations import Expectation
from jit_agent.percept_context import PerceptContext
from jit_agent.percept_intake import ingest_percept, install_source_policy
from jit_agent.perception import PerceptSource
from jit_agent.percept_triage import SourcePolicy
from jit_agent.reflexes import poll_reflexes
from jit_agent.situation_runtime import drain_situations
from jit_agent.situations import register_expectation


def tick(conn) -> dict:
    poll_reflexes(conn)
    cursor = get_record(conn, "schedule_cursor", "consolidation") or {"after_key": "", "revision": 0}
    after = emit_due_consolidations(conn, now=datetime.now(timezone.utc), after_key=cursor["after_key"])
    revision = cursor["revision"] + 1
    put_record(conn, "schedule_cursor", "consolidation", {"after_key": after or "", "revision": revision}, revision=str(revision))
    return {"completed": drain_situations(conn), "schedule_cursor": after}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("install-source", "ingest", "expectation", "schedule-consolidation"):
        commands.add_parser(name).add_argument("json_file", type=Path)
    commands.add_parser("tick")
    commands.add_parser("rebuild-heads")
    show = commands.add_parser("situations")
    show.add_argument("--after-key", default="")
    args = parser.parse_args()
    with db.get_connection() as conn:
        data = json.loads(args.json_file.read_text(encoding="utf-8")) if hasattr(args, "json_file") else None
        if args.command == "install-source":
            install_source_policy(conn, SourcePolicy.model_validate(data))
        elif args.command == "expectation":
            register_expectation(conn, Expectation.model_validate(data))
        elif args.command == "schedule-consolidation":
            schedule_consolidation(conn, ConsolidationSchedule.model_validate(data))
        elif args.command == "ingest":
            kwargs = {"conversation_id": UUID(data["conversation_id"])} if data.get("conversation_id") else {}
            percept = ingest_percept(
                conn, source=PerceptSource.model_validate(data["source"]), observation=data["observation"],
                observed_at=datetime.fromisoformat(data["observed_at"]), delivery_id=data["delivery_id"],
                context=PerceptContext.model_validate(data.get("context", {})),
                correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None, **kwargs,
            )
            print(percept.model_dump_json(indent=2))
        elif args.command == "tick":
            print(json.dumps(tick(conn), indent=2))
        elif args.command == "situations":
            print(json.dumps(list_records(conn, "situation", after_key=args.after_key), indent=2))
        elif args.command == "rebuild-heads":
            rebuild_heads(conn)


if __name__ == "__main__":
    main()
