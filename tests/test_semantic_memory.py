import uuid

import pytest

from jit_agent import db, event_store, jit_memory, semantic_memory
from jit_agent.models import (
    EvidenceStatus,
    EventType,
    SemanticRetrievalIntentV1,
    SemanticRetrievalTarget,
    SemanticTemporalFocus,
)


class FakeEmbeddingProvider:
    """Deterministic 1536d provider for CI; no external model is required."""

    provider_name = "fake"
    model = "fake-semantic-v1"
    dimensions = 1536

    @staticmethod
    def _vector(bucket: int) -> list[float]:
        vector = [0.0] * 1536
        vector[bucket] = 1.0
        return vector

    @classmethod
    def _bucket(cls, text: str) -> int:
        lowered = text.casefold()
        if "deployment" in lowered or "arm64" in lowered:
            return 0
        if "atlas" in lowered or "schedule" in lowered:
            return 1
        if "vehicle" in lowered or "insur" in lowered or "mazda" in lowered:
            return 2
        return 3

    def embed_documents(self, texts):
        return [self._vector(self._bucket(text)) for text in texts]

    def embed_query(self, query: str, instruction: str):
        return self._vector(self._bucket(query + " " + instruction))


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record_text(conn, conversation_id, text):
    event_store.start_conversation(conn, conversation_id)
    return event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": text},
        payload_text=text,
    )


def test_semantic_instruction_is_deterministically_rendered_from_bounded_intent():
    intent = SemanticRetrievalIntentV1(
        target=SemanticRetrievalTarget.PRIOR_STATE,
        temporal_focus=SemanticTemporalFocus.PREVIOUS,
    )

    instruction = semantic_memory.render_semantic_instruction(intent)

    assert instruction == (
        "Retrieve persisted evidence that establishes the immediately preceding state or value. "
        "Prefer evidence that establishes the immediately preceding state before the relevant change."
    )
    assert "vault" not in instruction.casefold()
    assert "database" not in instruction.casefold()


def test_semantic_fallback_recovers_source_event_after_deterministic_abstention(conn):
    source_conversation = uuid.uuid4()
    request_conversation = uuid.uuid4()
    token = uuid.uuid4().hex[:10].upper()
    source_event = _record_text(
        conn,
        source_conversation,
        f"My deployment requirement is {token}.",
    )
    _record_text(conn, source_conversation, "The cafeteria closes at 7 PM.")
    question = (
        "Use a specialist to propose one deployment step that explicitly includes "
        "my deployment requirement."
    )
    current_prompt = _record_text(conn, request_conversation, question)

    packet = jit_memory.request_memory(
        conn,
        conversation_id=request_conversation,
        correlation_id=current_prompt.correlation_id,
        requesting_agent="test_specialist",
        need=jit_memory.build_memory_need(
            question,
            supplemental_query_texts=[
                "access to the prior internal constraint needed for the current rollout task"
            ],
            semantic_intent=SemanticRetrievalIntentV1(
                target=SemanticRetrievalTarget.PROCEDURE,
                temporal_focus=SemanticTemporalFocus.UNSPECIFIED,
            ),
            conversation_id=request_conversation,
        ),
        before_global_seq=current_prompt.global_seq,
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert packet.supported is False
    assert packet.items
    assert packet.items[0].source_event_id == source_event.event_id
    assert token in packet.items[0].content
    assert packet.items[0].evidence_status == EvidenceStatus.SEMANTIC_CANDIDATE
    assert packet.items[0].retrieval_reasons == ["SEMANTIC_CANDIDATE"]
    assert packet.retrieval_trace["semantic"]["candidate_limit"] == 10
    assert packet.retrieval_trace["semantic"]["candidate_only"] is True

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*)
            FROM memory_semantic_projection_entries
            WHERE source_event_id = %s
              AND dimensions = 1536
            """,
            (source_event.event_id,),
        )
        assert cur.fetchone()[0] == 1


def test_semantic_similarity_never_promotes_unknown_relation_to_supported(conn):
    source_conversation = uuid.uuid4()
    request_conversation = uuid.uuid4()
    source_event = _record_text(conn, source_conversation, "My vehicle is a red Mazda crossover.")
    current_prompt = _record_text(conn, request_conversation, "Who insures my vehicle?")

    packet = jit_memory.request_memory(
        conn,
        conversation_id=request_conversation,
        correlation_id=current_prompt.correlation_id,
        requesting_agent="test_agent",
        need=jit_memory.build_memory_need(
            "Who insures my vehicle?",
            semantic_intent=SemanticRetrievalIntentV1(
                target=SemanticRetrievalTarget.RELATIONSHIP,
                temporal_focus=SemanticTemporalFocus.CURRENT,
            ),
        ),
        before_global_seq=current_prompt.global_seq,
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert packet.supported is False
    assert packet.items
    assert packet.items[0].source_event_id == source_event.event_id
    assert all(item.evidence_status == EvidenceStatus.SEMANTIC_CANDIDATE for item in packet.items)
