"""Deterministic bounded associative recall for Prometheist Memory Kernel.

Canonical events remain authoritative evidence; associations are derived,
replaceable routing hints with explicit provenance. The algorithm performs
bounded spreading activation over a small typed graph and then ranks source
events using the stronger of deterministic cue score and association
activation.
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

ASSOCIATIVE_POLICY_VERSION = "deterministic-associations-v3"
NodeKind = Literal["TERM", "EVENT"]

# These tokens shape which state or interpretation the caller wants but are not
# themselves evidence-bearing subject matter. Removing them from the direct
# support denominator prevents questions such as "Where do I work now?" from
# looking artificially weak merely because the event does not contain "now".
_DIRECT_SUPPORT_MODIFIERS = frozenset(
    {
        "actually",
        "before",
        "current",
        "currently",
        "immediately",
        "now",
        "still",
        "usually",
    }
)

# Direct lexical evidence must cover more than half of the substantive query
# terms unless another independent cue supplies support. This rejects merely
# topical matches such as a generic vehicle record for "Who insures my
# vehicle?" while preserving explicitly associated and temporally anchored
# evidence. Keep this conservative and benchmarked; it is not a semantic model.
_MIN_DIRECT_SUPPORT_COVERAGE = 0.60


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
    required_cue_terms: tuple[str, ...] = ()

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


def _term_token(value: str) -> str:
    """Normalize one association TERM exactly as a query term is normalized."""
    tokens = tokenize(value)
    if len(tokens) != 1:
        raise ValueError("TERM association nodes must normalize to exactly one token")
    return tokens[0]


def _node(kind: NodeKind, value: str) -> str:
    if kind == "TERM":
        return f"term:{_term_token(value)}"
    if not value:
        raise ValueError("EVENT association nodes cannot be blank")
    return f"event:{value}"


def _cue_nodes(cue: CueState) -> tuple[str, ...]:
    ignored = {
        token
        for term in cue.ignored_terms
        for token in tokenize(term)
    }
    nodes = {
        f"term:{token}"
        for token in tokenize(cue.query_text or "")
        if token not in ignored
    }
    for entity in cue.entities:
        normalized = normalize_text(entity)
        if normalized:
            # Retain an exact normalized entity node for future phrase-level
            # associations while also exposing its query-normalized term nodes.
            nodes.add(f"term:{normalized}")
        nodes.update(
            f"term:{token}"
            for token in tokenize(entity)
            if token not in ignored
        )
    return tuple(sorted(nodes))


def _direct_support_coverage(event: MemoryEvent, cue: CueState) -> float:
    """Measure how much substantive query content appears in one event.

    This is intentionally separate from ``score_event``. The baseline score is
    an activation score and is allowed to be broad enough to seed association
    traversal. Evidence admission is stricter: a directly returned event should
    support the requested content rather than merely share one topical word.
    """
    ignored = {
        token
        for value in cue.ignored_terms
        for token in tokenize(value)
    }
    query_terms = {
        token
        for token in tokenize(cue.query_text or "")
        if token not in ignored and token not in _DIRECT_SUPPORT_MODIFIERS
    }
    if not query_terms:
        # Entity-only or non-text cues should continue to use the baseline
        # scoring policy rather than being rejected by an empty denominator.
        return 1.0
    event_terms = set(tokenize(event.text))
    return len(query_terms & event_terms) / len(query_terms)


def _direct_evidence_is_admissible(
    event: MemoryEvent,
    cue: CueState,
    *,
    has_association_support: bool,
) -> bool:
    """Return whether a candidate has enough support to be surfaced as evidence.

    Association-backed evidence is admitted because the explicit relationship
    route is itself support. A temporal query may admit sparse direct lexical
    evidence because time is an independent first-class cue. Otherwise a direct
    candidate must cover a majority of substantive query terms.
    """
    if has_association_support:
        return True

    coverage = _direct_support_coverage(event, cue)
    if coverage >= _MIN_DIRECT_SUPPORT_COVERAGE:
        return True

    if cue.reference_time is not None and coverage > 0.0:
        return True

    return False


def associative_recall(
    events: Iterable[MemoryEvent],
    cue: CueState,
    associations: Sequence[Association],
    *,
    max_hops: int = 2,
    decay: float = 0.85,
) -> AssociativeMemoryPacket:
    """Recall source evidence using cue scoring plus bounded spreading activation.

    Query/entity terms begin fully activated. Any event that already clears the
    deterministic minimum score also becomes a fully activated event node. This
    models a two-stage process: direct cues activate an initial memory set, then
    explicit associations can activate neighboring concepts/events.

    Direct activation and associative activation are tracked separately. A
    directly matched event may still receive a meaningful relationship-specific
    associative boost; direct activation must not suppress evidence that a valid
    association path reached that same event.

    Baseline activation is deliberately broader than final evidence admission.
    Weak topical matches may seed association traversal, but a directly returned
    event must have substantive query-content support unless an association or
    temporal cue independently supports it.

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

    # ``activation`` controls propagation and therefore contains both cue/direct
    # seeds and propagated activation. ``associative_activation`` contains only
    # activation earned by traversing an Association edge. Keeping these domains
    # separate prevents a direct 1.0 seed from masking a valid 0.85 relationship
    # boost to the same event.
    activation: dict[str, float] = {}
    associative_activation: dict[str, float] = {}
    cue_nodes = _cue_nodes(cue)
    cue_term_values = {node.removeprefix("term:") for node in cue_nodes}
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
            required_terms = {
                token
                for value in association.required_cue_terms
                for token in tokenize(value)
            }
            if required_terms and not required_terms.issubset(cue_term_values):
                continue
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

            # Compare against prior *associative* activation, not the combined
            # propagation seed. A direct event seed is intentionally 1.0, but it
            # must not erase the fact that an association independently reached
            # that event with a relationship-specific score.
            if propagated <= associative_activation.get(target_node, 0.0):
                continue
            associative_activation[target_node] = propagated
            if propagated > activation.get(target_node, 0.0):
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
        assoc_activation = associative_activation.get(event_node, 0.0)
        total = max(score.total, assoc_activation)
        if has_cues and total < cue.minimum_score:
            continue
        hops = tuple(hops_by_target.get(event_node, ()))
        if has_cues and not _direct_evidence_is_admissible(
            event,
            cue,
            has_association_support=bool(hops),
        ):
            continue
        ranked.append(
            (
                total,
                event,
                score.total,
                assoc_activation,
                hops,
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
