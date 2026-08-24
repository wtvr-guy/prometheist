"""Real-Ollama acceptance test for stateless conversational continuity.

Every ``run_once`` call launches a brand-new Python process and supplies the LLM
only the current user message. The test therefore fails if useful conversation
state exists only in an LLM context window.

The scenario deliberately requires two kinds of JIT recall at once:

1. immediate conversational context from earlier turns in the same conversation;
2. older relevant history from a separate conversation, mixed with unrelated
   persisted facts.

This is intentionally phrased like an ordinary conversation. Later turns use
references such as "those approaches", "what you just ruled out", and "that
one" rather than repeating the missing context in benchmark-style keywords.
"""
from __future__ import annotations

import json
import re
import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.models import EventType
from tests._cli_helpers import ollama_available, run_once

pytestmark = pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable")


def _events(conversation_id: uuid.UUID):
    conn = db.get_connection()
    try:
        return event_store.get_events_by_conversation(conn, conversation_id)
    finally:
        conn.close()


def _trace(*conversation_ids: uuid.UUID) -> str:
    lines: list[str] = []
    for conversation_id in conversation_ids:
        lines.append(f"conversation={conversation_id}")
        for event in _events(conversation_id):
            payload = json.dumps(event.payload, sort_keys=True, default=str)
            lines.append(
                f"  seq={event.conversation_seq} type={event.event_type.value} "
                f"source={event.source} correlation={event.correlation_id} payload={payload}"
            )
    return "\n".join(lines)


def _event_for_text(conversation_id: uuid.UUID, event_type: EventType, text: str):
    for event in _events(conversation_id):
        if event.event_type != event_type:
            continue
        payload_text = event.payload.get("text") if isinstance(event.payload, dict) else None
        if payload_text == text:
            return event
    raise AssertionError(
        f"No {event_type.value} event with exact text {text!r}.\n{_trace(conversation_id)}"
    )


def _response_for_correlation(conversation_id: uuid.UUID, correlation_id: uuid.UUID):
    responses = [
        event
        for event in _events(conversation_id)
        if event.correlation_id == correlation_id and event.event_type == EventType.AGENT_RESPONSE
    ]
    if len(responses) != 1:
        raise AssertionError(
            f"Expected one AGENT_RESPONSE for correlation {correlation_id}, got {len(responses)}.\n"
            f"{_trace(conversation_id)}"
        )
    return responses[0]


def _correlation_event_ids(conversation_id: uuid.UUID, correlation_id: uuid.UUID) -> set[uuid.UUID]:
    return {
        event.event_id
        for event in _events(conversation_id)
        if event.correlation_id == correlation_id
    }


def _memory_source_ids_for_correlation(
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> set[uuid.UUID]:
    source_ids: set[uuid.UUID] = set()
    for event in _events(conversation_id):
        if event.correlation_id != correlation_id or event.event_type != EventType.MEMORY_PACKET:
            continue
        for item in event.payload.get("packet", {}).get("items", []):
            source_ids.add(uuid.UUID(item["source_event_id"]))
    return source_ids


def _seed_distractors(count: int = 12) -> None:
    """Add unrelated history without spending extra real-LLM calls."""
    conn = db.get_connection()
    try:
        for index in range(count):
            conversation_id = uuid.uuid4()
            text = (
                f"Unrelated historical note {index}: inventory marker "
                f"{uuid.uuid4().hex[:10].upper()} belongs to archive shelf {index}."
            )
            event_store.start_conversation(conn, conversation_id)
            event_store.record_event(
                conn,
                conversation_id=conversation_id,
                correlation_id=uuid.uuid4(),
                event_type=EventType.USER_PROMPT,
                source="user",
                payload={"text": text},
                payload_text=text,
            )
    finally:
        conn.close()


def _print_turn(number: int, prompt: str, answer: str) -> None:
    print(f"\nTurn {number} — User:\n{prompt}")
    print(f"\nTurn {number} — Prometheist:\n{answer}")


def test_stateless_multiturn_conversation_retains_local_context_and_relevant_history():
    historical_conversation = uuid.uuid4()
    active_conversation = uuid.uuid4()
    profile_token = f"VX-{uuid.uuid4().hex[:8].upper()}"
    plan_label = f"BlueHarbor-{uuid.uuid4().hex[:6].upper()}"

    print("\n=== Stateless multi-turn conversation acceptance ===")
    print(f"historical_conversation={historical_conversation}")
    print(f"active_conversation={active_conversation}")

    # Persist an older fact through the normal CLI in a completely separate
    # process/conversation. It will later become relevant without being repeated.
    historical_rule = (
        "For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows "
        f"because virtualization is disabled. I track that constraint under profile {profile_token}."
    )
    historical_answer = run_once(historical_rule, historical_conversation)
    print(f"\nHistorical seed — User:\n{historical_rule}")
    print(f"\nHistorical seed — Prometheist:\n{historical_answer}")
    historical_rule_event = _event_for_text(
        historical_conversation,
        EventType.USER_PROMPT,
        historical_rule,
    )

    # Add unrelated persisted history so cross-conversation recall must select a
    # relevant old event rather than merely returning the only historical event.
    _seed_distractors()

    # Turn 1 establishes the immediate conversational frame. This process exits
    # completely before Turn 2 begins.
    turn1 = (
        f"I'm revisiting Project Kestrel. For this conversation, call the plan {plan_label}. "
        "I'm choosing between Docker Compose and running PostgreSQL directly on Windows. "
        "I want to keep the discussion practical."
    )
    answer1 = run_once(turn1, active_conversation)
    _print_turn(1, turn1, answer1)
    turn1_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn1)

    # Turn 2 requires BOTH missing pieces: "those approaches" comes from Turn 1,
    # while the established rule/profile comes from the older conversation.
    turn2 = (
        "Which of those approaches conflicts with my established Kestrel rule, "
        "and what constraint profile did I give that rule?"
    )
    answer2 = run_once(turn2, active_conversation)
    _print_turn(2, turn2, answer2)
    turn2_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn2)
    answer2_event = _response_for_correlation(active_conversation, turn2_event.correlation_id)
    turn2_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn2_event.correlation_id,
    )

    failure_trace = _trace(historical_conversation, active_conversation)
    assert "docker" in answer2.casefold(), failure_trace
    assert profile_token.casefold() in answer2.casefold(), failure_trace
    # These two source assertions are the core of the test: the same turn must
    # retrieve one event from the immediate conversation and one older event from
    # a different conversation. A plausible model guess is not enough to pass.
    assert historical_rule_event.event_id in turn2_sources, failure_trace
    assert turn1_event.event_id in turn2_sources, failure_trace

    # Turn 3 tests immediate continuity after another total process/context loss.
    # The nickname was introduced two turns ago; "just rule out" refers to the
    # immediately preceding exchange.
    turn3 = "What nickname are we using for this plan, and which approach did you just rule out?"
    answer3 = run_once(turn3, active_conversation)
    _print_turn(3, turn3, answer3)
    turn3_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn3)
    answer3_event = _response_for_correlation(active_conversation, turn3_event.correlation_id)
    turn3_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn3_event.correlation_id,
    )
    turn2_exchange_ids = _correlation_event_ids(active_conversation, turn2_event.correlation_id)

    failure_trace = _trace(historical_conversation, active_conversation)
    assert plan_label.casefold() in answer3.casefold(), failure_trace
    assert "docker" in answer3.casefold(), failure_trace
    assert turn1_event.event_id in turn3_sources, failure_trace
    assert turn3_sources & turn2_exchange_ids, failure_trace

    # Turn 4 contains almost no standalone semantic content. Correctly resolving
    # "that one" requires the recent dialogue; giving the reason requires either
    # the original historical rule or a prior grounded answer that carried it
    # forward. We deliberately allow either valid retrieval path.
    turn4 = "Why did we rule that one out? Keep it to one sentence."
    answer4 = run_once(turn4, active_conversation)
    _print_turn(4, turn4, answer4)
    turn4_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn4)
    turn4_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn4_event.correlation_id,
    )
    turn3_exchange_ids = _correlation_event_ids(active_conversation, turn3_event.correlation_id)

    failure_trace = _trace(historical_conversation, active_conversation)
    assert re.search(r"virtuali[sz]ation", answer4, re.IGNORECASE), failure_trace
    assert "disabled" in answer4.casefold(), failure_trace
    assert turn4_sources & turn3_exchange_ids, failure_trace
    assert (
        historical_rule_event.event_id in turn4_sources
        or answer2_event.event_id in turn4_sources
    ), failure_trace

    # Structural sanity check: the active conversation really did span four
    # independent external turns and every context-dependent turn invoked memory.
    active_events = _events(active_conversation)
    user_prompts = [event for event in active_events if event.event_type == EventType.USER_PROMPT]
    assert [event.payload["text"] for event in user_prompts] == [turn1, turn2, turn3, turn4]
    for prompt_event in (turn2_event, turn3_event, turn4_event):
        assert any(
            event.event_type == EventType.MEMORY_REQUEST
            and event.correlation_id == prompt_event.correlation_id
            for event in active_events
        ), failure_trace

    # Keep these references live so failures clearly preserve the exact assistant
    # turns whose continuity is being tested.
    assert answer2_event.event_type == EventType.AGENT_RESPONSE
    assert answer3_event.event_type == EventType.AGENT_RESPONSE
    print("\nPASS: immediate context + older relevant history survived fresh-process turns.")
