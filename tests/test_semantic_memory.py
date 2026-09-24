from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from jit_agent import db
from jit_agent.semantic_memory import (
    FactRelation,
    current_semantic_fact,
    derive_semantic_fact,
    reconcile_fact,
    semantic_fact_as_of,
    semantic_fact_history,
    semantic_fact_key,
)


@pytest.fixture
def conn():
    with db.get_connection() as connection:
        yield connection


def _at(offset_minutes: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=offset_minutes)


# --- reconcile_fact: pure, deterministic classification -------------------


def test_reconcile_fact_is_initial_with_no_current_fact():
    relation = reconcile_fact(
        candidate_value="latte", candidate_unit=None, candidate_observed_at=_at(0), current=None,
    )
    assert relation is FactRelation.INITIAL


def test_reconcile_fact_corroborates_identical_value(conn):
    result = derive_semantic_fact(
        conn, subject="person:mike", property="preferred_drink", value="latte", confidence=0.9,
        derived_from=(uuid4(),), observed_at=_at(0), asserted_at=_at(0), derivation_method="test/v1",
    )
    relation = reconcile_fact(
        candidate_value="latte", candidate_unit=None, candidate_observed_at=_at(5), current=result.fact,
    )
    assert relation is FactRelation.CORROBORATES


def test_reconcile_fact_supersedes_when_value_changes_later():
    relation = reconcile_fact(
        candidate_value="espresso", candidate_unit=None, candidate_observed_at=_at(10),
        current=_fact(value="latte", valid_from=_at(0)),
    )
    assert relation is FactRelation.SUPERSEDES


def test_reconcile_fact_contradicts_when_value_differs_earlier():
    relation = reconcile_fact(
        candidate_value="espresso", candidate_unit=None, candidate_observed_at=_at(-10),
        current=_fact(value="latte", valid_from=_at(0)),
    )
    assert relation is FactRelation.CONTRADICTS


def _fact(*, value, valid_from):
    from jit_agent.semantic_memory import SemanticFact

    return SemanticFact(
        fact_id=uuid4(), subject="person:mike", property="preferred_drink", value=value, unit=None,
        confidence=1.0, derived_from=(uuid4(),), derivation_method="test/v1",
        valid_from=valid_from, asserted_at=valid_from, supersedes=None, relation=FactRelation.INITIAL,
    )


# --- semantic_fact_as_of: pure history lookup -----------------------------


def test_semantic_fact_as_of_returns_none_before_any_evidence():
    history = (_fact(value="latte", valid_from=_at(10)),)
    assert semantic_fact_as_of(history, _at(0)) is None


def test_semantic_fact_as_of_returns_the_fact_in_effect_at_a_past_moment():
    early = _fact(value="latte", valid_from=_at(0))
    later = _fact(value="espresso", valid_from=_at(20))
    history = (early, later)
    assert semantic_fact_as_of(history, _at(10)) == early
    assert semantic_fact_as_of(history, _at(20)) == later
    assert semantic_fact_as_of(history, _at(100)) == later


# --- derive_semantic_fact: additive, non-destructive persistence ---------


def test_derive_semantic_fact_creates_an_initial_fact(conn):
    source_event = uuid4()
    result = derive_semantic_fact(
        conn, subject="person:mike", property="preferred_drink", value="latte", confidence=0.8,
        derived_from=(source_event,), observed_at=_at(0), asserted_at=_at(0),
        derivation_method="consolidation/v1",
    )
    assert result.created is True
    assert result.fact.relation is FactRelation.INITIAL
    assert result.fact.supersedes is None
    assert result.fact.derived_from == (source_event,)
    assert current_semantic_fact(conn, "person:mike", "preferred_drink") == result.fact


def test_derive_semantic_fact_is_additive_for_repeated_evidence(conn):
    first = derive_semantic_fact(
        conn, subject="person:mike", property="preferred_drink", value="latte", confidence=0.8,
        derived_from=(uuid4(),), observed_at=_at(0), asserted_at=_at(0), derivation_method="test/v1",
    )
    second = derive_semantic_fact(
        conn, subject="person:mike", property="preferred_drink", value="latte", confidence=0.95,
        derived_from=(uuid4(),), observed_at=_at(30), asserted_at=_at(30), derivation_method="test/v1",
    )
    assert second.created is False
    assert second.fact == first.fact
    assert len(semantic_fact_history(conn, "person:mike", "preferred_drink")) == 1


def test_derive_semantic_fact_supersedes_without_mutating_the_old_record(conn):
    original = derive_semantic_fact(
        conn, subject="person:mike", property="preferred_drink", value="latte", confidence=0.8,
        derived_from=(uuid4(),), observed_at=_at(0), asserted_at=_at(0), derivation_method="test/v1",
    )
    events_before = conn.execute("SELECT event_id, payload FROM events ORDER BY global_seq").fetchall()

    changed = derive_semantic_fact(
        conn, subject="person:mike", property="preferred_drink", value="espresso", confidence=0.9,
        derived_from=(uuid4(),), observed_at=_at(60), asserted_at=_at(60), derivation_method="test/v1",
    )

    assert changed.created is True
    assert changed.fact.relation is FactRelation.SUPERSEDES
    assert changed.fact.supersedes == original.fact.fact_id
    # The old record's own canonical event bytes are completely untouched.
    events_after = conn.execute("SELECT event_id, payload FROM events ORDER BY global_seq").fetchall()
    assert events_after[: len(events_before)] == events_before

    history = semantic_fact_history(conn, "person:mike", "preferred_drink")
    assert history == (original.fact, changed.fact)
    assert current_semantic_fact(conn, "person:mike", "preferred_drink") == changed.fact
    assert semantic_fact_as_of(history, _at(30)) == original.fact
    assert semantic_fact_as_of(history, _at(90)) == changed.fact


def test_derive_semantic_fact_contradicts_without_discarding_either_fact(conn):
    current = derive_semantic_fact(
        conn, subject="person:mike", property="job_title", value="engineer", confidence=0.9,
        derived_from=(uuid4(),), observed_at=_at(100), asserted_at=_at(100), derivation_method="test/v1",
    )
    backfilled = derive_semantic_fact(
        conn, subject="person:mike", property="job_title", value="manager", confidence=0.6,
        derived_from=(uuid4(),), observed_at=_at(10), asserted_at=_at(100), derivation_method="test/v1",
    )
    assert backfilled.created is True
    assert backfilled.fact.relation is FactRelation.CONTRADICTS
    assert backfilled.fact.supersedes == current.fact.fact_id
    history = semantic_fact_history(conn, "person:mike", "job_title")
    assert set(history) == {current.fact, backfilled.fact}
    # Neither belief silently vanished; both remain forensically visible.
    assert current.fact in history and backfilled.fact in history


def test_semantic_fact_key_is_deterministic_and_distinguishes_property():
    assert semantic_fact_key("person:mike", "preferred_drink") == semantic_fact_key("person:mike", "preferred_drink")
    assert semantic_fact_key("person:mike", "preferred_drink") != semantic_fact_key("person:mike", "job_title")
    assert semantic_fact_key("person:mike", "preferred_drink") != semantic_fact_key("person:jane", "preferred_drink")


def test_semantic_fact_history_is_empty_for_unknown_subject(conn):
    assert semantic_fact_history(conn, "person:unknown", "preferred_drink") == ()
    assert current_semantic_fact(conn, "person:unknown", "preferred_drink") is None
