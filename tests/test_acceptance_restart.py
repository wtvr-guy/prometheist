"""Cross-process acceptance tests using the real local Ollama adapter.

Each ``run_once`` invocation launches a brand-new Python process. The tests are
skipped when Ollama is unavailable, but when run they exercise real fresh model
calls, deterministic capability discovery, and PostgreSQL-backed JIT memory.
"""
from __future__ import annotations

import json
import uuid

import pytest

from jit_agent import db, event_store
from tests._cli_helpers import ollama_available, run_once

pytestmark = pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable")


def _conversation_trace(conversation_id: uuid.UUID) -> str:
    """Return a compact persisted causal trace for acceptance-test failures."""
    conn = db.get_connection()
    try:
        events = event_store.get_events_by_conversation(conn, conversation_id)
    finally:
        conn.close()

    lines: list[str] = []
    for event in events:
        payload = json.dumps(event.payload, sort_keys=True, default=str)
        lines.append(
            f"seq={event.conversation_seq} type={event.event_type.value} "
            f"source={event.source} payload={payload}"
        )
    return "\n".join(lines)


@pytest.mark.parametrize(
    "fact_sentence,question",
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
def test_cross_process_restart_discovers_internal_memory_capability(fact_sentence, question):
    fact_conversation = uuid.uuid4()
    recall_conversation = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()

    # Process A persists evidence and exits completely.
    run_once(fact_sentence.format(fact=random_fact), fact_conversation)

    # Process B has no transcript and no privileged memory path. The Primary
    # emits REQUEST_CAPABILITY and deterministic discovery selects internal_memory.
    answer = run_once(question, recall_conversation)

    assert random_fact in answer, _conversation_trace(recall_conversation)


@pytest.mark.parametrize(
    "fact_sentence,specialist_task",
    [
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
def test_v06_multiple_specialists_discover_memory_without_hidden_transcript(
    fact_sentence,
    specialist_task,
):
    fact_conversation = uuid.uuid4()
    task_conversation = uuid.uuid4()
    random_fact = uuid.uuid4().hex[:8].upper()

    # Process A persists evidence and exits completely.
    run_once(fact_sentence.format(fact=random_fact), fact_conversation)

    # Process B receives no capability catalog or inherited transcript. Primary
    # requests a capability, the registry selects the relevant specialist, and
    # that fresh specialist independently requests another capability for the
    # missing persisted information. The registry then selects internal_memory.
    answer = run_once(specialist_task, task_conversation)

    assert random_fact in answer, _conversation_trace(task_conversation)
