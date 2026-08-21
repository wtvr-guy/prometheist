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


@pytest.mark.parametrize(
    "fact_sentence,specialist_task",
    [
        (
            "The codename for Project Oriole is {fact}.",
            "Use a specialist to recall the codename for Project Oriole and state it exactly.",
        ),
        (
            "My deployment requirement is {fact}.",
            "Use a specialist to propose one deployment step that explicitly includes my deployment requirement.",
        ),
        (
            "The Project Atlas schedule changed from September to {fact}.",
            "Use a specialist to compare the Project Atlas schedule change and state the new schedule value exactly.",
        ),
    ],
)
def test_v06_registry_routes_multiple_specialists_without_hidden_transcript(
    fact_sentence,
    specialist_task,
):
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()

    # Process A persists evidence and exits completely.
    run_once(fact_sentence.format(fact=random_fact), fact_conversation)

    # Process B receives no capability catalog or inherited transcript. The
    # Primary chooses only DELEGATE; deterministic capability discovery resolves
    # the relevant registered specialist from the task itself.
    answer = run_once(specialist_task, task_conversation)

    assert random_fact in answer
