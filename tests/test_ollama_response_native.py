"""Narrow real-Ollama smoke gate for final response synthesis over activated memory."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent.llm import OllamaClient
from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from tests._cli_helpers import ollama_available


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


def _evidence(
    event_type: EventType,
    content: str,
    *,
    conversation_id,
    conversation_seq: int,
    global_seq: int,
) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid4(),
        event_type=event_type,
        source="native-response-smoke",
        created_at=datetime.now(timezone.utc),
        conversation_id=conversation_id,
        conversation_seq=conversation_seq,
        global_seq=global_seq,
        content=content,
    )


def test_real_ollama_response_reconciles_recent_relational_evidence():
    historical_conversation = uuid4()
    active_conversation = uuid4()
    profile_token = "VX-NATIVE01"
    plan_label = "BlueHarbor-NATIVE"

    historical_rule = (
        "For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows "
        f"because virtualization is disabled. I track that constraint under profile {profile_token}."
    )
    turn1 = (
        f"I'm revisiting Project Kestrel. For this conversation, call the plan {plan_label}. "
        "I'm choosing between Docker Compose and PostgreSQL directly on Windows. "
        "Based on my established constraints, choose the compatible approach."
    )
    turn2 = (
        "Which approach conflicts with my established Kestrel rule, and what constraint "
        "profile did I give that rule?"
    )
    turn2_answer = f"Docker Compose | {profile_token}"

    # Intentionally preserve the retrieval-priority order observed in native
    # acceptance. OllamaClient.respond must build its own chronological view.
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="What nickname and which approach was just ruled out?"),
        supported=True,
        items=[
            _evidence(
                EventType.INTERACTION_RESPONSE,
                turn2_answer,
                conversation_id=active_conversation,
                conversation_seq=13,
                global_seq=32,
            ),
            _evidence(
                EventType.USER_PROMPT,
                turn2,
                conversation_id=active_conversation,
                conversation_seq=8,
                global_seq=27,
            ),
            _evidence(
                EventType.INTERACTION_RESPONSE,
                "PostgreSQL directly on Windows",
                conversation_id=active_conversation,
                conversation_seq=6,
                global_seq=25,
            ),
            _evidence(
                EventType.USER_PROMPT,
                turn1,
                conversation_id=active_conversation,
                conversation_seq=1,
                global_seq=20,
            ),
            _evidence(
                EventType.USER_PROMPT,
                historical_rule,
                conversation_id=historical_conversation,
                conversation_seq=1,
                global_seq=1,
            ),
        ],
    )

    answer = OllamaClient().respond(
        "What nickname are we using for this plan, and which approach did you just rule out? "
        "Return exactly '<nickname> | <approach>' and nothing else.",
        packet,
    )

    assert answer.strip() == f"{plan_label} | Docker Compose"
