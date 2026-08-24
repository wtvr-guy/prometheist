"""Semantic candidate retrieval for Prometheist JIT Memory.

This module is deliberately a candidate-recovery layer. Vector proximity never
creates a persistent relationship and never, by itself, marks an event as
admitted evidence. Authoritative history remains the append-only ``events``
ledger; semantic rows are disposable projections.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from typing import Protocol, Sequence
import uuid

import httpx
import psycopg
from psycopg.rows import dict_row

from jit_agent.memory_integrity import canonical_event_bytes
from jit_agent.memory_kernel import MemoryEvent
from jit_agent.models import (
    EventType,
    SemanticRetrievalIntentV1,
    SemanticRetrievalTarget,
    SemanticTemporalFocus,
)
from jit_agent import postgres_memory_kernel

SEMANTIC_PROJECTION_VERSION = "event-text-v1"
SEMANTIC_CANDIDATE_LIMIT = 10
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:4b-q4_K_M"
DEFAULT_EMBEDDING_DIMENSIONS = 1536
DEFAULT_BATCH_SIZE = 16


class EmbeddingProvider(Protocol):
    provider_name: str
    model: str
    dimensions: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, query: str, instruction: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    """Reference semantic provider: Ollama + Qwen3-Embedding-4B Q4_K_M."""

    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
    ) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        self.dimensions = dimensions
        if self.dimensions != DEFAULT_EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"v0.6 semantic profile requires {DEFAULT_EMBEDDING_DIMENSIONS} dimensions"
            )
        self._client = httpx.Client(base_url=self.base_url, timeout=300.0)

    def _embed(self, inputs: Sequence[str]) -> list[list[float]]:
        response = self._client.post(
            "/api/embed",
            json={
                "model": self.model,
                "input": list(inputs),
                "dimensions": self.dimensions,
                "truncate": False,
                "keep_alive": "10m",
            },
        )
        response.raise_for_status()
        vectors = list(response.json().get("embeddings") or [])
        if len(vectors) != len(inputs):
            raise RuntimeError(
                f"Expected {len(inputs)} embeddings from {self.model}, received {len(vectors)}"
            )
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise RuntimeError(
                    f"Expected {self.dimensions} dimensions from {self.model}, received {len(vector)}"
                )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, query: str, instruction: str) -> list[float]:
        formatted = f"Instruct: {instruction}\nQuery:{query}"
        return self._embed([formatted])[0]


_TARGET_TEXT = {
    SemanticRetrievalTarget.FACT: "directly states the requested fact",
    SemanticRetrievalTarget.CURRENT_STATE: "establishes the currently applicable state or value",
    SemanticRetrievalTarget.PRIOR_STATE: "establishes the immediately preceding state or value",
    SemanticRetrievalTarget.STATE_TRANSITION: "describes the relevant change from an earlier state to a later state",
    SemanticRetrievalTarget.IDENTITY: "identifies the requested person, object, or named item",
    SemanticRetrievalTarget.RELATIONSHIP: "establishes the requested relationship between referenced subjects",
    SemanticRetrievalTarget.LOCATION: "identifies the requested location",
    SemanticRetrievalTarget.TIME: "identifies the requested date, time, schedule, or temporal value",
    SemanticRetrievalTarget.VALUE: "states the requested numeric, monetary, identifier, or other concrete value",
    SemanticRetrievalTarget.BOOLEAN_STATUS: "establishes whether the requested condition is true or false",
    SemanticRetrievalTarget.PREFERENCE: "states the requested preference or habitual choice",
    SemanticRetrievalTarget.PROCEDURE: "describes the requested procedure, method, or operational requirement",
    SemanticRetrievalTarget.GENERAL: "contains information needed to satisfy the request",
}

_TEMPORAL_TEXT = {
    SemanticTemporalFocus.CURRENT: "Prefer evidence that establishes the current state over superseded historical states.",
    SemanticTemporalFocus.PREVIOUS: "Prefer evidence that establishes the immediately preceding state before the relevant change.",
    SemanticTemporalFocus.AS_OF_REFERENCE_TIME: "Prefer evidence applicable at the request's reference time.",
    SemanticTemporalFocus.HISTORICAL: "Prefer evidence about the requested historical state or event rather than the current state.",
    SemanticTemporalFocus.UNSPECIFIED: "",
}


def render_semantic_instruction(intent: SemanticRetrievalIntentV1) -> str:
    """Render one bounded Qwen retrieval instruction without free-form LLM prose."""
    base = f"Retrieve persisted evidence that {_TARGET_TEXT[intent.target]}."
    temporal = _TEMPORAL_TEXT[intent.temporal_focus]
    return f"{base} {temporal}".strip()


@dataclass(frozen=True, slots=True)
class SemanticCandidate:
    source_event_id: uuid.UUID
    event_type: EventType
    source: str
    created_at: object
    conversation_id: uuid.UUID
    conversation_seq: int
    global_seq: int
    content: str
    similarity: float


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"


def _source_hash(event: MemoryEvent) -> str:
    return hashlib.sha256(canonical_event_bytes(event)).hexdigest()


def _batched(values: Sequence[MemoryEvent], size: int = DEFAULT_BATCH_SIZE):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def ensure_semantic_projection(
    conn: psycopg.Connection,
    provider: EmbeddingProvider,
    *,
    before_global_seq: int | None,
    source_types: Sequence[EventType],
) -> int:
    """Incrementally project eligible authoritative events into pgvector."""
    events = postgres_memory_kernel.load_events(conn, before_global_seq=before_global_seq)
    allowed = {item.value for item in source_types}
    eligible = [event for event in events if event.event_type in allowed]
    if not eligible:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_event_id
            FROM memory_semantic_projection_entries
            WHERE embedding_provider = %s
              AND embedding_model = %s
              AND dimensions = %s
              AND projection_version = %s
            """,
            (
                provider.provider_name,
                provider.model,
                provider.dimensions,
                SEMANTIC_PROJECTION_VERSION,
            ),
        )
        existing = {str(row[0]) for row in cur.fetchall()}

    missing = [event for event in eligible if event.event_id not in existing]
    if not missing:
        return 0

    inserted = 0
    for batch in _batched(missing):
        vectors = provider.embed_documents([event.text for event in batch])
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO memory_semantic_projection_entries (
                    embedding_provider, embedding_model, dimensions,
                    projection_version, source_event_id, source_global_seq,
                    source_hash, embedding
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (
                    embedding_provider, embedding_model, dimensions,
                    projection_version, source_event_id
                ) DO NOTHING
                """,
                [
                    (
                        provider.provider_name,
                        provider.model,
                        provider.dimensions,
                        SEMANTIC_PROJECTION_VERSION,
                        uuid.UUID(event.event_id),
                        event.global_seq,
                        _source_hash(event),
                        _vector_literal(vector),
                    )
                    for event, vector in zip(batch, vectors, strict=True)
                ],
            )
        inserted += len(batch)
    conn.commit()
    return inserted


def search_semantic_candidates(
    conn: psycopg.Connection,
    provider: EmbeddingProvider,
    *,
    query: str,
    intent: SemanticRetrievalIntentV1,
    before_global_seq: int | None,
    source_types: Sequence[EventType],
    limit: int = SEMANTIC_CANDIDATE_LIMIT,
) -> tuple[list[SemanticCandidate], str]:
    """Return exact-cosine semantic candidates; no ANN and no evidence assertion."""
    instruction = render_semantic_instruction(intent)
    query_vector = provider.embed_query(query, instruction)
    cutoff_sql = "AND s.source_global_seq < %s" if before_global_seq is not None else ""
    source_values = [item.value for item in source_types]
    params: list[object] = [
        provider.provider_name,
        provider.model,
        provider.dimensions,
        SEMANTIC_PROJECTION_VERSION,
        source_values,
    ]
    if before_global_seq is not None:
        params.append(before_global_seq)
    params.extend([_vector_literal(query_vector), limit])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT
                e.event_id,
                e.event_type,
                e.source,
                e.created_at,
                e.conversation_id,
                e.conversation_seq,
                e.global_seq,
                COALESCE(e.payload_text, e.payload->>'text', e.payload::text) AS content,
                1 - (s.embedding <=> %s::vector) AS similarity
            FROM memory_semantic_projection_entries s
            JOIN events e ON e.event_id = s.source_event_id
            WHERE s.embedding_provider = %s
              AND s.embedding_model = %s
              AND s.dimensions = %s
              AND s.projection_version = %s
              AND e.event_type = ANY(%s)
              {cutoff_sql}
            ORDER BY s.embedding <=> %s::vector ASC, s.source_global_seq DESC
            LIMIT %s
            """,
            [params[-2], *params[:-2], params[-2], params[-1]],
        )
        rows = cur.fetchall()

    return (
        [
            SemanticCandidate(
                source_event_id=row["event_id"],
                event_type=EventType(row["event_type"]),
                source=str(row["source"]),
                created_at=row["created_at"],
                conversation_id=row["conversation_id"],
                conversation_seq=int(row["conversation_seq"]),
                global_seq=int(row["global_seq"]),
                content=str(row["content"]),
                similarity=float(row["similarity"]),
            )
            for row in rows
        ],
        instruction,
    )
