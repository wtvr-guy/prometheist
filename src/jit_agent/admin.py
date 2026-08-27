"""LLM-free administrative and data-sovereignty operations.

This module deliberately has no dependency on ``jit_agent.llm`` or an inference
runtime. It is the administrative control plane required by Constitutional
Articles 21 and 22: durable state remains inspectable, verifiable, rebuildable,
exportable, restorable, and explicitly erasable when cognition is unavailable.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from jit_agent.postgres_memory_kernel import rebuild as rebuild_memory_kernel
from jit_agent.postgres_memory_kernel import verify as verify_memory_kernel


EXPORT_SCHEMA_VERSION = 1
ERASE_ALL_CONFIRMATION = "ERASE-ALL-PROMETHEIST-DATA"
RESTORE_CONFIRMATION = "RESTORE-INTO-EMPTY-PROMETHEIST"

EXPORT_TABLES: tuple[str, ...] = (
    "conversations",
    "events",
    "event_integrity",
    "memory_projection_runs",
    "memory_projection_entries",
    "memory_association_entries",
    "attention_execution_resources",
    "attention_tasks",
    "attention_resource_observations",
    "attention_assignments",
    "attention_scheduling_epochs",
    "attention_scheduler_state",
    "attention_task_transitions",
    "attention_preemption_events",
    "attention_resource_reservations",
    "attention_worker_steps",
    "attention_worker_claim_observations",
    "attention_worker_claims",
    "attention_worker_checkpoints",
    "attention_worker_results",
    "attention_interactions",
)
RESTORE_TABLES: tuple[str, ...] = EXPORT_TABLES
ERASURE_TABLES: tuple[str, ...] = tuple(reversed(EXPORT_TABLES))


def inspect_state(conn: psycopg.Connection) -> dict[str, Any]:
    """Return a bounded, machine-readable summary without invoking an LLM."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) AS count FROM conversations")
        conversations = int(cur.fetchone()["count"])
        cur.execute("SELECT count(*) AS count FROM events")
        events = int(cur.fetchone()["count"])
        cur.execute(
            """
            SELECT count(*) AS count
            FROM attention_tasks
            WHERE status NOT IN ('COMPLETED', 'FAILED')
            """
        )
        unfinished_tasks = int(cur.fetchone()["count"])
        cur.execute(
            """
            SELECT count(*) AS count
            FROM attention_worker_steps s
            WHERE NOT EXISTS (
                SELECT 1 FROM attention_worker_results r
                WHERE r.scheduler_key = s.scheduler_key AND r.step_id = s.step_id
            )
            """
        )
        unfinished_worker_steps = int(cur.fetchone()["count"])
        cur.execute("SELECT count(*) AS count FROM attention_worker_claims WHERE status = 'ACTIVE'")
        active_worker_claims = int(cur.fetchone()["count"])
        cur.execute("SELECT count(*) AS count FROM attention_interactions")
        interactions = int(cur.fetchone()["count"])
        cur.execute("SELECT max(global_seq) AS max_global_seq FROM events")
        row = cur.fetchone()
        max_global_seq = int(row["max_global_seq"]) if row["max_global_seq"] is not None else None
    return {
        "llm_required": False,
        "conversations": conversations,
        "events": events,
        "max_global_seq": max_global_seq,
        "interactions": interactions,
        "unfinished_tasks": unfinished_tasks,
        "unfinished_worker_steps": unfinished_worker_steps,
        "active_worker_claims": active_worker_claims,
    }


def inspect_history(
    conn: psycopg.Connection,
    *,
    rows: int = 50,
    conversation_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Read canonical event history directly from the durable ledger."""
    if rows < 1:
        raise ValueError("history rows must be positive")
    where = ""
    params: list[object] = []
    if conversation_id is not None:
        where = "WHERE conversation_id = %s"
        params.append(conversation_id)
    params.append(rows)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT event_id, conversation_id, correlation_id, global_seq,
                   conversation_seq, event_type, source, created_at,
                   payload, payload_text, schema_version
            FROM events
            {where}
            ORDER BY global_seq DESC
            LIMIT %s
            """,
            params,
        )
        return [_json_safe(dict(row)) for row in cur.fetchall()]


def inspect_unfinished_work(
    conn: psycopg.Connection,
    *,
    rows: int = 100,
) -> dict[str, list[dict[str, Any]]]:
    """Enumerate durable work that has not reached a terminal state."""
    if rows < 1:
        raise ValueError("unfinished-work rows must be positive")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT scheduler_key, task_id, task_key, criticality, service_class,
                   interruption_policy, status, enqueued_cycle, revision, updated_at
            FROM attention_tasks
            WHERE status NOT IN ('COMPLETED', 'FAILED')
            ORDER BY created_seq ASC, task_id ASC
            LIMIT %s
            """,
            (rows,),
        )
        tasks = [_json_safe(dict(row)) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT s.scheduler_key, s.step_id, s.assignment_id, s.task_id,
                   s.step_key, s.capability, s.effect_policy, s.created_at
            FROM attention_worker_steps s
            WHERE NOT EXISTS (
                SELECT 1 FROM attention_worker_results r
                WHERE r.scheduler_key = s.scheduler_key AND r.step_id = s.step_id
            )
            ORDER BY s.created_at ASC, s.step_id ASC
            LIMIT %s
            """,
            (rows,),
        )
        steps = [_json_safe(dict(row)) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT scheduler_key, claim_id, step_id, assignment_id, task_id,
                   worker_id, attempt, checkpoint_revision, claimed_at,
                   lease_expires_at, last_heartbeat_at, status
            FROM attention_worker_claims
            WHERE status = 'ACTIVE'
            ORDER BY claimed_at ASC, claim_id ASC
            LIMIT %s
            """,
            (rows,),
        )
        claims = [_json_safe(dict(row)) for row in cur.fetchall()]
    return {"tasks": tasks, "worker_steps": steps, "active_claims": claims}


def verify_state(conn: psycopg.Connection) -> dict[str, Any]:
    result = verify_memory_kernel(conn)
    if hasattr(result, "model_dump"):
        return _json_safe(result.model_dump(mode="json"))
    if isinstance(result, dict):
        return _json_safe(result)
    return {"verified": bool(result), "detail": _json_safe(result)}


def rebuild_derived_state(conn: psycopg.Connection) -> dict[str, Any]:
    return _json_safe(rebuild_memory_kernel(conn))


def export_bundle(conn: psycopg.Connection, output_path: str | Path) -> dict[str, Any]:
    tables = {table: _export_table(conn, table) for table in EXPORT_TABLES}
    core = {"schema_version": EXPORT_SCHEMA_VERSION, "tables": tables}
    digest = _bundle_digest(core)
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "digest_algorithm": "sha256",
        "digest": digest,
        "tables": tables,
    }
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "digest": digest,
        "table_count": len(tables),
        "row_count": sum(len(rows) for rows in tables.values()),
    }


def restore_bundle(
    conn: psycopg.Connection,
    input_path: str | Path,
    *,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != RESTORE_CONFIRMATION:
        raise ValueError(f"restore requires exact confirmation {RESTORE_CONFIRMATION!r}")
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    _validate_bundle(payload)
    _assert_restore_target_empty(conn)
    tables = payload["tables"]
    try:
        with conn.cursor() as cur:
            for table in RESTORE_TABLES:
                rows = list(tables[table])
                if table == "attention_tasks":
                    rows.sort(key=lambda row: int(row.get("created_seq", 0)))
                elif table == "attention_scheduling_epochs":
                    rows.sort(key=lambda row: (str(row.get("scheduler_key", "")), int(row.get("epoch_sequence", 0))))
                for row in rows:
                    cur.execute(
                        sql.SQL("INSERT INTO {} SELECT * FROM json_populate_record(NULL::{}, %s::json)").format(
                            sql.Identifier(table), sql.Identifier(table)
                        ),
                        (json.dumps(row, sort_keys=True, ensure_ascii=False),),
                    )
            _repair_sequences(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "restored": True,
        "digest": payload["digest"],
        "row_count": sum(len(rows) for rows in tables.values()),
    }


def erase_all_user_data(conn: psycopg.Connection, *, confirmation: str) -> dict[str, Any]:
    """Explicit whole-deployment erasure; never ordinary memory mutation."""
    if confirmation != ERASE_ALL_CONFIRMATION:
        raise ValueError(f"erasure requires exact confirmation {ERASE_ALL_CONFIRMATION!r}")
    before = inspect_state(conn)
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL prometheist.user_erasure = 'on'")
            cur.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(table) for table in ERASURE_TABLES)
                )
            )
            cur.execute("ALTER SEQUENCE attention_task_created_seq RESTART WITH 1")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "erased": True,
        "previous_conversations": before["conversations"],
        "previous_events": before["events"],
        "previous_interactions": before["interactions"],
    }


def _export_table(conn: psycopg.Connection, table: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql.SQL("SELECT to_jsonb(t) AS row FROM {} AS t").format(sql.Identifier(table)))
        rows = [dict(row["row"]) for row in cur.fetchall()]
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str))
    return [_json_safe(row) for row in rows]


def _validate_bundle(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise ValueError("unsupported Prometheist export schema version")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("export bundle has no table mapping")
    if set(tables) != set(EXPORT_TABLES):
        raise ValueError("export bundle table set does not match this release")
    core = {"schema_version": EXPORT_SCHEMA_VERSION, "tables": tables}
    expected = _bundle_digest(core)
    if payload.get("digest_algorithm") != "sha256" or payload.get("digest") != expected:
        raise ValueError("export bundle digest mismatch")


def _assert_restore_target_empty(conn: psycopg.Connection) -> None:
    nonempty: list[str] = []
    with conn.cursor() as cur:
        for table in EXPORT_TABLES:
            cur.execute(sql.SQL("SELECT EXISTS (SELECT 1 FROM {})").format(sql.Identifier(table)))
            if bool(cur.fetchone()[0]):
                nonempty.append(table)
    if nonempty:
        raise RuntimeError("restore target must be empty; non-empty tables: " + ", ".join(nonempty))


def _repair_sequences(cur) -> None:
    cur.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('events', 'global_seq'),
            COALESCE((SELECT max(global_seq) FROM events), 1),
            EXISTS(SELECT 1 FROM events)
        )
        """
    )
    cur.execute(
        """
        SELECT setval(
            'attention_task_created_seq',
            COALESCE((SELECT max(created_seq) FROM attention_tasks), 1),
            EXISTS(SELECT 1 FROM attention_tasks)
        )
        """
    )


def _bundle_digest(core: dict[str, Any]) -> str:
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))
