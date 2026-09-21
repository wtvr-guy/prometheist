from __future__ import annotations

import json

from benchmarks import person_fidelity_exp1_lexical_candidates as exp1
from benchmarks import run_person_fidelity_mechanism_experiments as mechanism


def test_mechanism_fixture_is_frozen_and_independent_of_person_holdout_content():
    fixture, fixture_hash = mechanism.load_fixture()

    assert fixture.status == "FROZEN_BEFORE_NATIVE_CANDIDATE_SELECTION"
    assert len(fixture.composer_cases) == 10
    assert len(fixture.source_policy_cases) == 11
    assert len(fixture_hash) == 64

    serialized = mechanism.FIXTURE_PATH.read_text(encoding="utf-8").casefold()
    assert "mara" not in serialized
    assert "wren" not in serialized
    assert len({case["case_id"] for case in fixture.composer_cases}) == 10
    assert len({case["case_id"] for case in fixture.source_policy_cases}) == 11


def test_composer_candidate_distinguishes_generic_answerability_from_person_support():
    prompt = " ".join(mechanism.COMPOSER_CANDIDATE_PROMPT.split()).casefold()

    assert "as this particular person" in prompt
    assert "general model knowledge is never a substitute" in prompt
    assert "empty packet" in prompt
    assert "one side of a requested comparison" in prompt
    assert "unknown personal fact" not in prompt  # avoid phrase-specific fixture patching
    assert "bounded adaptive recall" in prompt


def test_source_policy_candidate_adds_one_narrow_person_history_domain():
    prompt = " ".join(mechanism.SOURCE_POLICY_CANDIDATE_PROMPT.split()).casefold()
    scopes = mechanism.ExperimentalHistoricalEvidenceScope

    assert scopes.PERSON_HISTORY.value == "PERSON_HISTORY"
    assert "both direct self-report and observed/system-recorded life evidence" in prompt
    assert "runtime/system state" in prompt
    assert "narrowest domain that is sufficient" in prompt
    assert "truth or trust verdict" in prompt


def test_source_policy_experiment_preserves_deterministic_assistant_reference_path():
    fixture, _fixture_hash = mechanism.load_fixture()
    case = next(
        item for item in fixture.source_policy_cases if item["case_id"] == "sp-005-prior-assistant"
    )

    for variant in ("baseline", "candidate"):
        result = mechanism._run_source_policy_variant(
            object(),
            [case],
            variant=variant,
            trials=1,
        )
        attempt = result["cases"][0]["attempts"][0]
        assert attempt["matched_expected"] is True
        assert attempt["execution_path"] == "DETERMINISTIC_PRIOR_ASSISTANT_REFERENCE"
        assert attempt["raw_output"] is None


def test_promotion_requires_complete_candidate_success_improvement_and_no_regression():
    baseline = {
        "cases": [
            {"case_id": "a", "all_trials_matched": True},
            {"case_id": "b", "all_trials_matched": False},
        ]
    }
    candidate = {
        "correct_case_count": 2,
        "case_count": 2,
        "cases": [
            {"case_id": "a", "all_trials_matched": True},
            {"case_id": "b", "all_trials_matched": True},
        ],
    }

    accepted = mechanism._promotion_verdict(baseline, candidate)

    assert accepted["accepted_for_production_promotion"] is True
    assert accepted["improved_case_ids"] == ["b"]
    assert accepted["regressed_case_ids"] == []

    review_required = mechanism._promotion_verdict(
        baseline,
        candidate,
        requires_human_review=True,
    )
    assert review_required["mechanical_gate_passed"] is True
    assert review_required["accepted_for_production_promotion"] is False
    assert review_required["verdict"] == "MECHANICAL_PASS_HUMAN_REVIEW_REQUIRED"

    candidate["cases"][0]["all_trials_matched"] = False
    candidate["correct_case_count"] = 1
    rejected = mechanism._promotion_verdict(baseline, candidate)
    assert rejected["accepted_for_production_promotion"] is False
    assert rejected["regressed_case_ids"] == ["a"]


def test_committed_exp1_report_matches_reproducible_candidate_code():
    committed = json.loads(exp1.RESULT_PATH.read_text(encoding="utf-8"))
    assert committed == exp1.build_report()
