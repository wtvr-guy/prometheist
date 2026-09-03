"""Narrow real-Ollama smoke gate for the v2 final responder."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.percept_response_runtime import ResponseMemoryPackage
from jit_agent.percept_response_worker import UserPromptLLM
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
    packet = MemoryPacket(
        memory_request_id=uuid4(),
        need=MemoryNeed(query_text="What nickname and which approach was just ruled out?"),
        supported=True,
        items=[
            _evidence(
                EventType.INTERACTION_RESPONSE,
                f"Docker Compose | {profile_token}",
                conversation_id=active_conversation,
                conversation_seq=13,
                global_seq=32,
            ),
            _evidence(
                EventType.USER_PROMPT,
                "Which approach conflicts with my established Kestrel rule?",
                conversation_id=active_conversation,
                conversation_seq=8,
                global_seq=27,
            ),
            _evidence(
                EventType.USER_PROMPT,
                f"Call the active Kestrel plan {plan_label}.",
                conversation_id=active_conversation,
                conversation_seq=1,
                global_seq=20,
            ),
            _evidence(
                EventType.USER_PROMPT,
                "For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows "
                f"under profile {profile_token}.",
                conversation_id=historical_conversation,
                conversation_seq=1,
                global_seq=1,
            ),
        ],
    )
    package = ResponseMemoryPackage(
        memory_packet=packet,
        sufficient=True,
        composer_rounds=1,
        adaptive_recall_rounds=0,
    )

    answer = UserPromptLLM().generate_final_response(
        "What nickname are we using for this plan, and which approach did you just rule out? "
        "Return exactly '<nickname> | <approach>' and nothing else.",
        package,
        (),
    )
    assert answer.strip() == f"{plan_label} | Docker Compose"
