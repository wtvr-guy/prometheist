"""Real-Ollama v0.7 continuity acceptance through fresh guarded workers.

Every turn launches a new CLI process; that controller launches every durable
stage in another freshly guarded process.  The model therefore receives neither
an inherited transcript nor persistent worker state.
"""
from __future__ import annotations

import json
import re
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
            f"{len(responses)}.\n{_trace(conversation_id)}"
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


def _normalized_answer(answer: str) -> str:
    return " ".join(answer.casefold().replace("\u2019", "'").split())


def _negates_near_subject(
    answer: str,
    *,
    subject: str,
    predicate: str,
    distance: int = 100,
) -> bool:
    negation = r"(?:\b(?:no|neither|not|never)\b|n['\u2019]t\b)"
    return any(
        re.search(pattern, answer) is not None
        for pattern in (
            rf"{subject}[^,.;!?]{{0,{distance}}}{negation}[^,.;!?]{{0,40}}\b(?:{predicate})\b",
            rf"{negation}[^,.;!?]{{0,40}}\b(?:{predicate})\b[^,.;!?]{{0,{distance}}}{subject}",
            rf"{negation}[^,.;!?]{{0,40}}{subject}[^,.;!?]{{0,{distance}}}\b(?:{predicate})\b",
        )
    )


def _contrasts_subject(
    answer: str,
    *,
    subject: str,
    predicate: str,
    distance: int = 100,
) -> bool:
    negation = r"(?:\b(?:not|never)\b|n['\u2019]t\b)"
    return re.search(
        rf"\b(?:{predicate})\b[^.;!?]{{0,{distance}}}{negation}\s+{subject}\b",
        answer,
    ) is not None


def _affirms_docker_compose_conflicts(answer: str) -> bool:
    normalized = _normalized_answer(answer)
    predicate = r"conflicts?|violates?|prohibit(?:ed|s)?|rules? out|ruled out"
    denies = re.search(
        r"\b(?:none|neither)\s+of\s+(?:those|the)\s+approaches?\s+conflicts?\b",
        normalized,
    ) is not None or _negates_near_subject(
        normalized,
        subject=r"docker compose",
        predicate=predicate,
    ) or _contrasts_subject(
        normalized,
        subject=r"docker compose",
        predicate=predicate,
        distance=80,
    )
    positive = (
        rf"(?:docker compose[^,.;!?]{{0,100}}\b(?:{predicate})\b"
        rf"|\b(?:{predicate})\b[^,.;!?]{{0,100}}docker compose)"
    )
    return not denies and re.search(positive, normalized) is not None


def _affirms_docker_compose_was_ruled_out(answer: str) -> bool:
    normalized = _normalized_answer(answer)
    predicate = r"rules?\s+out|ruled\s+out"
    denies = _negates_near_subject(
        normalized,
        subject=r"docker compose",
        predicate=predicate,
    ) or _contrasts_subject(
        normalized,
        subject=r"docker compose",
        predicate=predicate,
        distance=80,
    ) or re.search(
        r"(?:\bnot\b|n['\u2019]t\b)[^,.;!?]{0,30}\brule(?:d)?\b"
        r"[^,.;!?]{0,50}docker compose[^,.;!?]{0,30}\bout\b",
        normalized,
    ) is not None
    positive = (
        r"docker compose[^,.;!?]{0,100}\bruled\s+out\b",
        r"\bruled(?:-|\s+)out\b[^,.;!?]{0,100}docker compose",
        r"\bruled\b[^,.;!?]{0,50}docker compose[^,.;!?]{0,30}\bout\b",
    )
    return not denies and any(re.search(pattern, normalized) for pattern in positive)


def _affirms_virtualization_was_disabled(answer: str) -> bool:
    normalized = _normalized_answer(answer)
    subject = r"virtuali[sz]ation"
    denies = _negates_near_subject(
        normalized,
        subject=subject,
        predicate=r"disabled",
        distance=50,
    ) or _contrasts_subject(
        normalized,
        subject=subject,
        predicate=r"disabled",
        distance=50,
    )
    affirms_enabled = re.search(
        rf"(?:{subject}[^,.;!?]{{0,50}}\benabled\b|\benabled\b[^,.;!?]{{0,50}}{subject})",
        normalized,
    ) is not None and not _negates_near_subject(
        normalized,
        subject=subject,
        predicate=r"enabled",
        distance=50,
    )
    positive = (
        r"(?:virtuali[sz]ation[^,.;!?]{0,40}\bdisabled\b"
        r"|\bdisabled\b[^,.;!?]{0,40}virtuali[sz]ation"
        r"|virtuali[sz]ation[^.!?]{0,80}\bnot enabled\b[^.!?]{0,40}\bdisabled\b)"
    )
    return not denies and not affirms_enabled and re.search(positive, normalized) is not None


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
        "I'm choosing between Docker Compose and running PostgreSQL directly on Windows. "
        "I want to keep the discussion practical."
    )
    answer1 = run_once(turn1, active_conversation)
    _print_turn(1, turn1, answer1)
    turn1_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn1)

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
    assert _affirms_docker_compose_conflicts(answer2), failure_trace
    assert profile_token in answer2, failure_trace
    assert historical_rule_event.event_id in turn2_sources, failure_trace
    assert turn1_event.event_id in turn2_sources, failure_trace

    turn3 = "What nickname are we using for this plan, and which approach did you just rule out?"
    answer3 = run_once(turn3, active_conversation)
    _print_turn(3, turn3, answer3)
    turn3_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn3)
    answer3_event = _response_for_correlation(active_conversation, turn3_event.correlation_id)
    turn3_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn3_event.correlation_id,
    )
    failure_trace = _trace(historical_conversation, active_conversation)
    assert plan_label in answer3, failure_trace
    assert _affirms_docker_compose_was_ruled_out(answer3), failure_trace
    assert turn1_event.event_id in turn3_sources, failure_trace
    assert answer2_event.event_id in turn3_sources, failure_trace

    turn4 = (
        "Name that approach and give the underlying technical reason we ruled it out, "
        "in one sentence."
    )
    answer4 = run_once(turn4, active_conversation)
    _print_turn(4, turn4, answer4)
    turn4_event = _event_for_text(active_conversation, EventType.USER_PROMPT, turn4)
    turn4_sources = _memory_source_ids_for_correlation(
        active_conversation,
        turn4_event.correlation_id,
    )
    failure_trace = _trace(historical_conversation, active_conversation)
    assert _affirms_docker_compose_was_ruled_out(answer4), failure_trace
    assert _affirms_virtualization_was_disabled(answer4), failure_trace
    assert len(re.findall(r"[.!?](?=\s|$)", answer4.strip())) <= 1, failure_trace
    assert answer3_event.event_id in turn4_sources, failure_trace
    assert historical_rule_event.event_id in turn4_sources, failure_trace

    active_events = _events(active_conversation)
    prompts = [event for event in active_events if event.event_type is EventType.USER_PROMPT]
    assert [event.payload["text"] for event in prompts] == [turn1, turn2, turn3, turn4]
    for prompt_event in (turn2_event, turn3_event, turn4_event):
        assert any(
            event.event_type is EventType.MEMORY_REQUEST
            and event.correlation_id == prompt_event.correlation_id
            for event in active_events
        ), failure_trace

    print("\nPASS: v0.7 task/worker continuity preserved recent and older evidence.")
