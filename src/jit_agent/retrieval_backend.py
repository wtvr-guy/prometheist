"""Replaceable retrieval backend contracts and the PostgreSQL FTS adapter.

PostgreSQL-specific query syntax lives here, behind ``RetrievalBackend``.
The higher-level ``jit_agent.retrieval`` service owns request semantics and can
swap this adapter without exposing PostgreSQL operators to callers.
"""
from __future__ import annotations

import re
import uuid
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from jit_agent.models import EventType, RetrievalItem, RetrievalRequest, RetrievalResult


_WORD_RE = re.compile(r"[A-Za-z0-9]+")


class RetrievalBackend(Protocol):
    """Narrow storage adapter used by the Retrieval Service."""

    def search(
        self,
        conn: object,
        conversation_id: uuid.UUID,
        request: RetrievalRequest,
        *,
        before_conversation_seq: int | None = None,
        before_global_seq: int | None = None,
    ) -> RetrievalResult:
        ...


class PostgresFullTextRetrievalBackend:
    """Reference PostgreSQL lexical adapter.

    All Postgres full-text-search operators are intentionally confined to this
    class so replacing the persistence/search implementation does not require
    rewriting request-policy orchestration.
    """

    def search(
        self,
        conn: object,
        conversation_id: uuid.UUID,
        request: RetrievalRequest,
        *,
        before_conversation_seq: int | None = None,
        before_global_seq: int | None = None,
    ) -> RetrievalResult:
        if not isinstance(conn, psycopg.Connection):
            raise TypeError("PostgresFullTextRetrievalBackend requires a psycopg connection")

        where_clauses: list[str] = []
        where_params: list[object] = []
        scope_is_current = request.conversation_scope == "CURRENT_CONVERSATION"

        if scope_is_current:
            where_clauses.append("conversation_id = %s")
            where_params.append(conversation_id)
            if before_conversation_seq is not None:
                where_clauses.append("conversation_seq < %s")
                where_params.append(before_conversation_seq)
        elif before_global_seq is not None:
            where_clauses.append("global_seq < %s")
            where_params.append(before_global_seq)

        if request.source_types:
            where_clauses.append("event_type = ANY(%s)")
            where_params.append([event_type.value for event_type in request.source_types])

        rank_select = "NULL::float AS rank"
        rank_params: list[object] = []
        tsquery_str = _or_tsquery(request.query_text) if request.query_text else None
        if tsquery_str:
            rank_select = (
                "ts_rank(to_tsvector('english', coalesce(payload_text, '')), "
                "to_tsquery('english', %s)) AS rank"
            )
            rank_params = [tsquery_str]
            where_clauses.append(
                "to_tsvector('english', coalesce(payload_text, '')) "
                "@@ to_tsquery('english', %s)"
            )
            where_params.append(tsquery_str)

        order_column = "conversation_seq" if scope_is_current else "global_seq"
        if request.ordering == "CHRON_ASC":
            order_by = f"{order_column} ASC"
        elif request.ordering == "RELEVANCE" and tsquery_str:
            order_by = f"rank DESC, {order_column} DESC"
        else:
            order_by = f"{order_column} DESC"

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        query = f"""
            SELECT event_id, event_type, created_at, conversation_id, conversation_seq,
                   global_seq, payload, payload_text, {rank_select}
            FROM events
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT %s
        """
        params = rank_params + where_params + [request.limit]

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return RetrievalResult(
            items=[
                RetrievalItem(
                    source_event_id=row["event_id"],
                    event_type=EventType(row["event_type"]),
                    created_at=row["created_at"],
                    conversation_id=row["conversation_id"],
                    conversation_seq=row["conversation_seq"],
                    global_seq=row["global_seq"],
                    content=row["payload_text"] or _payload_to_text(row["payload"]),
                    rank=row["rank"],
                )
                for row in rows
            ]
        )


def _or_tsquery(text: str) -> str | None:
    """Build an OR-of-words query while keeping SQL syntax adapter-local."""
    words = _WORD_RE.findall(text)
    if not words:
        return None
    return " | ".join(words)


def _payload_to_text(payload: dict) -> str:
    return payload.get("text", str(payload))
