"""Event store: the sole way anything gets persisted.

Persistence here is unconditional and automatic -- it is never gated by an
LLM decision. Every meaningful thing that happens (prompts, responses,
decisions, retrieval requests/results, errors) goes through `record_event`.
All deterministic metadata (ids, timestamps, sequence numbers) is generated
here in application code, never by the LLM.
"""
from __future__ import annotations

import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from jit_agent.models import Event, EventType


_WORKPIECE_SNAPSHOT_KIND = "INTERACTION_WORKPIECE_SNAPSHOT"
_WORKPIECE_SNAPSHOT_SEMANTIC_TEXT = "interaction workpiece audit snapshot"


def _effective_payload_text(
    event_type: EventType,
    payload: dict[str, Any],
    payload_text: str | None,
) -> str | None:
    """Return the bounded text used by semantic projections for one event.

    Canonical JSON payloads remain complete and immutable. Large derived audit
    snapshots deliberately receive a compact semantic descriptor so their nested
    copies of prompts/evidence cannot recursively outrank the canonical source
    events during later JIT recall.
    """

    if payload_text is not None:
        return payload_text
    if (
        event_type is EventType.SYSTEM_EVENT
        and payload.get("kind") == _WORKPIECE_SNAPSHOT_KIND
    ):
        return _WORKPIECE_SNAPSHOT_SEMANTIC_TEXT
    return None


def start_conversation(conn: psycopg.Connection, conversation_id: uuid.UUID | None = None) -> uuid.UUID:
    """Create a new conversation, or a no-op if `conversation_id` already exists."""
    conversation_id = conversation_id or uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO conversations (conversation_id)
            VALUES (%s)
            ON CONFLICT (conversation_id) DO NOTHING
            """,
            (conversation_id,),
        )
    conn.commit()
    return conversation_id


def record_event(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    event_type: EventType,
    source: str,
    payload: dict[str, Any],
    payload_text: str | None = None,
    event_id: uuid.UUID | None = None,
) -> Event:
    """Append one event, assigning a monotonic per-conversation sequence number.

    Uses a simple locked-counter transaction (single-user prototype scale):
    lock the conversation row, read+use its next_event_seq, then increment it.
    """
    event_id = event_id or uuid.uuid4()
    effective_payload_text = _effective_payload_text(event_type, payload, payload_text)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, conversation_id, correlation_id, global_seq,
                   conversation_seq, event_type, source, created_at,
                   payload, payload_text, schema_version
            FROM events WHERE event_id = %s
            """,
            (event_id,),
        )
        existing = cur.fetchone()
        if existing is not None:
            stored = _row_to_event(existing)
            if (
                stored.conversation_id != conversation_id
                or stored.correlation_id != correlation_id
                or stored.event_type is not event_type
                or stored.source != source
                or stored.payload != payload
                or existing["payload_text"] != effective_payload_text
            ):
                raise ValueError("conflicting deterministic event retry")
            conn.commit()
            return stored
        cur.execute(
            "SELECT next_event_seq FROM conversations WHERE conversation_id = %s FOR UPDATE",
            (conversation_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown conversation_id: {conversation_id}")
        conversation_seq = row["next_event_seq"]

        cur.execute(
            """
            INSERT INTO events (
                event_id, conversation_id, correlation_id, conversation_seq,
                event_type, source, payload, payload_text
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING event_id, conversation_id, correlation_id, global_seq,
                      conversation_seq, event_type, source, created_at,
                      payload, schema_version
            """,
            (
                event_id,
                conversation_id,
                correlation_id,
                conversation_seq,
                event_type.value,
                source,
                Json(payload),
                effective_payload_text,
            ),
        )
        inserted = cur.fetchone()

        cur.execute(
            "UPDATE conversations SET next_event_seq = next_event_seq + 1 WHERE conversation_id = %s",
            (conversation_id,),
        )
    conn.commit()
    return _row_to_event(inserted)


def get_event_by_id(conn: psycopg.Connection, event_id: uuid.UUID) -> Event | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, conversation_id, correlation_id, global_seq,
                   conversation_seq, event_type, source, created_at,
                   payload, schema_version
            FROM events WHERE event_id = %s
            """,
            (event_id,),
        )
        row = cur.fetchone()
    return _row_to_event(row) if row else None


def get_events_by_conversation(conn: psycopg.Connection, conversation_id: uuid.UUID) -> list[Event]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, conversation_id, correlation_id, global_seq,
                   conversation_seq, event_type, source, created_at,
                   payload, schema_version
            FROM events WHERE conversation_id = %s
            ORDER BY conversation_seq ASC
            """,
            (conversation_id,),
        )
        rows = cur.fetchall()
    return [_row_to_event(r) for r in rows]


def get_first_event_in_conversation(conn: psycopg.Connection, conversation_id: uuid.UUID) -> Event | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_id, conversation_id, correlation_id, global_seq,
                   conversation_seq, event_type, source, created_at,
                   payload, schema_version
            FROM events WHERE conversation_id = %s
            ORDER BY conversation_seq ASC LIMIT 1
            """,
            (conversation_id,),
        )
        row = cur.fetchone()
    return _row_to_event(row) if row else None


def _row_to_event(row: dict[str, Any]) -> Event:
    return Event(
        event_id=row["event_id"],
        conversation_id=row["conversation_id"],
        correlation_id=row["correlation_id"],
        global_seq=row["global_seq"],
        conversation_seq=row["conversation_seq"],
        event_type=EventType(row["event_type"]),
        source=row["source"],
        created_at=row["created_at"],
        payload=row["payload"],
        schema_version=row["schema_version"],
    )
