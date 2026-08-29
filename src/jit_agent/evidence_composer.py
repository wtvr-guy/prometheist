"""Deterministic evidence composition for bounded stateless cognition.

The retrieval kernel answers "what evidence is reachable/relevant?". This module
answers the separate question "which bounded subset should cross the cognition
boundary?".

``compose_coverage_aware`` is the frozen v1 experiment from MEM-ADAPT-003/004.
``compose_relevance_coverage`` is the v2 experiment. V2 does not average relevance
and diversity. Instead it preserves a relevance core, identifies only demonstrably
redundant core slots, and allows coverage/support augmentation to compete for those
vacated slots. This keeps relevance and coverage as separate responsibilities.

This module is experimental and is not wired into the production interaction path.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Iterable
import uuid

from jit_agent.models import MemoryEvidence

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_INDEX_SUFFIX_RE = re.compile(r"(?<=[A-Za-z])-\d+\b")


@dataclass(frozen=True, slots=True)
class CompositionDecision:
    source_event_id: uuid.UUID
    original_rank: int
    retained: bool
    novel_provenance: int
    novel_retrieval_reasons: int
    novel_tokens: int
    token_novelty: Fraction
    novel_source: bool
    novel_event_type: bool
    novel_conversation: bool


@dataclass(frozen=True, slots=True)
class CompositionResult:
    items: tuple[MemoryEvidence, ...]
    decisions: tuple[CompositionDecision, ...]


@dataclass(frozen=True, slots=True)
class RelevanceCoverageDecision:
    source_event_id: uuid.UUID
    original_rank: int
    retained: bool
    selection_role: str
    information_novel: bool
    support_novel: bool
    novel_provenance: int
    novel_retrieval_reasons: int
    novel_tokens: int
    token_novelty: Fraction


@dataclass(frozen=True, slots=True)
class RelevanceCoverageResult:
    items: tuple[MemoryEvidence, ...]
    decisions: tuple[RelevanceCoverageDecision, ...]


def _tokens(text: str) -> frozenset[str]:
    """Return the frozen v1 lexical signature, ignoring numeric-only suffixes."""

    return frozenset(
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if not token.isdigit()
    )


def _relevance_coverage_tokens(text: str) -> frozenset[str]:
    """Return a v2 information signature.

    Standalone numbers are retained because they may be the fact payload. Numeric
    suffixes attached with a hyphen are stripped as mechanical labels so benchmark
    or event numbering cannot create artificial novelty by itself.
    """

    normalized = _INDEX_SUFFIX_RE.sub("", text)
    return frozenset(token.casefold() for token in _TOKEN_RE.findall(normalized))


def _support_identity(item: MemoryEvidence) -> tuple[object, ...]:
    """Return an application-observable identity for independent support.

    Canonical provenance is preferred when available. Otherwise source and
    conversation provide the conservative fallback. Event ids alone are not used:
    multiple rows from one source/conversation do not automatically become
    independent corroboration merely because they have distinct ids.
    """

    if item.provenance_event_ids:
        return ("provenance", *sorted(item.provenance_event_ids, key=str))
    return ("origin", item.source, item.conversation_id)


def _deduplicated_pool(
    candidates: Iterable[MemoryEvidence],
    retained: Iterable[MemoryEvidence],
) -> tuple[list[MemoryEvidence], set[uuid.UUID]]:
    candidate_items = list(candidates)
    retained_items = list(retained)
    retained_ids = {item.source_event_id for item in retained_items}
    ordered = [*candidate_items, *retained_items]
    unique: list[MemoryEvidence] = []
    seen: set[uuid.UUID] = set()
    for item in ordered:
        if item.source_event_id in seen:
            continue
        seen.add(item.source_event_id)
        unique.append(item)
    return unique, retained_ids


def compose_coverage_aware(
    candidates: Iterable[MemoryEvidence],
    *,
    limit: int,
    retained: Iterable[MemoryEvidence] = (),
) -> CompositionResult:
    """Select a bounded evidence set by deterministic marginal coverage.

    This is the frozen v1 composer used by MEM-ADAPT-003 and MEM-ADAPT-004.
    The first slot preserves the retrieval system's strongest current candidate.
    Remaining slots greedily prefer evidence that adds provenance, retrieval-route,
    lexical, source, type, or conversation coverage. Previously surfaced evidence
    wins only after marginal coverage ties, so retention is sticky but not absolute.
    Raw retrieval score and original rank remain final tie-breakers.
    """

    pool, retained_ids = _deduplicated_pool(candidates, retained)
    if not pool or not limit:
        return CompositionResult(items=(), decisions=())

    candidate_rank = {item.source_event_id: index for index, item in enumerate(pool)}
    selected: list[MemoryEvidence] = []
    decisions: list[CompositionDecision] = []
    covered_tokens: set[str] = set()
    covered_provenance: set[uuid.UUID] = set()
    covered_reasons: set[str] = set()
    covered_sources: set[str] = set()
    covered_types: set[object] = set()
    covered_conversations: set[uuid.UUID] = set()

    def describe(item: MemoryEvidence) -> CompositionDecision:
        tokens = _tokens(item.content)
        new_tokens = tokens - covered_tokens
        provenance = set(item.provenance_event_ids)
        reasons = set(item.retrieval_reasons)
        denominator = len(tokens)
        token_novelty = Fraction(len(new_tokens), denominator) if denominator else Fraction()
        return CompositionDecision(
            source_event_id=item.source_event_id,
            original_rank=candidate_rank[item.source_event_id],
            retained=item.source_event_id in retained_ids,
            novel_provenance=len(provenance - covered_provenance),
            novel_retrieval_reasons=len(reasons - covered_reasons),
            novel_tokens=len(new_tokens),
            token_novelty=token_novelty,
            novel_source=item.source not in covered_sources,
            novel_event_type=item.event_type not in covered_types,
            novel_conversation=item.conversation_id not in covered_conversations,
        )

    def utility(item: MemoryEvidence) -> tuple[object, ...]:
        decision = describe(item)
        score = item.score if item.score is not None else float("-inf")
        return (
            decision.novel_provenance,
            decision.novel_retrieval_reasons,
            decision.token_novelty,
            decision.novel_tokens,
            decision.novel_source,
            decision.novel_event_type,
            decision.novel_conversation,
            decision.retained,
            score,
            -decision.original_rank,
        )

    def accept(item: MemoryEvidence) -> None:
        decision = describe(item)
        decisions.append(decision)
        selected.append(item)
        covered_tokens.update(_tokens(item.content))
        covered_provenance.update(item.provenance_event_ids)
        covered_reasons.update(item.retrieval_reasons)
        covered_sources.add(item.source)
        covered_types.add(item.event_type)
        covered_conversations.add(item.conversation_id)

    accept(pool[0])
    remaining = pool[1:]
    while remaining and len(selected) < limit:
        best = max(remaining, key=utility)
        remaining.remove(best)
        accept(best)

    return CompositionResult(items=tuple(selected), decisions=tuple(decisions))


def compose_relevance_coverage(
    candidates: Iterable[MemoryEvidence],
    *,
    limit: int,
    retained: Iterable[MemoryEvidence] = (),
) -> RelevanceCoverageResult:
    """Compose evidence by preserving relevance and spending only redundant slots.

    V2 starts from the current retrieval top-k. A top-k item is replaceable only
    when an earlier core item already represents both the same information signature
    and the same support identity. Repeated equivalent evidence from independent
    provenance/source remains protected as corroboration. Coverage augmentation then
    fills only those vacated slots, ordered first by retrieval score and then by
    marginal information/support contribution. Retained evidence participates only
    in augmentation and therefore cannot evict a nonredundant current core item.

    No model-generated score, learned coefficient, similarity threshold, or fixed
    relevance/diversity weight is used.
    """

    candidate_items, _ = _deduplicated_pool(candidates, ())
    retained_items = list(retained)
    retained_ids = {item.source_event_id for item in retained_items}
    if not candidate_items or not limit:
        return RelevanceCoverageResult(items=(), decisions=())

    candidate_ids = {item.source_event_id for item in candidate_items}
    retained_only = [item for item in retained_items if item.source_event_id not in candidate_ids]
    ordered = [*candidate_items, *retained_only]
    rank = {item.source_event_id: index for index, item in enumerate(ordered)}

    selected: list[MemoryEvidence] = []
    decisions: list[RelevanceCoverageDecision] = []
    covered_tokens: set[str] = set()
    covered_provenance: set[uuid.UUID] = set()
    covered_reasons: set[str] = set()
    represented_signatures: set[frozenset[str]] = set()
    represented_support: set[tuple[frozenset[str], tuple[object, ...]]] = set()

    def signature(item: MemoryEvidence) -> frozenset[str]:
        return _relevance_coverage_tokens(item.content)

    def contribution_key(item: MemoryEvidence) -> tuple[frozenset[str], tuple[object, ...]]:
        return (signature(item), _support_identity(item))

    def describe(item: MemoryEvidence, role: str) -> RelevanceCoverageDecision:
        item_signature = signature(item)
        item_support = contribution_key(item)
        new_tokens = item_signature - covered_tokens
        provenance = set(item.provenance_event_ids)
        reasons = set(item.retrieval_reasons)
        denominator = len(item_signature)
        token_novelty = Fraction(len(new_tokens), denominator) if denominator else Fraction()
        return RelevanceCoverageDecision(
            source_event_id=item.source_event_id,
            original_rank=rank[item.source_event_id],
            retained=item.source_event_id in retained_ids,
            selection_role=role,
            information_novel=item_signature not in represented_signatures,
            support_novel=item_support not in represented_support,
            novel_provenance=len(provenance - covered_provenance),
            novel_retrieval_reasons=len(reasons - covered_reasons),
            novel_tokens=len(new_tokens),
            token_novelty=token_novelty,
        )

    def accept(item: MemoryEvidence, role: str) -> None:
        decision = describe(item, role)
        decisions.append(decision)
        selected.append(item)
        item_signature = signature(item)
        represented_signatures.add(item_signature)
        represented_support.add(contribution_key(item))
        covered_tokens.update(item_signature)
        covered_provenance.update(item.provenance_event_ids)
        covered_reasons.update(item.retrieval_reasons)

    core = candidate_items[:limit]
    redundant_core: list[MemoryEvidence] = []
    seen_core_contributions: set[tuple[frozenset[str], tuple[object, ...]]] = set()
    for item in core:
        key = contribution_key(item)
        if key in seen_core_contributions:
            redundant_core.append(item)
            continue
        seen_core_contributions.add(key)
        accept(item, "core")

    selected_ids = {item.source_event_id for item in selected}
    augmentation_pool = [
        item
        for item in [*candidate_items[len(core) :], *retained_only]
        if item.source_event_id not in selected_ids
    ]

    def is_informative(item: MemoryEvidence) -> bool:
        return contribution_key(item) not in represented_support

    def augmentation_utility(item: MemoryEvidence) -> tuple[object, ...]:
        decision = describe(item, "augmentation")
        score = item.score if item.score is not None else float("-inf")
        return (
            score,
            decision.information_novel,
            decision.support_novel,
            decision.novel_provenance,
            decision.novel_retrieval_reasons,
            decision.token_novelty,
            decision.novel_tokens,
            decision.retained,
            -decision.original_rank,
        )

    while augmentation_pool and len(selected) < limit:
        informative = [item for item in augmentation_pool if is_informative(item)]
        if not informative:
            break
        best = max(informative, key=augmentation_utility)
        augmentation_pool.remove(best)
        accept(best, "augmentation")

    fallback = [
        *redundant_core,
        *[
            item
            for item in candidate_items[len(core) :]
            if item.source_event_id not in {selected_item.source_event_id for selected_item in selected}
        ],
        *[
            item
            for item in retained_only
            if item.source_event_id not in {selected_item.source_event_id for selected_item in selected}
        ],
    ]
    for item in fallback:
        if len(selected) >= limit:
            break
        if item.source_event_id in {selected_item.source_event_id for selected_item in selected}:
            continue
        accept(item, "fallback")

    return RelevanceCoverageResult(items=tuple(selected), decisions=tuple(decisions))
