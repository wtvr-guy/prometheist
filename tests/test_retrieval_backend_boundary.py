from __future__ import annotations

import inspect
import uuid

from jit_agent import retrieval
from jit_agent.models import RetrievalRequest, RetrievalResult


class RecordingBackend:
    def __init__(self) -> None:
        self.call = None

    def search(
        self,
        conn,
        conversation_id,
        request,
        *,
        before_conversation_seq=None,
        before_global_seq=None,
    ):
        self.call = {
            "conn": conn,
            "conversation_id": conversation_id,
            "request": request,
            "before_conversation_seq": before_conversation_seq,
            "before_global_seq": before_global_seq,
        }
        return RetrievalResult(items=[])


def test_retrieval_service_contains_no_postgres_fts_syntax():
    source = inspect.getsource(retrieval)
    for postgres_term in ("to_tsvector", "to_tsquery", "ts_rank", "@@"):
        assert postgres_term not in source


def test_retrieval_service_delegates_through_replaceable_backend():
    backend = RecordingBackend()
    conn = object()
    conversation_id = uuid.uuid4()
    request = RetrievalRequest(
        query_text="adapter boundary",
        conversation_scope="ALL_CONVERSATIONS",
        ordering="RELEVANCE",
        limit=3,
    )
    result = retrieval.search(
        conn,
        conversation_id,
        request,
        before_conversation_seq=7,
        before_global_seq=11,
        backend=backend,
    )
    assert result == RetrievalResult(items=[])
    assert backend.call == {
        "conn": conn,
        "conversation_id": conversation_id,
        "request": request,
        "before_conversation_seq": 7,
        "before_global_seq": 11,
    }
