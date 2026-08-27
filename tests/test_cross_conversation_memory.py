"""Acceptance test for system memory across fresh processes and sessions.

Process A (Conversation A) is told an arbitrary fact and exits completely.
Process B (a brand-new Conversation B) asks about it and must still find it
-- conversation boundaries are organizational metadata, not memory walls.

Requires a running local Ollama with the configured model pulled, and
Postgres reachable via DATABASE_URL. Skipped automatically if Ollama isn't
reachable.
"""
from __future__ import annotations

import uuid

import pytest

from tests._cli_helpers import ollama_available, run_once

pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


def test_cross_conversation_cross_process_memory_recall():
    conversation_a = uuid.uuid4()
    conversation_b = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()

    # Process A, Conversation A: persist the fact, then exit completely.
    run_once(f"The codename for Project Harrier is {random_fact}.", conversation_a)

    # Process B, a *different* conversation: no shared conversation_id, no
    # shared process/memory -- only the persisted event history in common.
    answer = run_once("What codename did I give Project Harrier?", conversation_b)

    assert random_fact in answer
