from datetime import datetime, timezone
import uuid

from jit_agent.evidence_composer import compose_relevance_coverage
from jit_agent.models import EventType, MemoryEvidence


def _evidence(
    text: str,
    *,
    score: float,
    seq: int,
    source: str = "memory",
    conversation_id: uuid.UUID = uuid.NAMESPACE_URL,
    provenance: tuple[uuid.UUID, ...] = (),
) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid.uuid5(uuid.NAMESPACE_URL, f"v2:{seq}:{text}:{source}"),
        event_type=EventType.USER_PROMPT,
        source=source,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        conversation_id=conversation_id,
        conversation_seq=seq,
        global_seq=seq,
        content=text,
        score=score,
        retrieval_reasons=["LEXICAL"],
        provenance_event_ids=list(provenance),
    )


def _selected_ids(result):
    return {item.source_event_id for item in result.items}


def test_v2_preserves_standalone_numeric_facts_against_lexical_bait():
    required = [
        _evidence(f"calibration threshold value {10 * (index + 1)}", score=1.0 - index * 0.01, seq=index)
        for index in range(6)
    ]
    bait = [
        _evidence(
            f"calibration threshold commentary zephyr{index} quartz{index} nebula{index}",
            score=0.8 - index * 0.01,
            seq=100 + index,
        )
        for index in range(8)
    ]

    result = compose_relevance_coverage([*required, *bait], limit=6)

    assert _selected_ids(result) == {item.source_event_id for item in required}


def test_v2_spends_duplicate_core_slots_on_lower_rank_unique_evidence():
    repetitive = [
        _evidence(f"orbit cedar amber repetitive update-{index}", score=0.95, seq=100 + index)
        for index in range(6)
    ]
    target = _evidence(
        "orbit cedar amber decisive exception cobalt",
        score=0.4,
        seq=1,
    )

    result = compose_relevance_coverage([*repetitive, target], limit=6)

    assert target.source_event_id in _selected_ids(result)
    assert any(decision.selection_role == "augmentation" for decision in result.decisions)


def test_v2_preserves_repeated_content_from_independent_provenance():
    repeated = [
        _evidence(
            "independent check confirms reactor seal remained intact",
            score=1.0 - index * 0.01,
            seq=index,
            provenance=(uuid.uuid5(uuid.NAMESPACE_OID, f"witness:{index}"),),
        )
        for index in range(4)
    ]
    filler = [
        _evidence(f"reactor seal filler-{index}", score=0.8 - index * 0.01, seq=20 + index)
        for index in range(4)
    ]

    result = compose_relevance_coverage([*repeated, *filler], limit=6)

    selected = _selected_ids(result)
    assert all(item.source_event_id in selected for item in repeated)


def test_v2_does_not_let_stale_retained_evidence_evict_nonredundant_core():
    current = [
        _evidence(f"current verified state component item{index}", score=1.0 - index * 0.01, seq=index)
        for index in range(6)
    ]
    stale = _evidence(
        "obsolete superseded hypothesis from prior attention round",
        score=0.01,
        seq=900,
        source="stale",
    )

    result = compose_relevance_coverage(current, retained=[stale], limit=6)

    assert _selected_ids(result) == {item.source_event_id for item in current}


def test_v2_retains_unique_prior_evidence_when_current_core_is_redundant():
    current = [
        _evidence(f"obsolete explanation reinforcement-{index}", score=0.9, seq=100 + index)
        for index in range(6)
    ]
    retained = _evidence(
        "escape correction canonical fact",
        score=0.7,
        seq=1,
    )

    result = compose_relevance_coverage(current, retained=[retained], limit=6)

    assert retained.source_event_id in _selected_ids(result)


def test_v2_is_deterministic_for_identical_inputs():
    candidates = [
        _evidence("same fact repeated", score=0.9, seq=1),
        _evidence("same fact repeated", score=0.9, seq=2),
        _evidence("different fact", score=0.5, seq=3),
    ]

    first = compose_relevance_coverage(candidates, limit=2)
    second = compose_relevance_coverage(candidates, limit=2)

    assert first == second
