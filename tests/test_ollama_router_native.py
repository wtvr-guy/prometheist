"""Narrow real-Ollama smoke gate for the production structured router adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent.capability_registry import CapabilityDescriptor, CapabilityKind
from jit_agent.interaction_policy import InteractionAction, InteractionDecision
from jit_agent.llm import OllamaClient
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from tests._cli_helpers import ollama_available


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


def _evidence(content: str, *, seq: int) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=EventType.USER_PROMPT,
        source="native-router-smoke",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid4(),
        conversation_seq=seq,
        global_seq=seq,
        content=content,
    )


def test_real_ollama_router_returns_nonempty_valid_structured_decision():
    profile_token = "VX-NATIVE01"
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="Which established Kestrel constraint and profile apply?"),
        supported=True,
        items=[
            _evidence(
                "For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows "
                f"because virtualization is disabled. I track that constraint under profile {profile_token}.",
                seq=1,
            ),
            _evidence(
                "For Project Juniper, Docker Compose is acceptable when virtualization is available.",
                seq=2,
            ),
            _evidence(
                "The active Kestrel plan is called BlueHarbor-NATIVE.",
                seq=3,
            ),
        ],
    )
    catalog = (
        CapabilityDescriptor(
            capability_id="memory.inspect",
            kind=CapabilityKind.WORKFLOW,
            description="Inspect additional memory only if supplied evidence is insufficient.",
        ),
    )

    decision = OllamaClient().classify(
        "Which approach conflicts with my established Kestrel rule, and what constraint "
        "profile did I give that rule? Return exactly '<approach> | <profile>' and nothing else.",
        packet,
        catalog,
    )

    assert isinstance(decision, InteractionDecision)
    assert decision.next_action is InteractionAction.RESPOND
    assert decision.capability_indices == []
