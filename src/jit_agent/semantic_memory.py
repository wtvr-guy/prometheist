"""Additive, provenance-linked, bi-temporal derived facts about durable subjects.

Canonical events remain the sole evidence of what was actually observed.
``SemanticFact`` is a *derived* belief about the current value of one
``(subject, property)`` pair -- e.g. a preference, a relationship, a role --
distinct from the ``situations``/``expectations`` modules' structured
observation tracking, which is scoped to one bounded, overlapping situation
window rather than a durable cross-conversation belief.

This intentionally follows patterns from external prior art rather than
inventing new vocabulary, adapted to Prometheist's append-only constraints:

- Graphiti (``getzep/graphiti``, ``graphiti_core/edges.py``) represents a
  derived assertion as an ``EntityEdge`` with ``fact``, ``episodes``
  (provenance), and a bi-temporal ``valid_at``/``invalid_at`` (real-world
  validity) versus ``expired_at`` (when Graphiti itself learned the fact no
  longer held) split. Graphiti is backed by a mutable graph database, so it
  implements invalidation by updating the old edge's ``invalid_at``/
  ``expired_at`` in place.  Prometheist's constitution forbids editing a
  historical record (``LOSSLESS_PROGRESSIVE_MEMORY.md``), so this module
  adapts the same bi-temporal idea without ever mutating an existing fact:
  ``valid_from``/``asserted_at`` live on the *new* record, and the old
  record's implicit end-of-validity is always the newer record's
  ``valid_from`` -- discoverable via ``supersedes`` without rewriting
  anything.  This mirrors the ``supersedes: UUID | None`` pattern already
  used by ``situations.Situation`` and ``expectations.Expectation``.
- Mem0 (``mem0ai/mem0``, ``mem0/memory/main.py``) moved its extraction
  pipeline to an "additive" model: new candidate memories are always added,
  and a separate step decides what to do about relationships to existing
  memories, rather than having extraction itself silently rewrite or delete
  history.  ``derive_semantic_fact`` mirrors that split: ``reconcile_fact``
  is a pure, deterministic classification step, kept separate from the
  (single) place that actually persists a new record.

Unlike both Graphiti and Mem0, reconciliation here is fully deterministic
(exact ``(subject, property)`` identity, not vector/LLM similarity), because
the evidence this module consumes is already a structured ``Observation``
(see ``percept_context.py``) rather than free text. Extraction of structured
observations from free text remains a separate, LLM-backed concern for a
future consolidation/reflection worker to own; this module only formalizes
what happens once a candidate observation already exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid5

import psycopg
from pydantic import Field, field_validator

from jit_agent.cognitive_store import COGNITIVE_NAMESPACE, get_record, put_record, record_history
from jit_agent.percept_context import FrozenRecord, Reference, Scalar, aware
from jit_agent.situations import SITUATION_WINDOW

RECORD_KIND = "semantic_fact"


class FactRelation(str, Enum):
    """How a candidate observation relates to the current fact head, if any."""

    INITIAL = "INITIAL"
    """No prior fact exists for this ``(subject, property)``."""

    CORROBORATES = "CORROBORATES"
    """The candidate repeats the current fact's exact value; no new record."""

    SUPERSEDES = "SUPERSEDES"
    """The value changed and the candidate's evidence time is not earlier
    than the current fact's ``valid_from``: an ordinary real-world update."""

    CONTRADICTS = "CONTRADICTS"
    """The value differs and the candidate's evidence time is earlier than
    the current fact's ``valid_from``: two sources disagree about an
    overlapping period. Both remain visible; neither is discarded."""


class SemanticFact(FrozenRecord):
    """One durable, provenance-linked belief about a subject/property value.

    Never mutated once written. A changed belief is always a *new* record
    whose ``supersedes`` points at the fact it replaces; the old record's
    own fields are untouched, so the full history of what Prometheist
    believed at any past moment remains exactly reconstructable.
    """

    fact_id: UUID
    subject: Reference
    property: Reference
    value: Scalar
    unit: Reference | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    # Durable evidence identifiers this fact was derived from: the same
    # percept-identifier evidence space as consolidation.py's existing
    # ``support_percept_ids``, and playing the role Expectation.provenance
    # and Situation.provenance already play for other derived records.
    derived_from: tuple[UUID, ...] = Field(min_length=1, max_length=SITUATION_WINDOW)
    derivation_method: Reference
    valid_from: datetime
    """When the evidence indicates this value became true (real-world time)."""
    asserted_at: datetime
    """When Prometheist derived/recorded this belief (system time).

    Equal to ``valid_from`` for today's deterministic derivation path; a
    future asynchronous reflection worker may derive a fact well after its
    evidence occurred, at which point the two will genuinely diverge.
    """
    supersedes: UUID | None = None
    relation: FactRelation

    _aware = field_validator("valid_from", "asserted_at")(aware)


@dataclass(frozen=True, slots=True)
class FactDerivationResult:
    fact: SemanticFact
    """The current fact after reconciliation: either the pre-existing head
    (``CORROBORATES``, ``created=False``) or the newly written one."""
    created: bool


def semantic_fact_key(subject: str, property: str) -> str:
    """Deterministic ``cognitive_store`` record key for one subject/property."""

    return str(uuid5(COGNITIVE_NAMESPACE, f"semantic-fact:{subject}\x1f{property}"))


def reconcile_fact(
    *,
    candidate_value: Scalar,
    candidate_unit: str | None,
    candidate_observed_at: datetime,
    current: SemanticFact | None,
) -> FactRelation:
    """Pure, deterministic classification of a candidate against the current head."""

    aware(candidate_observed_at)
    if current is None:
        return FactRelation.INITIAL
    if (candidate_value, candidate_unit) == (current.value, current.unit):
        return FactRelation.CORROBORATES
    if candidate_observed_at >= current.valid_from:
        return FactRelation.SUPERSEDES
    return FactRelation.CONTRADICTS


def current_semantic_fact(conn: psycopg.Connection, subject: str, property: str) -> SemanticFact | None:
    data = get_record(conn, RECORD_KIND, semantic_fact_key(subject, property))
    return SemanticFact.model_validate(data) if data is not None else None


def semantic_fact_history(conn: psycopg.Connection, subject: str, property: str) -> tuple[SemanticFact, ...]:
    """Every fact ever derived for one subject/property, oldest first."""

    return tuple(
        SemanticFact.model_validate(data)
        for data in record_history(conn, RECORD_KIND, semantic_fact_key(subject, property))
    )


def semantic_fact_as_of(history: tuple[SemanticFact, ...], at: datetime) -> SemanticFact | None:
    """The fact that was current at a past moment, from an already-loaded history.

    Among facts whose ``valid_from`` is not after ``at``, the one with the
    latest ``valid_from`` was in effect: any later fact necessarily
    superseded whatever came before it, so no explicit chain walk is needed.
    """

    aware(at)
    candidates = [fact for fact in history if fact.valid_from <= at]
    if not candidates:
        return None
    return max(candidates, key=lambda fact: (fact.valid_from, str(fact.fact_id)))


def derive_semantic_fact(
    conn: psycopg.Connection,
    *,
    subject: str,
    property: str,
    value: Scalar,
    unit: str | None = None,
    confidence: float,
    derived_from: tuple[UUID, ...],
    observed_at: datetime,
    asserted_at: datetime,
    derivation_method: str,
) -> FactDerivationResult:
    """Reconcile one candidate observation against the current fact head.

    Additive: a changed value always creates a new record rather than
    editing the old one. A repeated value creates nothing and returns the
    unchanged existing head (``created=False``), so callers cannot spam a
    growing chain of identical facts merely by re-observing the same truth.
    """

    aware(observed_at)
    aware(asserted_at)
    current = current_semantic_fact(conn, subject, property)
    relation = reconcile_fact(
        candidate_value=value, candidate_unit=unit, candidate_observed_at=observed_at, current=current,
    )
    if relation is FactRelation.CORROBORATES:
        assert current is not None  # CORROBORATES is only returned when current exists.
        return FactDerivationResult(fact=current, created=False)

    fact_id = uuid5(
        COGNITIVE_NAMESPACE,
        f"semantic-fact:{subject}\x1f{property}\x1f{observed_at.isoformat()}\x1f{value!r}\x1f{unit}",
    )
    fact = SemanticFact(
        fact_id=fact_id,
        subject=subject,
        property=property,
        value=value,
        unit=unit,
        confidence=confidence,
        derived_from=derived_from,
        derivation_method=derivation_method,
        valid_from=observed_at,
        asserted_at=asserted_at,
        supersedes=current.fact_id if current is not None else None,
        relation=relation,
    )
    put_record(
        conn, RECORD_KIND, semantic_fact_key(subject, property), fact.model_dump(mode="json"), revision=str(fact_id),
    )
    return FactDerivationResult(fact=fact, created=True)
