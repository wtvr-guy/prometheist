"""Native acceptance for memory across fresh processes and conversations.

Process A is told an arbitrary fact and exits completely. Process B starts a
different conversation and asks about it.  Conversation boundaries are
organizational provenance, not memory walls.

The automated gate verifies that the fresh final response worker receives the
correct policy-admitted canonical evidence.  Its natural-language response is
printed for human inspection rather than constrained to a canned string.
"""
from __future__ import annotations

import uuid

import pytest

from jit_agent.models import EventType
from tests._cli_helpers import ollama_available, print_transcript, run_once
from tests._native_final_response import (
    assert_final_responder_has,
    event_for_text,
    final_responder_view,
)

pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


def test_cross_conversation_cross_process_memory_recall():
    conversation_a = uuid.uuid4()
    conversation_b = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()
    seed = f"The codename for Project Harrier is {random_fact}."

    seed_answer = run_once(seed, conversation_a)
    print_transcript(f"\nHistorical seed — User:\n{seed}")
    print_transcript(f"\nHistorical seed — Prometheist:\n{seed_answer}")
    seed_event = event_for_text(conversation_a, EventType.USER_PROMPT, seed)

    question = "What codename did I give Project Harrier?"
    answer = run_once(question, conversation_b)
    print_transcript(f"\nFresh-conversation recall — User:\n{question}")
    print_transcript(f"\nFresh-conversation recall — Prometheist:\n{answer}")

    view = final_responder_view(conversation_b, question)
    assert_final_responder_has(
        view,
        required_source_event_ids=(seed_event.event_id,),
        required_literals=(random_fact,),
    )
