from datetime import datetime, timezone

from jit_agent.memory_kernel import CueState, MemoryEvent, recall


def ev(event_id: str, seq: int, text: str, *, entities=()):
    return MemoryEvent(
        event_id=event_id,
        global_seq=seq,
        conversation_id="c1",
        conversation_seq=seq,
        event_type="USER_PROMPT",
        source="user",
        created_at=datetime(2026, 1, seq, tzinfo=timezone.utc),
        text=text,
        payload={"entities": list(entities)},
    )


def test_recall_is_deterministic_and_bounded():
    events = [
        ev("a", 1, "I like black coffee", entities=("coffee",)),
        ev("b", 2, "I bought a bicycle", entities=("bicycle",)),
        ev("c", 3, "Black coffee is still my morning drink", entities=("coffee",)),
    ]
    cue = CueState(query_text="What coffee do I drink?", entities=("coffee",), limit=2)

    first = recall(events, cue)
    second = recall(events, cue)

    assert first == second
    assert len(first.items) == 2
    assert [item.event_id for item in first.items] == ["c", "a"]
    assert first.trace.policy_version == "deterministic-cues-v1"
    assert all(item.reasons for item in first.trace.items)


def test_unknown_query_returns_no_evidence_instead_of_nearest_noise():
    events = [ev("a", 1, "I like black coffee"), ev("b", 2, "I drive a Toyota")]
    packet = recall(events, CueState(query_text="What is my favorite color?", limit=5))
    assert packet.items == ()


def test_no_cues_returns_newest_history():
    events = [ev("a", 1, "first"), ev("b", 2, "second"), ev("c", 3, "third")]
    packet = recall(events, CueState(limit=2))
    assert [item.event_id for item in packet.items] == ["c", "b"]
