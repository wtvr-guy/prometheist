from datetime import datetime, timezone
import uuid

from jit_agent.evidence_composer import compose_coverage_aware
from jit_agent.models import EventType, MemoryEvidence


def _evidence(
    text: str,
    *,
    score: float,
    seq: int,
    source: str = "benchmark-user",
    reasons: tuple[str, ...] = ("DIRECT_CUE",),
    provenance: tuple[uuid.UUID, ...] = (),
) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid.uuid5(uuid.NAMESPACE_URL, f"evidence:{seq}:{text}"),
        event_type=EventType.USER_PROMPT,
        source=source,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        conversation_id=uuid.NAMESPACE_URL,
        conversation_seq=seq,
        global_seq=seq,
        content=text,
        score=score,
        retrieval_reasons=list(reasons),
        provenance_event_ids=list(provenance),
    )


def test_composer_preserves_strongest_current_candidate_first():
    strongest = _evidence("shared cue newest", score=0.9, seq=3)
    diverse = _evidence("completely different evidence", score=0.5, seq=2)

    result = compose_coverage_aware([strongest, diverse], limit=2)

    assert result.items[0].source_event_id == strongest.source_event_id


def test_composer_breaks_near_duplicate_recency_starvation():
    distractors = [
        _evidence(f"amber cedar orbit distractor-{index}", score=0.81, seq=100 + index)
        for index in range(12)
    ]
    target = _evidence(
        "amber cedar orbit exact phrase identifies CANDIDATE-TARGET",
        score=0.81,
        seq=1,
    )
    ranked = [*reversed(distractors), target]

    result = compose_coverage_aware(ranked, limit=6)

    assert target.source_event_id in {item.source_event_id for item in result.items}


def test_composer_preserves_distributed_weak_clues_against_duplicate_flood():
    distractors = [
        _evidence(f"project decision exact-looking distractor-{index}", score=0.95, seq=200 + index)
        for index in range(18)
    ]
    clues = [
        _evidence("project decision clue alpha mentions thermal ceiling", score=0.4, seq=10),
        _evidence("project decision clue beta records memory pressure", score=0.39, seq=11),
        _evidence("project decision clue gamma links scheduler headroom", score=0.38, seq=12),
    ]

    result = compose_coverage_aware([*reversed(distractors), *clues], limit=6)
    selected = {item.source_event_id for item in result.items}

    assert all(clue.source_event_id in selected for clue in clues)


def test_retained_unique_evidence_survives_noninformative_new_round():
    retained_target = _evidence(
        "escape correction canonical fact",
        score=0.7,
        seq=1,
    )
    current = [
        _evidence(f"obsolete explanation reinforcement-{index}", score=0.9, seq=300 + index)
        for index in range(12)
    ]

    result = compose_coverage_aware(
        list(reversed(current)),
        retained=[retained_target],
        limit=6,
    )

    assert retained_target.source_event_id in {
        item.source_event_id for item in result.items
    }


def test_composer_is_deterministic_for_identical_inputs():
    candidates = [
        _evidence("shared cue newest", score=0.9, seq=3),
        _evidence("shared cue alternative", score=0.8, seq=2),
        _evidence("different provenance route", score=0.7, seq=1),
    ]

    first = compose_coverage_aware(candidates, limit=2)
    second = compose_coverage_aware(candidates, limit=2)

    assert [item.source_event_id for item in first.items] == [
        item.source_event_id for item in second.items
    ]
    assert first.decisions == second.decisions
