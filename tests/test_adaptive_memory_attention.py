import pytest

from jit_agent.adaptive_memory_attention import (
    AssociationEffort,
    FocusMode,
    MemoryUncertainty,
    RetrievalTelemetry,
    ScopeProfile,
    derive_adaptive_recall_policy,
    dominant_score_share,
    normalized_score_entropy,
)


def test_score_geometry_is_deterministic_and_bounded():
    assert dominant_score_share([8.0, 1.0, 1.0]) == pytest.approx(0.8)
    assert normalized_score_entropy([1.0, 1.0, 1.0, 1.0]) == pytest.approx(1.0)
    assert normalized_score_entropy([9.0, 0.0, 0.0]) == pytest.approx(0.0)


def test_specific_detail_can_be_narrow_and_shallow():
    policy = derive_adaptive_recall_policy(
        uncertainty=MemoryUncertainty.SPECIFIC_DETAIL_MISSING,
        anchor_count=1,
        telemetry=RetrievalTelemetry(candidate_scores=(0.9, 0.1)),
    )

    assert policy.scope is ScopeProfile.NARROW
    assert policy.association_effort is AssociationEffort.SHALLOW
    assert policy.focus_mode is FocusMode.SINGLE_ANCHOR
    assert policy.candidate_limit == 175
    assert policy.max_hops == 2
    assert policy.use_focus_anchors is True


def test_contextual_contradiction_can_be_broad_and_deep():
    policy = derive_adaptive_recall_policy(
        uncertainty=MemoryUncertainty.POSSIBLE_CONTRADICTION,
        anchor_count=2,
        telemetry=RetrievalTelemetry(candidate_scores=(0.51, 0.49)),
    )

    assert policy.scope is ScopeProfile.CONTEXTUAL
    assert policy.association_effort is AssociationEffort.DEEP
    assert policy.focus_mode is FocusMode.MULTI_ANCHOR
    assert policy.candidate_limit == 600
    assert policy.association_limit == 1200
    assert policy.max_hops == 5


def test_multiple_anchors_are_a_focus_mode_not_a_separate_capability():
    policy = derive_adaptive_recall_policy(
        uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
        anchor_count=3,
        telemetry=RetrievalTelemetry(candidate_scores=(0.36, 0.34, 0.30)),
    )

    assert policy.focus_mode is FocusMode.MULTI_ANCHOR
    assert policy.association_effort is AssociationEffort.DEEP
    assert policy.use_focus_anchors is True


def test_diffuse_ambiguous_candidates_preserve_breadth():
    policy = derive_adaptive_recall_policy(
        uncertainty=MemoryUncertainty.AMBIGUOUS_CANDIDATES,
        anchor_count=1,
        telemetry=RetrievalTelemetry(candidate_scores=(0.26, 0.25, 0.25, 0.24)),
    )

    assert policy.scope is ScopeProfile.BALANCED
    assert policy.focus_mode is FocusMode.SINGLE_ANCHOR


def test_repeated_anchor_exploitation_without_gain_forces_reorientation():
    policy = derive_adaptive_recall_policy(
        uncertainty=MemoryUncertainty.SPECIFIC_DETAIL_MISSING,
        anchor_count=1,
        telemetry=RetrievalTelemetry(
            candidate_scores=(0.95, 0.03, 0.02),
            anchored_rounds=2,
            support_gain=0.0,
        ),
    )

    assert policy.focus_mode is FocusMode.REORIENT
    assert policy.use_focus_anchors is False
    assert policy.scope is ScopeProfile.CONTEXTUAL
    assert policy.association_effort is AssociationEffort.SHALLOW


def test_positive_support_gain_does_not_break_focus_lock():
    policy = derive_adaptive_recall_policy(
        uncertainty=MemoryUncertainty.SPECIFIC_DETAIL_MISSING,
        anchor_count=1,
        telemetry=RetrievalTelemetry(
            candidate_scores=(0.95, 0.03, 0.02),
            anchored_rounds=3,
            support_gain=0.05,
        ),
    )

    assert policy.focus_mode is FocusMode.SINGLE_ANCHOR
    assert policy.use_focus_anchors is True


def test_invalid_telemetry_fails_closed():
    with pytest.raises(ValueError):
        RetrievalTelemetry(candidate_scores=(0.5, -0.1))

    with pytest.raises(ValueError):
        derive_adaptive_recall_policy(
            uncertainty=MemoryUncertainty.MISSING_CONTEXT,
            anchor_count=-1,
            telemetry=RetrievalTelemetry(),
        )
