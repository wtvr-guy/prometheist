"""Deterministic association derivation for Prometheist Memory Kernel v0.4.

Canonical events remain authoritative evidence.  This module derives a small,
versioned association projection from those events using explicit rules.  The
projection is disposable and reproducible; deleting it never deletes memory.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

from jit_agent.associative_memory import Association
from jit_agent.memory_kernel import MemoryEvent, normalize_text, tokenize

ASSOCIATION_PROJECTION_NAME = "associations"
ASSOCIATION_PROJECTION_VERSION = "1"

# Small deterministic ontology used by the v0.4 experiment.  These are general
# concept aliases, not benchmark-answer edges.  Adding a concept changes the
# projection version and must be benchmarked as a policy change.
_CONCEPT_TERMS: dict[str, frozenset[str]] = {
    "beverage": frozenset(
        {
            "beverage",
            "drink",
            "coffee",
            "latte",
            "espresso",
            "cappuccino",
            "mocha",
            "tea",
            "chai",
        }
    ),
    "vehicle": frozenset(
        {
            "vehicle",
            "car",
            "sedan",
            "suv",
            "truck",
            "motorcycle",
            "corolla",
            "civic",
            "outback",
            "escape",
        }
    ),
}

_CHANGE_PHRASES = (
    "stopped ",
    "stop ",
    "switched ",
    "switch ",
    "changed ",
    "change ",
    "started ",
    "start ",
    "no longer ",
    "quit ",
)
_UNRESOLVED_PHRASES = (
    "owes me",
    "owed me",
    "still owes",
    "hasn't returned",
    "has not returned",
    "waiting for",
)
_RESOLVED_PHRASES = (
    "returned",
    "refunded",
    "repaid",
    "paid me back",
    "got back",
)
_ACQUISITION_PHRASES = (
    "bought ",
    "purchased ",
    "leased ",
    "acquired ",
    "i own ",
)


def _event_terms(event: MemoryEvent) -> set[str]:
    values = [event.text]
    values.extend(
        str(value)
        for value in event.payload.get("entities", [])
        if isinstance(value, (str, int, float))
    )
    return {token for value in values for token in tokenize(value)}


def _concepts(event: MemoryEvent) -> set[str]:
    terms = _event_terms(event)
    return {
        concept
        for concept, aliases in _CONCEPT_TERMS.items()
        if terms & aliases
    }


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in phrases)


def _entity_terms(event: MemoryEvent) -> set[str]:
    return {
        token
        for value in event.payload.get("entities", [])
        if isinstance(value, (str, int, float))
        for token in tokenize(str(value))
        if len(token) > 2
    }


def _association_id(
    relationship: str,
    source_kind: str,
    source: str,
    target_kind: str,
    target: str,
) -> str:
    canonical = "|".join(
        (
            ASSOCIATION_PROJECTION_VERSION,
            relationship,
            source_kind,
            source,
            target_kind,
            target,
        )
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
    return f"derived-{digest}"


def derive_associations(events: Iterable[MemoryEvent]) -> tuple[Association, ...]:
    """Derive reproducible routing associations solely from source events.

    v0.4 intentionally implements only three rule families that correspond to
    previously demonstrated retrieval gaps:

    * PREVIOUS_STATE: a change event links to the nearest earlier same-source
      event in the same coarse concept class, gated by the cue ``before``;
    * RESOLVED_BY: an unresolved event links to a later resolution sharing
      explicit entity terms, gated by the cue ``recover``;
    * CONCEPT_INSTANCE: acquisition/ownership evidence for a recognized vehicle
      links the general term ``vehicle`` to that evidence.

    Every edge carries the source event IDs that justify it.  No edge contains
    facts not present in those events.
    """
    ordered = tuple(sorted(events, key=lambda event: (event.global_seq, event.event_id)))
    concepts_by_id = {event.event_id: _concepts(event) for event in ordered}
    derived: dict[str, Association] = {}

    # Historical-state links.
    for index, event in enumerate(ordered):
        if not _contains_any(event.text, _CHANGE_PHRASES):
            continue
        event_concepts = concepts_by_id[event.event_id]
        if not event_concepts:
            continue
        for concept in sorted(event_concepts):
            previous = next(
                (
                    candidate
                    for candidate in reversed(ordered[:index])
                    if candidate.source == event.source
                    and concept in concepts_by_id[candidate.event_id]
                ),
                None,
            )
            if previous is None:
                continue
            association_id = _association_id(
                "PREVIOUS_STATE", "EVENT", event.event_id, "EVENT", previous.event_id
            )
            derived[association_id] = Association(
                association_id=association_id,
                source_kind="EVENT",
                source=event.event_id,
                target_kind="EVENT",
                target=previous.event_id,
                relationship="PREVIOUS_STATE",
                strength=1.0,
                provenance_event_ids=(previous.event_id, event.event_id),
                required_cue_terms=("before",),
            )

    # Resolution links.  Explicit entity overlap is required so generic words
    # such as "returned" cannot connect unrelated episodes.
    for later_index, later in enumerate(ordered):
        if not _contains_any(later.text, _RESOLVED_PHRASES):
            continue
        later_entities = _entity_terms(later)
        if not later_entities:
            continue
        previous = next(
            (
                earlier
                for earlier in reversed(ordered[:later_index])
                if _contains_any(earlier.text, _UNRESOLVED_PHRASES)
                and bool(_entity_terms(earlier) & later_entities)
            ),
            None,
        )
        if previous is None:
            continue
        association_id = _association_id(
            "RESOLVED_BY", "EVENT", previous.event_id, "EVENT", later.event_id
        )
        derived[association_id] = Association(
            association_id=association_id,
            source_kind="EVENT",
            source=previous.event_id,
            target_kind="EVENT",
            target=later.event_id,
            relationship="RESOLVED_BY",
            strength=1.0,
            provenance_event_ids=(previous.event_id, later.event_id),
            required_cue_terms=("recover",),
        )

    # General-concept links only for evidence that asserts acquisition or
    # ownership.  Mere consideration of a vehicle is deliberately excluded.
    for event in ordered:
        if "vehicle" not in concepts_by_id[event.event_id]:
            continue
        if not _contains_any(event.text, _ACQUISITION_PHRASES):
            continue
        association_id = _association_id(
            "CONCEPT_INSTANCE", "TERM", "vehicle", "EVENT", event.event_id
        )
        derived[association_id] = Association(
            association_id=association_id,
            source_kind="TERM",
            source="vehicle",
            target_kind="EVENT",
            target=event.event_id,
            relationship="CONCEPT_INSTANCE",
            strength=1.0,
            provenance_event_ids=(event.event_id,),
        )

    return tuple(derived[key] for key in sorted(derived))
