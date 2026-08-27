"""Backend-agnostic Retrieval Service.

The Primary Agent describes the information it needs with ``RetrievalRequest``.
This module owns request semantics and delegates physical search to a replaceable
``RetrievalBackend``. PostgreSQL-specific FTS syntax is isolated in
``jit_agent.retrieval_backend``.

The reference backend still has the v1 lexical limitation: fully paraphrased
recall with no shared vocabulary requires a semantic backend/mechanism.
"""
from __future__ import annotations

import uuid

from jit_agent.models import RetrievalRequest, RetrievalResult
from jit_agent.retrieval_backend import (
    PostgresFullTextRetrievalBackend,
    RetrievalBackend,
)


_DEFAULT_BACKEND: RetrievalBackend = PostgresFullTextRetrievalBackend()


def search(
    conn: object,
    conversation_id: uuid.UUID,
    request: RetrievalRequest,
    before_conversation_seq: int | None = None,
    before_global_seq: int | None = None,
    *,
    backend: RetrievalBackend | None = None,
) -> RetrievalResult:
    """Satisfy a retrieval request through the configured storage adapter.

    ``conversation_seq`` is meaningful only within one conversation, while
    ``global_seq`` is the cross-conversation ordering/cutoff. The backend
    receives both boundaries and applies the one appropriate to request scope.
    """
    selected_backend = backend or _DEFAULT_BACKEND
    return selected_backend.search(
        conn,
        conversation_id,
        request,
        before_conversation_seq=before_conversation_seq,
        before_global_seq=before_global_seq,
    )
