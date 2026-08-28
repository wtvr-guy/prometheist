"""Real-Ollama v0.7 continuity acceptance through fresh guarded workers.

Every turn launches a new CLI process; that controller launches every durable
stage in another freshly guarded process. The model therefore receives neither
an inherited transcript nor persistent worker state.

This experiment does not implement a hand-written natural-language semantic
parser. Where a deterministic behavioral verdict is required, the test asks for
an exact machine-verifiable value/tuple. Canonical MemoryPacket provenance is
checked independently so a correct-looking answer cannot pass without the
required source evidence being available to the fresh worker.
"""
from __future__ import annotations

import json
import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.models import EventType
from tests._cli_helpers import ollama_available, print_transcript, run_once


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


def _events(conversation_id: uuid.UUID):
    with db.get_connection() as conn:
        return event_store.get_events_by_conversation(conn, conversation_id)


def _event_by_id(event_id: uuid.UUID):
    with db.get_connection() as conn:
        return event_store.get_event_by_id(conn, event_id)


def _compact_memory_item(item: dict) -> dict:
    content = item.get("content")
    if (
        item.get("event_type") == EventType.SYSTEM_EVENT.value
        and item.get("source") == "pre_cognitive_response_finalizer"
        and isinstance(content, str)
        and "INTERACTION_WORKPIECE_SNAPSHOT" in content
    ):
        content = "<interaction workpiece snapshot omitted>"
    return {
        "source_event_id": item.get("source_event_id"),
        "event_type": item.get("event_type"),
        "source": item.get("source"),
        "score": item.get("score"),
        "content": content,
    }


def _compact_event_payload(event) -> dict | None:
    payload = event.payload
    if event.event_type in {EventType.USER_PROMPT, EventType.INTERACTION_RESPONSE}:
        return {"text": payload.get("text")}
    if event.event_type is EventType.MEMORY_PACKET:
        packet = payload.get("packet", {})
        return {
            "memory_request_id": packet.get("memory_request_id"),
            "supported": packet.get("supported"),
            "items": [_compact_memory_item(item) for item in packet.get("items", [])],
        }
    if event.event_type is EventType.SYSTEM_EVENT:
        kind = payload.get("kind")
        if kind == "PRE_COGNITIVE_ASSESSMENT":
            return {"kind": kind, "assessment": payload.get("assessment")}
        if kind == "FINAL_RESPONSE_DIRECTIVE":
            return {"kind": kind, "directive": payload.get("directive")}
        if kind == "INTERACTION_WORKPIECE_SNAPSHOT":
            workpiece = payload.get("workpiece", {})
            return {
                "kind": kind,
                "component_types": [
                    component.get("component_type")
                    for component in workpiece.get("components", [])
                ],
            }
    return None


def _compact_event_line(prefix: str, event) -> str:
    payload = _compact_event_payload(event)
    return (
        f"{prefix}seq={event.conversation_seq} type={event.event_type.value} "
        f"source={event.source} correlation={event.correlation_id} "
        f"payload={json.dumps(payload, sort_keys=True, default=str)}"
    )


def _trace(*conversation_ids: uuid.UUID) -> str:
    lines: list[str] = []
    for conversation_id in conversation_ids:
        lines.append(f"conversation={conversation_id}")
        for event in _events(conversation_id):
            if _compact_event_payload(event) is not None:
                lines.append(_compact_event_line("  ", event))
    return "\n".join(lines)


def _failure_trace(
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    *expected_source_event_ids: uuid.UUID,
) -> str:
    lines = [
        f"failing_conversation={conversation_id}",
        f"failing_correlation={correlation_id}",
    ]
    if expected_source_event_ids:
        lines.append("expected_source_anchors:")
        for event_id in expected_source_event_ids:
            event = _event_by_id(event_id)
            if event is None:
                lines.append(f"  missing event={event_id}")
            else:
                lines.append(_compact_event_line("  ", event))

    lines.append("failing_turn_events:")
    for event in _events(conversation_id):
        if event.correlation_id != correlation_id:
            continue
        if _compact_event_payload(event) is not None:
            lines.append(_compact_event_line("  ", event))
    return "\n".join(lines)


def _event_for_text(conversation_id: uuid.UUID, event_type: EventType, text: str):
    for event in _events(conversation_id):
        if event.event_type is event_type and event.payload.get("text") == text:
            return event
    raise AssertionError(
        f"No {event_type.value} event with exact text {text!r}.\n{_trace(conversation_id)}"
    )


def _response_for_correlation(conversation_id: uuid.UUID, correlation_id: uuid.UUID):
    responses = [
        event
        for event in _events(conversation_id)
        if event.correlation_id == correlation_id
        and event.event_type is EventType.INTERACTION_RESPONSE
    ]
    if len(responses) != 1:
        raise AssertionError(
            f"Expected one INTERACTION_RESPONSE for {correlation_id}, got "
            f"{len(responses)}.\n{_failure_trace(conversation_id, correlation_id)}"
        )
    return responses[0]


def _memory_source_ids_for_correlation(
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
) -> set[uuid.UUID]:
    source_ids: set[uuid.UUID] = set()
    for event in _events(conversation_id):
        if event.correlation_id != correlation_id or event.event_type is not EventType.MEMORY_PACKET:
            continue
        for item in event.payload.get("packet", {}).get("items", []):
            source_ids.add(uuid.UUID(item["source_event_id"]))
    return source_ids


def _seed_distractors(count: int = 12) -> None:
    with db.get_connection() as conn:
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


def _print_turn(number: int, prompt: str, answer: str) -> None:
    print_transcript(f"\nTurn {number} — User:\n{prompt}")
    print_transcript(f"\nTurn {number} — Prometheist:\n{answer}")


def test_stateless_four_turn_continuity_survives_sessions_and_distractors():
    historical_conversation = uuid.uuid4()
    active_conversation = uuid.uuid4()
    profile_token = f"VX-{uuid.uuid4().hex[:8].upper()}"
    plan_label = f"BlueHarbor-{uuid.uuid4().hex[:6].upper()}"

    historical_rule = (
        "For Project Kestrel, never use Docker; deploy PostgreSQL directly on Windows "
        f"because virtualization is disabled. I track that constraint under profile {profile_token}."
    )
    historical_answer = run_once(historical_rule, historical_conversation)
    print_transcript(f"\nHistorical seed — User:\n{historical_rule}")
    print_transcript(f"\nHistorical seed — Prometheist:\n{historical_answer}")
    historical_rule_event = _event_for_text(
        historical_conversation,
        EventType.USER_PROMPT,
        historical_rule,
    )
    _seed_distractors()

    turn1 = (
        f"I'm revisiting Project Kestrel. For this conversation, call the plan {plan_label}. "
        "I'm choosing between Docker Compose and PostgreSQL directly on Windows. "
        "Based on my established constraints, choose the compatible approach. "
        "Return exactly one of these labels and nothing else: "
        "Docker Compose | PostgreSQL directly on Windows."
    )
    answer1 = run_once(turn1, active_conversation)
    _print_turn(1, turn1, answer1)
    turn1_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn1)
    turn1_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn1_event.correlation_id,
    )
    failure_trace = _failure_trace(
        active_conversation,
        turn1_event.correlation_id,
        historical_rule_event.event_id,
    )
    assert answer1.strip() == "PostgreSQL directly on Windows", failure_trace
    assert historical_rule_event.event_id in turn1_sources, failure_trace

    turn2 = (
        "Which approach conflicts with my established Kestrel rule, and what constraint "
        "profile did I give that rule? Return exactly '<approach> | <profile>' and nothing else."
    )
    answer2 = run_once(turn2, active_conversation)
    _print_turn(2, turn2, answer2)
    turn2_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn2)
    answer2_event = _response_for_correlation(active_conversation, turn2_event.correlation_id)
    turn2_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn2_event.correlation_id,
    )
    failure_trace = _failure_trace(
        active_conversation,
        turn2_event.correlation_id,
        historical_rule_event.event_id,
        turn1_event.event_id,
    )
    assert answer2.strip() == f"Docker Compose | {profile_token}", failure_trace
    assert historical_rule_event.event_id in turn2_sources, failure_trace
    assert turn1_event.event_id in turn2_sources, failure_trace

    turn3 = (
        "What nickname are we using for this plan, and which approach did you just rule out? "
        "Return exactly '<nickname> | <approach>' and nothing else."
    )
    answer3 = run_once(turn3, active_conversation)
    _print_turn(3, turn3, answer3)
    turn3_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn3)
    answer3_event = _response_for_correlation(active_conversation, turn3_event.correlation_id)
    turn3_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn3_event.correlation_id,
    )
    failure_trace = _failure_trace(
        active_conversation,
        turn3_event.correlation_id,
        turn1_event.event_id,
        answer2_event.event_id,
    )
    assert answer3.strip() == f"{plan_label} | Docker Compose", failure_trace
    assert turn1_event.event_id in turn3_sources, failure_trace
    assert answer2_event.event_id in turn3_sources, failure_trace

    turn4 = (
        "Name that ruled-out approach and its underlying technical reason. "
        "Return exactly '<approach> | <reason>' and use the reason wording from my established rule."
    )
    answer4 = run_once(turn4, active_conversation)
    _print_turn(4, turn4, answer4)
    turn4_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn4)
    turn4_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn4_event.correlation_id,
    )
    failure_trace = _failure_trace(
        active_conversation,
        turn4_event.correlation_id,
        answer3_event.event_id,
        historical_rule_event.event_id,
    )
    assert answer4.strip() == "Docker Compose | virtualization is disabled", failure_trace
    assert answer3_event.event_id in turn4_sources, failure_trace
    assert historical_rule_event.event_id in turn4_sources, failure_trace

    active_events = _events(active_conversation)
    prompts = [event for event in active_events if event.event_type is EventType.USER_PROMPT]
    assert [event.payload["text"] for event in prompts] == [turn1, turn2, turn3, turn4]
    for prompt_event in (turn1_event, turn2_event, turn3_event, turn4_event):
        assert any(
            event.event_type is EventType.MEMORY_REQUEST
            and event.correlation_id == prompt_event.correlation_id
            for event in active_events
        ), failure_trace

    print("\nPASS: v0.7 task/worker continuity preserved recent and older evidence.")
