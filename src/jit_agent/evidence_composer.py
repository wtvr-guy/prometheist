"""Deterministic evidence composition for bounded stateless cognition.

The retrieval kernel answers "what evidence is reachable/relevant?". This module
answers the separate question "which bounded subset should cross the cognition
boundary?". It is intentionally parameter-light: no model scoring and no learned
weights. Composition prefers marginal evidence coverage, then previously retained
useful evidence, then the retrieval order already supplied by the kernel.

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


def _tokens(text: str) -> frozenset[str]:
    """Return a deterministic lexical signature, ignoring numeric-only suffixes."""

    return frozenset(
        token.casefold()
        for token in _TOKEN_RE.findall(text)
        if not token.isdigit()
    )


def _deduplicated_pool(
    candidates: Iterable[MemoryEvidence],
    retained: Iterable[MemoryEvidence],
) -> tuple[list[MemoryEvidence], set[uuid.UUID]]:
    retained_items = list(retained)
    retained_ids = {item.source_event_id for item in retained_items}
    ordered = [*retained_items, *candidates]
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

    The first slot preserves the retrieval system's strongest available item.
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

    # Preserve the retrieval system's strongest item before diversification.
    accept(pool[0])
    remaining = pool[1:]
    while remaining and len(selected) < limit:
        best = max(remaining, key=utility)
        remaining.remove(best)
        accept(best)

    return CompositionResult(items=tuple(selected), decisions=tuple(decisions))
