"""Deterministic, LLM-independent core of the Prometheist memory kernel.

The kernel treats persisted events as evidence.  It does not summarize or
rewrite them.  Recall is a pure function of the evidence set, the cue state,
and the retrieval policy version, which makes behavior reproducible and easy
to regression-test.

This is intentionally a v0.2 primitive.  The cue/score interfaces are designed
so later associative, episodic, semantic-vector, and graph routes can be added
without changing the evidence model or the LLM-facing memory packet shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

POLICY_VERSION = "deterministic-cues-v1"

_WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
        "did", "do", "does", "for", "from", "had", "has", "have", "he",
        "her", "hers", "him", "his", "i", "in", "is", "it", "its", "me",
        "my", "of", "on", "or", "our", "she", "so", "that", "the", "their",
        "them", "they", "this", "to", "us", "was", "we", "were", "what",
        "when", "where", "which", "who", "why", "with", "you", "your",
    }
)


def normalize_text(text: str) -> str:
    """Return stable case-folded text for deterministic matching."""
    return unicodedata.normalize("NFKC", text).casefold().strip()


def _light_stem(token: str) -> str:
    """Conservative deterministic morphology normalization.

    This is deliberately small: it handles common English inflections without
    pulling a full NLP runtime into the memory kernel.
    """
    if token.endswith("'s") and len(token) > 3:
        token = token[:-2]
    if token.endswith("ies") and len(token) > 5:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 5:
        base = token[:-3]
        # running -> run, but working -> work
        if len(base) >= 3 and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str, *, drop_stop_words: bool = True) -> tuple[str, ...]:
    """Tokenize without an NLP model or external dependency.

    Ordering and duplicates are preserved because query-term frequency can be
    useful to future policies.  Projection code can de-duplicate separately.
    """
    tokens = tuple(_light_stem(normalize_text(m.group(0))) for m in _WORD_RE.finditer(text))
    if not drop_stop_words:
        return tokens
    return tuple(t for t in tokens if len(t) > 1 and t not in _STOP_WORDS)


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    """Minimal canonical evidence shape consumed by the deterministic kernel."""

    event_id: str
    global_seq: int
    conversation_id: str
    conversation_seq: int
    event_type: str
    source: str
    created_at: datetime
    text: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CueState:
    """Present-state cues that may activate stored evidence.

    An explicit natural-language query is only one cue.  Entity, temporal,
    conversation, and source-type cues are first-class so the API can evolve
    toward context-triggered recall rather than remaining a query-only RAG API.
    """

    query_text: str | None = None
    entities: tuple[str, ...] = ()
    reference_time: datetime | None = None
    conversation_id: str | None = None
    source_types: tuple[str, ...] = ()
    ignored_terms: tuple[str, ...] = ()
    limit: int = 5
    minimum_score: float = 0.15

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("limit must be >= 1")
        if not 0.0 <= self.minimum_score <= 1.0:
            raise ValueError("minimum_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ScoreComponents:
    lexical: float = 0.0
    entity: float = 0.0
    temporal: float = 0.0
    conversation: float = 0.0
    total: float = 0.0


@dataclass(frozen=True, slots=True)
class RecallCandidate:
    event: MemoryEvent
    score: ScoreComponents
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecallTraceItem:
    event_id: str
    global_seq: int
    score: ScoreComponents
    reasons: tuple[str, ...]
    selected: bool


@dataclass(frozen=True, slots=True)
class RecallTrace:
    policy_version: str
    cue_tokens: tuple[str, ...]
    normalized_entities: tuple[str, ...]
    candidates_considered: int
    items: tuple[RecallTraceItem, ...]


@dataclass(frozen=True, slots=True)
class MemoryPacket:
    """Bounded evidence returned to a stateless consumer plus its audit trace."""

    items: tuple[MemoryEvent, ...]
    trace: RecallTrace


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _lexical_score(query_text: str | None, event_text: str, ignored_terms: Sequence[str] = ()) -> float:
    if not query_text:
        return 0.0
    ignored = {normalize_text(term) for term in ignored_terms}
    query_tokens = tuple(token for token in tokenize(query_text) if token not in ignored)
    if not query_tokens:
        return 0.0
    event_tokens = set(tokenize(event_text))
    if not event_tokens:
        return 0.0

    unique_query = set(query_tokens)
    coverage = len(unique_query & event_tokens) / len(unique_query)

    normalized_query = normalize_text(query_text)
    normalized_event = normalize_text(event_text)
    phrase_bonus = 0.15 if normalized_query and normalized_query in normalized_event else 0.0
    return _clamp01(coverage + phrase_bonus)


def _entity_score(entities: Sequence[str], event_text: str, payload: Mapping[str, Any]) -> float:
    if not entities:
        return 0.0
    haystack = normalize_text(event_text)
    payload_entities = {
        normalize_text(str(value))
        for value in payload.get("entities", [])
        if isinstance(value, (str, int, float))
    }
    hits = 0
    for entity in entities:
        normalized = normalize_text(entity)
        if normalized and (normalized in haystack or normalized in payload_entities):
            hits += 1
    return hits / len(entities)


def _temporal_score(reference_time: datetime | None, created_at: datetime) -> float:
    if reference_time is None:
        return 0.0
    ref = reference_time if reference_time.tzinfo else reference_time.replace(tzinfo=timezone.utc)
    event_time = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    delta_days = abs((ref - event_time).total_seconds()) / 86400.0
    # Gentle cue, not a forgetting curve.  Exact/semantic evidence should beat recency.
    return 1.0 / (1.0 + delta_days / 30.0)


def score_event(event: MemoryEvent, cue: CueState) -> ScoreComponents:
    """Score one event with explicit, inspectable deterministic components."""
    lexical = _lexical_score(cue.query_text, event.text, cue.ignored_terms)
    entity = _entity_score(cue.entities, event.text, event.payload)
    temporal = _temporal_score(cue.reference_time, event.created_at)
    conversation = 1.0 if cue.conversation_id and cue.conversation_id == event.conversation_id else 0.0

    # v0.2 weights deliberately favor evidence content.  Temporal/context cues
    # break ties and help activation but cannot overpower a strong lexical hit.
    total = _clamp01(
        0.78 * lexical
        + 0.14 * entity
        + 0.05 * temporal
        + 0.03 * conversation
    )
    return ScoreComponents(
        lexical=lexical,
        entity=entity,
        temporal=temporal,
        conversation=conversation,
        total=total,
    )


def _reasons(score: ScoreComponents) -> tuple[str, ...]:
    reasons: list[str] = []
    if score.lexical > 0:
        reasons.append("LEXICAL_CUE")
    if score.entity > 0:
        reasons.append("ENTITY_CUE")
    if score.temporal > 0:
        reasons.append("TEMPORAL_CUE")
    if score.conversation > 0:
        reasons.append("CONVERSATION_CUE")
    return tuple(reasons)


def recall(events: Iterable[MemoryEvent], cue: CueState) -> MemoryPacket:
    """Return a bounded, deterministic evidence packet for the given cue state.

    With no activation cues, recall degrades to deterministic newest-first
    history.  With cues, events below ``minimum_score`` are excluded so an
    unknown question can correctly return no evidence instead of inventing a
    nearest neighbor.
    """
    candidates: list[RecallCandidate] = []
    has_activation_cues = bool(cue.query_text or cue.entities or cue.reference_time or cue.conversation_id)
    allowed_types = set(cue.source_types)

    for event in events:
        if allowed_types and event.event_type not in allowed_types:
            continue
        score = score_event(event, cue)
        if has_activation_cues and score.total < cue.minimum_score:
            continue
        candidates.append(RecallCandidate(event=event, score=score, reasons=_reasons(score)))

    if has_activation_cues:
        candidates.sort(key=lambda c: (-c.score.total, -c.event.global_seq, c.event.event_id))
    else:
        candidates.sort(key=lambda c: (-c.event.global_seq, c.event.event_id))

    selected = candidates[: cue.limit]
    selected_ids = {candidate.event.event_id for candidate in selected}
    trace_items = tuple(
        RecallTraceItem(
            event_id=candidate.event.event_id,
            global_seq=candidate.event.global_seq,
            score=candidate.score,
            reasons=candidate.reasons,
            selected=candidate.event.event_id in selected_ids,
        )
        for candidate in candidates
    )
    trace = RecallTrace(
        policy_version=POLICY_VERSION,
        cue_tokens=tuple(token for token in tokenize(cue.query_text or "") if token not in {normalize_text(term) for term in cue.ignored_terms}),
        normalized_entities=tuple(normalize_text(e) for e in cue.entities),
        candidates_considered=len(candidates),
        items=trace_items,
    )
    return MemoryPacket(items=tuple(candidate.event for candidate in selected), trace=trace)


def reciprocal_rank(packet: MemoryPacket, relevant_event_ids: set[str]) -> float:
    """Convenience metric used by the synthetic-life benchmark."""
    for index, event in enumerate(packet.items, start=1):
        if event.event_id in relevant_event_ids:
            return 1.0 / index
    return 0.0
