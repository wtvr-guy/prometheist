"""Narrow real-Ollama smoke gate for the production structured router adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent.capability_registry import CapabilityDescriptor, CapabilityKind
from jit_agent.interaction_policy import InteractionDecision
from jit_agent.llm import OllamaClient
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from tests._cli_helpers import ollama_available


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


def test_real_ollama_router_returns_nonempty_valid_structured_decision():
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Which Kestrel deployment constraint applies?"),
        supported=True,
        items=[
            MemoryEvidence(
                source_event_id=uuid4(),
                event_type=EventType.USER_PROMPT,
                source="native-router-smoke",
                created_at=datetime.now(timezone.utc),
                conversation_id=uuid4(),
                conversation_seq=1,
                global_seq=1,
                content=(
                    "For Project Kestrel, PostgreSQL directly on Windows is the established "
                    "deployment constraint."
                ),
            )
        ],
    )
    catalog = (
        CapabilityDescriptor(
            capability_id="memory.inspect",
            kind=CapabilityKind.WORKFLOW,
            description="Inspect additional memory only if the supplied evidence is insufficient.",
        ),
    )

    decision = OllamaClient().classify(
        "Use the supplied memory to decide whether more work is required.",
        packet,
        catalog,
    )

    assert isinstance(decision, InteractionDecision)
