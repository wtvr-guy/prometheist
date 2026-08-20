"""PostgreSQL adapter for the deterministic Prometheist memory kernel.

This module is additive to the MVP Retrieval Service.  It intentionally does
not replace ``jit_agent.retrieval`` yet; the existing proof-of-concept remains
usable while the v0.2 kernel is benchmarked beside it.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import uuid
from typing import Iterable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from jit_agent.memory_integrity import (
    IntegrityRecord,
    build_integrity_chain,
    verify_integrity_chain,
)
from jit_agent.memory_kernel import CueState, MemoryEvent, MemoryPacket, normalize_text, recall, tokenize
from jit_agent.memory_projection import LexicalProjection, build_projection, projection_digest


def _row_to_memory_event(row: dict) -> MemoryEvent:
    payload = row["payload"] or {}
    text = row.get("payload_text") or payload.get("text") or json.dumps(payload, sort_keys=True, default=str)
    return MemoryEvent(
        event_id=str(row["event_id"]),
        global_seq=int(row["global_seq"]),
        conversation_id=str(row["conversation_id"]),
        conversation_seq=int(row["conversation_seq"]),
        event_type=str(row["event_type"]),
        source=str(row["source"]),
        created_at=row["created_at"],
        text=text,
        payload=payload,
    )


def load_events(conn: psycopg.Connection, *, before_global_seq: int | None = None) -> list[MemoryEvent]:
    where = "WHERE global_seq < %s" if before_global_seq is not None else ""
    params: tuple[object, ...] = (before_global_seq,) if before_global_seq is not None else ()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT event_id, global_seq, conversation_id, conversation_seq,
                   event_type, source, created_at, payload, payload_text
            FROM events
            {where}
            ORDER BY global_seq ASC
            """,
            params,
        )
        return [_row_to_memory_event(row) for row in cur.fetchall()]


def rebuild(conn: psycopg.Connection) -> dict[str, object]:
    """Rebuild every v0.2 derived structure solely from authoritative events."""
    events = load_events(conn)
    integrity = build_integrity_chain(events)
    projection = LexicalProjection()
    entries = build_projection(events, projection)
    digest = projection_digest(entries)
    run_id = uuid.uuid4()

    with conn.cursor() as cur:
        # Derived state is explicitly disposable.  Authoritative ``events`` is
        # never modified by this operation.
        cur.execute("DELETE FROM event_integrity")
        cur.execute(
            "DELETE FROM memory_projection_entries WHERE projection_name = %s AND projection_version = %s",
            (projection.name, projection.version),
        )

        if integrity:
            cur.executemany(
                """
                INSERT INTO event_integrity (
                    event_id, global_seq, previous_hash, content_hash, hash_algorithm
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        uuid.UUID(record.event_id),
                        record.global_seq,
                        record.previous_hash,
                        record.content_hash,
                        record.algorithm,
                    )
                    for record in integrity
                ],
            )

        if entries:
            cur.executemany(
                """
                INSERT INTO memory_projection_entries (
                    projection_name, projection_version, source_event_id,
                    source_global_seq, source_hash, data
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        entry.projection_name,
                        entry.projection_version,
                        uuid.UUID(entry.source_event_id),
                        entry.source_global_seq,
                        entry.source_hash,
                        Json(dict(entry.data)),
                    )
                    for entry in entries
                ],
            )

        cur.execute(
            """
            INSERT INTO memory_projection_runs (
                run_id, projection_name, projection_version, source_event_count,
                entry_count, projection_digest, status, completed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'COMPLETED', now())
            """,
            (run_id, projection.name, projection.version, len(events), len(entries), digest),
        )
    conn.commit()
    return {
        "run_id": str(run_id),
        "source_event_count": len(events),
        "integrity_record_count": len(integrity),
        "projection_entry_count": len(entries),
        "projection_digest": digest,
    }


def verify(conn: psycopg.Connection):
    events = load_events(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, global_seq, previous_hash, content_hash, hash_algorithm
            FROM event_integrity
            ORDER BY global_seq ASC
            """
        )
        records = tuple(
            IntegrityRecord(
                event_id=str(row["event_id"]),
                global_seq=int(row["global_seq"]),
                previous_hash=row["previous_hash"],
                content_hash=row["content_hash"],
                algorithm=row["hash_algorithm"],
            )
            for row in cur.fetchall()
        )
    return verify_integrity_chain(events, records)


def _candidate_event_ids(
    conn: psycopg.Connection,
    cue: CueState,
    *,
    before_global_seq: int | None,
    candidate_limit: int,
) -> list[uuid.UUID]:
    """Use the disposable lexical projection as a cheap global candidate index.

    The pure kernel still performs final scoring.  We union lexical matches
    with a small recency window so the adapter never relies on one route alone.
    """
    ignored_terms = {normalize_text(term) for term in cue.ignored_terms if normalize_text(term)}
    terms = sorted({token for token in tokenize(cue.query_text or "") if token not in ignored_terms})
    entity_terms = sorted({normalized for entity in cue.entities if (normalized := normalize_text(entity))})
    cutoff_sql = "AND e.global_seq < %s" if before_global_seq is not None else ""
    cutoff_params: list[object] = [before_global_seq] if before_global_seq is not None else []

    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    with conn.cursor() as cur:
        if terms or entity_terms:
            cur.execute(
                f"""
                SELECT e.event_id
                FROM memory_projection_entries p
                JOIN events e ON e.event_id = p.source_event_id
                WHERE p.projection_name = 'lexical'
                  AND p.projection_version = '1'
                  {cutoff_sql}
                  AND (
                    (p.data -> 'terms') ?| %s::text[]
                    OR (p.data -> 'entities') ?| %s::text[]
                  )
                ORDER BY e.global_seq DESC
                LIMIT %s
                """,
                cutoff_params + [terms, entity_terms, candidate_limit],
            )
            for (event_id,) in cur.fetchall():
                if event_id not in seen:
                    seen.add(event_id)
                    ids.append(event_id)

        remaining = max(0, candidate_limit - len(ids))
        if remaining:
            cutoff_where = "WHERE global_seq < %s" if before_global_seq is not None else ""
            params = ([before_global_seq] if before_global_seq is not None else []) + [min(remaining, 100)]
            cur.execute(
                f"""
                SELECT event_id FROM events
                {cutoff_where}
                ORDER BY global_seq DESC
                LIMIT %s
                """,
                params,
            )
            for (event_id,) in cur.fetchall():
                if event_id not in seen:
                    seen.add(event_id)
                    ids.append(event_id)
    return ids[:candidate_limit]


def recall_from_postgres(
    conn: psycopg.Connection,
    cue: CueState,
    *,
    before_global_seq: int | None = None,
    candidate_limit: int = 500,
) -> MemoryPacket:
    if candidate_limit < cue.limit:
        raise ValueError("candidate_limit must be >= cue.limit")
    event_ids = _candidate_event_ids(
        conn,
        cue,
        before_global_seq=before_global_seq,
        candidate_limit=candidate_limit,
    )
    if not event_ids:
        return recall([], cue)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, global_seq, conversation_id, conversation_seq,
                   event_type, source, created_at, payload, payload_text
            FROM events
            WHERE event_id = ANY(%s)
            """,
            (event_ids,),
        )
        events = [_row_to_memory_event(row) for row in cur.fetchall()]
    return recall(events, cue)
