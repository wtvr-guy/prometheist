"""Deterministic bounded associative recall for Memory Kernel v0.3.

This module is deliberately additive to the v0.2 kernel. Canonical events remain
authoritative evidence; associations are derived, replaceable routing hints with
explicit provenance. The algorithm performs bounded spreading activation over a
small typed graph and then ranks source events using the stronger of the v0.2
cue score and association activation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from jit_agent.memory_kernel import (
    CueState,
    MemoryEvent,
    normalize_text,
    score_event,
    tokenize,
)

ASSOCIATIVE_POLICY_VERSION = "deterministic-associations-v1"
NodeKind = Literal["TERM", "EVENT"]


@dataclass(frozen=True, slots=True)
class Association:
    association_id: str
    source_kind: NodeKind
    source: str
    target_kind: NodeKind
    target: str
    relationship: str
    strength: float
    provenance_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 < self.strength <= 1.0:
            raise ValueError("association strength must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class AssociationHop:
    association_id: str
    source_node: str
    target_node: str
    relationship: str
    hop: int
    activation: float
    provenance_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssociativeTraceItem:
    event_id: str
    global_seq: int
    baseline_score: float
    associative_activation: float
    total_score: float
    selected: bool
    association_hops: tuple[AssociationHop, ...] = ()


@dataclass(frozen=True, slots=True)
class AssociativeTrace:
    policy_version: str
    max_hops: int
    decay: float
    cue_nodes: tuple[str, ...]
    items: tuple[AssociativeTraceItem, ...]


@dataclass(frozen=True, slots=True)
class AssociativeMemoryPacket:
    items: tuple[MemoryEvent, ...]
    trace: AssociativeTrace


def _node(kind: NodeKind, value: str) -> str:
    if kind == "TERM":
        normalized = normalize_text(value)
        if not normalized:
            raise ValueError("TERM association nodes cannot be blank")
        return f"term:{normalized}"
    if not value:
        raise ValueError("EVENT association nodes cannot be blank")
    return f"event:{value}"


def _cue_nodes(cue: CueState) -> tuple[str, ...]:
    ignored = {
        normalized
        for term in cue.ignored_terms
        if (normalized := normalize_text(term))
    }
    nodes = {
        f"term:{token}"
        for token in tokenize(cue.query_text or "")
        if token not in ignored
    }
    nodes.update(
        f"term:{normalized}"
        for entity in cue.entities
        if (normalized := normalize_text(entity))
    )
    return tuple(sorted(nodes))


def associative_recall(
    events: Iterable[MemoryEvent],
    cue: CueState,
    associations: Sequence[Association],
    *,
    max_hops: int = 2,
    decay: float = 0.85,
) -> AssociativeMemoryPacket:
    """Recall source evidence using v0.2 scoring plus bounded spreading activation.

    Query/entity terms begin fully activated. Any event that already clears the
    v0.2 minimum score also becomes a fully activated event node. This models a
    two-stage process: direct cues activate an initial memory set, then explicit
    associations can activate neighboring concepts/events.

    Associations never replace evidence. The returned items are canonical
    MemoryEvent objects, and trace hops retain association provenance.
    """
    if max_hops < 1:
        raise ValueError("max_hops must be >= 1")
    if not 0.0 < decay <= 1.0:
        raise ValueError("decay must be in (0, 1]")

    event_list = tuple(events)
    allowed_types = set(cue.source_types)
    baseline = {
        event.event_id: score_event(event, cue)
        for event in event_list
        if not allowed_types or event.event_type in allowed_types
    }

    activation: dict[str, float] = {}
    cue_nodes = _cue_nodes(cue)
    for node in cue_nodes:
        activation[node] = 1.0

    for event in event_list:
        score = baseline.get(event.event_id)
        if score is not None and score.total >= cue.minimum_score:
            activation[f"event:{event.event_id}"] = 1.0

    hops_by_target: dict[str, list[AssociationHop]] = {}
    ordered_associations = tuple(
        sorted(associations, key=lambda item: item.association_id)
    )

    for hop_number in range(1, max_hops + 1):
        prior = dict(activation)
        changed = False
        for association in ordered_associations:
            source_node = _node(association.source_kind, association.source)
            source_activation = prior.get(source_node, 0.0)
            if source_activation <= 0.0:
                continue
            target_node = _node(association.target_kind, association.target)
            propagated = (
                source_activation
                * association.strength
                * (decay ** hop_number)
            )
            if propagated <= activation.get(target_node, 0.0):
                continue
            activation[target_node] = propagated
            hops_by_target.setdefault(target_node, []).append(
                AssociationHop(
                    association_id=association.association_id,
                    source_node=source_node,
                    target_node=target_node,
                    relationship=association.relationship,
                    hop=hop_number,
                    activation=propagated,
                    provenance_event_ids=association.provenance_event_ids,
                )
            )
            changed = True
        if not changed:
            break

    ranked: list[
        tuple[float, MemoryEvent, float, float, tuple[AssociationHop, ...]]
    ] = []
    has_cues = bool(
        cue.query_text
        or cue.entities
        or cue.reference_time
        or cue.conversation_id
    )
    for event in event_list:
        score = baseline.get(event.event_id)
        if score is None:
            continue
        event_node = f"event:{event.event_id}"
        assoc_activation = activation.get(event_node, 0.0)
        # Direct activation only seeds spreading; it must not manufacture a
        # perfect association score for the event that was directly retrieved.
        if not hops_by_target.get(event_node):
            assoc_activation = 0.0
        total = max(score.total, assoc_activation)
        if has_cues and total < cue.minimum_score:
            continue
        ranked.append(
            (
                total,
                event,
                score.total,
                assoc_activation,
                tuple(hops_by_target.get(event_node, ())),
            )
        )

    if has_cues:
        ranked.sort(
            key=lambda row: (-row[0], -row[1].global_seq, row[1].event_id)
        )
    else:
        ranked.sort(key=lambda row: (-row[1].global_seq, row[1].event_id))

    selected_rows = ranked[: cue.limit]
    selected_ids = {row[1].event_id for row in selected_rows}
    trace_items = tuple(
        AssociativeTraceItem(
            event_id=event.event_id,
            global_seq=event.global_seq,
            baseline_score=baseline_score,
            associative_activation=assoc_activation,
            total_score=total,
            selected=event.event_id in selected_ids,
            association_hops=hops,
        )
        for total, event, baseline_score, assoc_activation, hops in ranked
    )
    return AssociativeMemoryPacket(
        items=tuple(row[1] for row in selected_rows),
        trace=AssociativeTrace(
            policy_version=ASSOCIATIVE_POLICY_VERSION,
            max_hops=max_hops,
            decay=decay,
            cue_nodes=cue_nodes,
            items=trace_items,
        ),
    )
