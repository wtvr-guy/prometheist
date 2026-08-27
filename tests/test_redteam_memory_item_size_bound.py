from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from jit_agent.budgeted_evidence_llm import BudgetedEvidenceBoundOllamaClient
from jit_agent.model_evidence_budget import ModelEvidenceBudgetExceeded
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket


class _NoModelCallAllowed:
    def post(self, *args, **kwargs):
        del args, kwargs
        raise AssertionError("oversized evidence reached the model transport")

    def close(self):
        return None


def test_single_oversized_memory_event_cannot_expand_llm_context_without_bound():
    """A bounded item count is not a bounded cognitive context if one item is unbounded.

    This preserves the original 2 MB attack but exercises the current production
    model boundary. Canonical evidence may remain arbitrarily large in durable
    storage; the disposable worker must fail closed before formatting or sending
    the full event to Ollama.
    """

    huge_content = "OVERSIZED-CANONICAL-EVIDENCE " + ("x" * 2_000_000)
    packet = MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="What does the stored evidence say?", limit=1),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid.uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                created_at=datetime.now(UTC),
                conversation_id=uuid.uuid4(),
                conversation_seq=1,
                global_seq=1,
                content=huge_content,
            )
        ],
    )

    client = BudgetedEvidenceBoundOllamaClient(
        base_url="http://ollama.test",
        model="model:test",
    )
    client._client = _NoModelCallAllowed()

    with pytest.raises(ModelEvidenceBudgetExceeded, match="item exceeds"):
        client.respond("What does the stored evidence say?", packet)
