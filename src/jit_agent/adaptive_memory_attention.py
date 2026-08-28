"""Deterministic adaptive control for deliberate JIT-memory attention.

This module is intentionally parallel to the frozen v0.7 recall profiles.  It does
not make the photography metaphor part of runtime semantics.  Instead it exposes
literal retrieval-control dimensions discovered while examining those profiles:

* semantic uncertainty: the unresolved cognitive problem expressed by a model as
  a closed enum, never as retrieval parameters or generated search text;
* focus anchors: canonical event IDs selected from an existing MemoryPacket;
* retrieval telemetry: application-owned measurements of the current packet;
* retrieval policy: deterministic kernel mechanics derived from the above.

Models may point attention and classify the unresolved uncertainty.  Prometheist
owns the optics: candidate breadth, associative effort, anchor use, and the
anti-lock-in decision to reorient.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import log
from typing import Iterable


class MemoryUncertainty(str, Enum):
    """Closed semantic reasons why the currently visible memory is insufficient."""

    MISSING_CONTEXT = "MISSING_CONTEXT"
    AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"
    MISSING_RELATIONSHIP = "MISSING_RELATIONSHIP"
    POSSIBLE_CONTRADICTION = "POSSIBLE_CONTRADICTION"
    SPECIFIC_DETAIL_MISSING = "SPECIFIC_DETAIL_MISSING"


class ScopeProfile(str, Enum):
    """How broadly direct candidate generation should frame persisted memory."""

    CONTEXTUAL = "CONTEXTUAL"
    BALANCED = "BALANCED"
    NARROW = "NARROW"


class AssociationEffort(str, Enum):
    """How aggressively bounded association traversal should be explored."""

    SHALLOW = "SHALLOW"
    MODERATE = "MODERATE"
    DEEP = "DEEP"


class FocusMode(str, Enum):
    """Whether the next pass should exploit anchors or deliberately reorient."""

    UNANCHORED = "UNANCHORED"
    SINGLE_ANCHOR = "SINGLE_ANCHOR"
    MULTI_ANCHOR = "MULTI_ANCHOR"
    REORIENT = "REORIENT"


@dataclass(frozen=True, slots=True)
class RetrievalTelemetry:
    """Bounded measurements from the current retrieval state.

    ``candidate_scores`` must be non-negative and should be supplied in the same
    deterministic order as the visible MemoryPacket.  Scores are used only as
    relative attention telemetry; they are not promoted to epistemic truth.

    ``anchored_rounds`` counts consecutive deliberate passes that exploited one
    or more anchors.  ``support_gain`` is the application-owned change in the
    chosen support metric since the previous deliberate pass.  A non-positive
    gain after repeated anchored passes triggers bounded reorientation.
    """

    candidate_scores: tuple[float, ...] = ()
    anchored_rounds: int = 0
    support_gain: float | None = None

    def __post_init__(self) -> None:
        if self.anchored_rounds < 0:
            raise ValueError("anchored_rounds must be non-negative")
        if any(score < 0 for score in self.candidate_scores):
            raise ValueError("candidate scores must be non-negative")


@dataclass(frozen=True, slots=True)
class AdaptiveRecallPolicy:
    """Concrete application-owned mechanics for one bounded memory pass."""

    scope: ScopeProfile
    association_effort: AssociationEffort
    focus_mode: FocusMode
    candidate_limit: int
    association_limit: int
    max_hops: int
    decay: float
    use_focus_anchors: bool
    minimum_score: float = 0.15


# These are experimental constraints, not constitutional constants.  They are
# deliberately expressed independently so that broad+deep and narrow+shallow
# combinations are representable; the frozen v0.7 profiles couple those axes.
_SCOPE_CANDIDATE_LIMITS = {
    ScopeProfile.CONTEXTUAL: 600,
    ScopeProfile.BALANCED: 350,
    ScopeProfile.NARROW: 175,
}

_ASSOCIATION_SETTINGS = {
    AssociationEffort.SHALLOW: (300, 2, 0.85),
    AssociationEffort.MODERATE: (750, 3, 0.88),
    AssociationEffort.DEEP: (1200, 5, 0.92),
}

_REORIENT_AFTER_ANCHORED_ROUNDS = 2
_DOMINANT_SHARE = 0.60
_LOW_NORMALIZED_ENTROPY = 0.55


def normalized_score_entropy(scores: Iterable[float]) -> float:
    """Return normalized Shannon entropy in [0, 1] for non-negative scores.

    Empty and single-positive-score distributions have zero ambiguity.  A fully
    even positive distribution approaches one.  This measurement is deterministic
    and intentionally says nothing about factual correctness.
    """

    values = tuple(float(score) for score in scores)
    if any(score < 0 for score in values):
        raise ValueError("candidate scores must be non-negative")
    positive = tuple(score for score in values if score > 0)
    if len(positive) <= 1:
        return 0.0
    total = sum(positive)
    probabilities = tuple(score / total for score in positive)
    entropy = -sum(probability * log(probability) for probability in probabilities)
    return entropy / log(len(probabilities))


def dominant_score_share(scores: Iterable[float]) -> float:
    """Return the fraction of positive score mass held by the top candidate."""

    values = tuple(float(score) for score in scores)
    if any(score < 0 for score in values):
        raise ValueError("candidate scores must be non-negative")
    total = sum(values)
    if total <= 0:
        return 0.0
    return max(values, default=0.0) / total


def _scope_for(
    uncertainty: MemoryUncertainty,
    anchor_count: int,
    telemetry: RetrievalTelemetry,
) -> ScopeProfile:
    # Explicit contextual uncertainty should remain wide even when an anchor is
    # available.  This is how the adaptive controller can express broad+deep.
    if uncertainty in {
        MemoryUncertainty.MISSING_CONTEXT,
        MemoryUncertainty.POSSIBLE_CONTRADICTION,
    }:
        return ScopeProfile.CONTEXTUAL

    # Exact-detail work can remain local rather than inheriting the old rule that
    # every deeper pass must also traverse a large direct-candidate population.
    if uncertainty is MemoryUncertainty.SPECIFIC_DETAIL_MISSING and anchor_count == 1:
        return ScopeProfile.NARROW

    entropy = normalized_score_entropy(telemetry.candidate_scores)
    dominance = dominant_score_share(telemetry.candidate_scores)
    if anchor_count == 1 and dominance >= _DOMINANT_SHARE and entropy <= _LOW_NORMALIZED_ENTROPY:
        return ScopeProfile.NARROW
    if anchor_count >= 2 or uncertainty is MemoryUncertainty.AMBIGUOUS_CANDIDATES:
        return ScopeProfile.BALANCED
    return ScopeProfile.CONTEXTUAL


def _association_effort_for(
    uncertainty: MemoryUncertainty,
    anchor_count: int,
) -> AssociationEffort:
    if uncertainty in {
        MemoryUncertainty.MISSING_RELATIONSHIP,
        MemoryUncertainty.POSSIBLE_CONTRADICTION,
    }:
        return AssociationEffort.DEEP
    if uncertainty is MemoryUncertainty.SPECIFIC_DETAIL_MISSING:
        return AssociationEffort.SHALLOW
    if anchor_count >= 2:
        return AssociationEffort.MODERATE
    if uncertainty is MemoryUncertainty.MISSING_CONTEXT:
        return AssociationEffort.MODERATE
    return AssociationEffort.SHALLOW


def _should_reorient(telemetry: RetrievalTelemetry, *, anchor_count: int) -> bool:
    if anchor_count == 0:
        return False
    return (
        telemetry.anchored_rounds >= _REORIENT_AFTER_ANCHORED_ROUNDS
        and telemetry.support_gain is not None
        and telemetry.support_gain <= 0
    )


def derive_adaptive_recall_policy(
    *,
    uncertainty: MemoryUncertainty,
    anchor_count: int,
    telemetry: RetrievalTelemetry,
) -> AdaptiveRecallPolicy:
    """Derive deterministic retrieval mechanics from bounded semantic direction.

    The caller supplies only a closed uncertainty class, the number of canonical
    focus anchors already selected, and deterministic retrieval telemetry.  No
    model-authored numeric retrieval settings are accepted.
    """

    if anchor_count < 0:
        raise ValueError("anchor_count must be non-negative")

    if _should_reorient(telemetry, anchor_count=anchor_count):
        scope = ScopeProfile.CONTEXTUAL
        effort = AssociationEffort.SHALLOW
        focus_mode = FocusMode.REORIENT
        use_focus_anchors = False
    else:
        scope = _scope_for(uncertainty, anchor_count, telemetry)
        effort = _association_effort_for(uncertainty, anchor_count)
        if anchor_count == 0:
            focus_mode = FocusMode.UNANCHORED
            use_focus_anchors = False
        elif anchor_count == 1:
            focus_mode = FocusMode.SINGLE_ANCHOR
            use_focus_anchors = True
        else:
            focus_mode = FocusMode.MULTI_ANCHOR
            use_focus_anchors = True

    association_limit, max_hops, decay = _ASSOCIATION_SETTINGS[effort]
    return AdaptiveRecallPolicy(
        scope=scope,
        association_effort=effort,
        focus_mode=focus_mode,
        candidate_limit=_SCOPE_CANDIDATE_LIMITS[scope],
        association_limit=association_limit,
        max_hops=max_hops,
        decay=decay,
        use_focus_anchors=use_focus_anchors,
    )
