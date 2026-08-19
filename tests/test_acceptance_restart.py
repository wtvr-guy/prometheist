"""Mandatory acceptance test (spec-required): full process restart.

Persist arbitrary randomized content in one process, exit completely,
launch a brand-new process, ask in different-but-lexically-overlapping
wording, and confirm the Retrieval Service finds it and the Primary Agent
answers correctly -- proving no in-memory state is required.

Requires a running local Ollama with the configured model pulled, and
Postgres reachable via DATABASE_URL. Skipped automatically if Ollama isn't
reachable, since this exercises the real LLM rather than a mock.
"""
from __future__ import annotations

import uuid

import pytest

from tests._cli_helpers import ollama_available, run_once

pytestmark = pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable")


@pytest.mark.parametrize(
    "codename_sentence,fact,question",
    [
        (
            "The codename for Project Oriole is {fact}.",
            None,
            "What codename did I give Project Oriole?",
        ),
        (
            "The launch code for Project Falcon is {fact}.",
            None,
            "What launch code did I give for Project Falcon?",
        ),
    ],
)
def test_cross_process_restart_recalls_randomized_fact(codename_sentence, fact, question):
    conversation_id = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()
    sentence = codename_sentence.format(fact=random_fact)

    # Process A: persist the fact, then exit completely.
    run_once(sentence, conversation_id)

    # Process B: brand-new process, no shared memory, ask differently.
    answer = run_once(question, conversation_id)

    assert random_fact in answer
