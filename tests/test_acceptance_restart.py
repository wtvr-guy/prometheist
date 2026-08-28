"""Cross-process native acceptance through the real local Ollama adapter.

Each ``run_once`` invocation launches a brand-new Python process.  The automated
oracle scores the policy-admitted evidence/authority handed to the fresh final
response worker, not one canned natural-language surface string.  The resulting
response is still printed so native runs expose actual user-facing behavior for
human inspection.
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


def _print_exchange(label: str, prompt: str, answer: str) -> None:
    print_transcript(f"\n{label} — User:\n{prompt}")
    print_transcript(f"\n{label} — Prometheist:\n{answer}")


@pytest.mark.parametrize(
    "codename_sentence,question",
    [
        (
            "The codename for Project Oriole is {fact}.",
            "What codename did I give Project Oriole?",
        ),
        (
            "The launch code for Project Falcon is {fact}.",
            "What launch code did I give for Project Falcon?",
        ),
    ],
)
def test_cross_process_restart_recalls_randomized_fact(codename_sentence, question):
    conversation_id = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()
    sentence = codename_sentence.format(fact=random_fact)

    seed_answer = run_once(sentence, conversation_id)
    _print_exchange("Historical seed", sentence, seed_answer)
    seed_event = event_for_text(conversation_id, EventType.USER_PROMPT, sentence)

    answer = run_once(question, conversation_id)
    _print_exchange("Fresh-process recall", question, answer)

    view = final_responder_view(conversation_id, question)
    assert_final_responder_has(
        view,
        required_source_event_ids=(seed_event.event_id,),
        required_literals=(random_fact,),
    )


def test_cross_process_memory_analysis_recalls_without_hidden_transcript():
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()
    seed = f"The codename for Project Oriole is {random_fact}."

    # Process A persists the event and exits completely.
    seed_answer = run_once(seed, fact_conversation)
    _print_exchange("Historical seed", seed, seed_answer)
    seed_event = event_for_text(fact_conversation, EventType.USER_PROMPT, seed)

    # Process B has no inherited transcript.  Prometheist must reconstruct the
    # relevant evidence through its durable JIT-memory/capability path.
    question = "Use the memory specialist to remind me what codename I gave Project Oriole."
    answer = run_once(question, task_conversation)
    _print_exchange("Fresh-process memory analysis", question, answer)

    view = final_responder_view(task_conversation, question)
    assert_final_responder_has(
        view,
        required_source_event_ids=(seed_event.event_id,),
        required_literals=(random_fact,),
    )
