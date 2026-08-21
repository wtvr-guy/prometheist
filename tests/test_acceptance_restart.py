"""Cross-process acceptance tests using the real local Ollama adapter.

Each ``run_once`` invocation launches a brand-new Python process. The tests are
skipped when Ollama is unavailable, but when run they exercise real fresh model
calls plus PostgreSQL-backed JIT memory rather than Python mock state.
"""
from __future__ import annotations

import uuid

import pytest

from tests._cli_helpers import ollama_available, run_once

pytestmark = pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable")


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

    run_once(sentence, conversation_id)
    answer = run_once(question, conversation_id)

    assert random_fact in answer


def test_v06_cross_process_specialist_recalls_without_hidden_transcript():
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()

    # Process A persists the event and exits completely.
    run_once(f"The codename for Project Oriole is {random_fact}.", fact_conversation)

    # Process B has a fresh Primary invocation. The explicit wording makes the
    # desired v0.6 control path unambiguous: Primary -> specialist -> JIT Memory.
    answer = run_once(
        "Use the memory specialist to tell me the codename for Project Oriole.",
        task_conversation,
    )

    assert random_fact in answer
