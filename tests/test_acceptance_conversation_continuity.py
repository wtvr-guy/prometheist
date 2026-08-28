"""Real-Ollama v0.7 continuity acceptance through fresh guarded workers.

Every turn launches a new CLI process; that controller launches every durable
stage in another freshly guarded process. The model therefore receives neither
an inherited transcript nor persistent worker state.

The automated oracle stops at the final response boundary.  It verifies that
the fresh responder receives the correct policy-admitted canonical evidence and
durable response authority, while the actual natural-language response remains
visible in the native test transcript for human inspection.  This avoids
optimizing Prometheist for canned machine-shaped prose merely because exact
string equality is convenient for pytest.
"""
from __future__ import annotations

import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.models import EventType
from jit_agent.response_policy import ResponseSurfaceMode
from tests._cli_helpers import ollama_available, print_transcript, run_once
from tests._native_final_response import (
    assert_final_responder_has,
    event_for_text,
    events,
    final_responder_view,
)


pytestmark = [
    pytest.mark.ollama,
    pytest.mark.skipif(not ollama_available(), reason="Ollama is not reachable"),
]


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
    historical_rule_event = event_for_text(
        historical_conversation,
        EventType.USER_PROMPT,
        historical_rule,
    )
    _seed_distractors()

    turn1 = (
        f"I'm revisiting Project Kestrel, and for this conversation let's call the plan "
        f"{plan_label}. Based on the deployment constraint I gave you before, how should I "
        "deploy its database?"
    )
    answer1 = run_once(turn1, active_conversation)
    _print_turn(1, turn1, answer1)
    turn1_event = event_for_text(active_conversation, EventType.USER_PROMPT, turn1)
    turn1_view = final_responder_view(active_conversation, turn1)
    assert_final_responder_has(
        turn1_view,
        required_source_event_ids=(historical_rule_event.event_id,),
        required_literals=("PostgreSQL directly on Windows", "virtualization is disabled"),
        expected_surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
    )

    turn2 = (
        "What profile did I attach to that Kestrel deployment rule, and what technical "
        "limitation was behind it?"
    )
    answer2 = run_once(turn2, active_conversation)
    _print_turn(2, turn2, answer2)
    turn2_event = event_for_text(active_conversation, EventType.USER_PROMPT, turn2)
    turn2_view = final_responder_view(active_conversation, turn2)
    assert_final_responder_has(
        turn2_view,
        required_source_event_ids=(historical_rule_event.event_id,),
        required_literals=(profile_token, "virtualization is disabled"),
        expected_surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
    )

    turn3 = (
        "What nickname did I just give this Kestrel plan, and which database deployment "
        "approach is compatible with the constraint?"
    )
    answer3 = run_once(turn3, active_conversation)
    _print_turn(3, turn3, answer3)
    turn3_event = event_for_text(active_conversation, EventType.USER_PROMPT, turn3)
    turn3_view = final_responder_view(active_conversation, turn3)
    assert_final_responder_has(
        turn3_view,
        required_source_event_ids=(turn1_event.event_id, historical_rule_event.event_id),
        required_literals=(plan_label, "PostgreSQL directly on Windows"),
        expected_surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
    )

    turn4 = (
        "Give me a short recap of the Kestrel plan we've established so far, including the "
        "nickname, the database deployment approach, and why Docker isn't appropriate."
    )
    answer4 = run_once(turn4, active_conversation)
    _print_turn(4, turn4, answer4)
    turn4_event = event_for_text(active_conversation, EventType.USER_PROMPT, turn4)
    turn4_view = final_responder_view(active_conversation, turn4)
    assert_final_responder_has(
        turn4_view,
        required_source_event_ids=(turn1_event.event_id, historical_rule_event.event_id),
        required_literals=(
            plan_label,
            "PostgreSQL directly on Windows",
            "virtualization is disabled",
        ),
        expected_surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE,
    )

    active_events = events(active_conversation)
    prompts = [event for event in active_events if event.event_type is EventType.USER_PROMPT]
    assert [event.payload["text"] for event in prompts] == [turn1, turn2, turn3, turn4]
    for prompt_event in (turn1_event, turn2_event, turn3_event, turn4_event):
        assert any(
            event.event_type is EventType.MEMORY_REQUEST
            and event.correlation_id == prompt_event.correlation_id
            for event in active_events
        )

    print(
        "\nPASS: v0.7 fresh responders received the required recent and historical "
        "evidence across all four conversational turns."
    )
