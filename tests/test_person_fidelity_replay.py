from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks import replay_person_fidelity_retrieval as replay
from benchmarks import person_fidelity_exp1_lexical_candidates as exp1
from prometheist.memory_kernel import MemoryEvent
from prometheist.person_fidelity_benchmark import load_person_fidelity_corpus
from prometheist.response_policy import HistoricalEvidenceScope


ROOT = Path(__file__).resolve().parents[1]
NATIVE_RESULT = (
    ROOT / "benchmarks" / "results" / "PERSON-FIDELITY-001_2026-09-16_215839.json"
)


@pytest.fixture(scope="module")
def baseline():
    return load_person_fidelity_corpus(replay.DEFAULT_CORPUS)


@pytest.fixture(scope="module")
def holdout():
    return load_person_fidelity_corpus(replay.HOLDOUT_CORPUS)


def test_kernel_events_mirror_the_seeded_ledger(baseline):
    events, fixture_by_event_id = replay.kernel_events(baseline)

    assert len(events) == len(baseline.life_events)
    assert all(isinstance(event, MemoryEvent) for event in events)
    assert [event.global_seq for event in events] == list(range(1, len(events) + 1))
    assert [event.created_at for event in events] == sorted(
        event.occurred_at for event in baseline.life_events
    )
    assert set(fixture_by_event_id.values()) == {
        event.event_id for event in baseline.life_events
    }


def test_replay_reproduces_the_recorded_native_run_exactly(baseline):
    report = replay.compare_with_native_result(baseline, NATIVE_RESULT)

    assert report["probe_count"] == 10
    assert report["reproduced_count"] == 10
    assert all(item["reproduced"] for item in report["probes"])


def test_replay_records_the_frozen_negative_retrieval_baseline(baseline, holdout):
    """Both frozen fixtures currently fail the same evidence-selection families.

    This is the negative baseline the 2026-09-17 review localized. It is
    evidence, not a target to be edited away; a change here must be an explicit,
    reviewed mechanism result.
    """

    baseline_report = replay.replay_corpus(baseline)
    holdout_report = replay.replay_corpus(holdout)

    assert baseline_report["retrieval_contract_met_count"] == 2
    assert holdout_report["retrieval_contract_met_count"] == 2

    baseline_by_id = {item["probe_id"]: item for item in baseline_report["probes"]}
    # Long multi-constraint prompts deliver no life evidence at all.
    assert baseline_by_id["pf-q006"]["delivered_fixture_ids"] == []
    assert baseline_by_id["pf-q007"]["delivered_fixture_ids"] == []
    # A single common-word match admits unrelated evidence to the unknown probe.
    assert baseline_by_id["pf-q010"]["unexpected_on_unknown_probe"] == [
        "pf-e014",
        "pf-e017",
    ]

    holdout_by_id = {item["probe_id"]: item for item in holdout_report["probes"]}
    assert holdout_by_id["hf-q007"]["delivered_fixture_ids"] == []
    assert holdout_by_id["hf-q010"]["unexpected_on_unknown_probe"]


def test_observational_system_events_are_lexically_unreachable(baseline):
    """The self-report and belief-change observations share no cue vocabulary.

    No admission threshold can deliver them, which is why the review separates
    the retrieval mechanism from the source-policy mechanism.
    """

    report = replay.replay_corpus(baseline)
    by_id = {item["probe_id"]: item for item in report["probes"]}

    for probe_id, fixture_id in (("pf-q003", "pf-e006"), ("pf-q004", "pf-e009")):
        scores = {
            item["fixture_id"]: item["lexical"]
            for item in by_id[probe_id]["all_event_scores"]
        }
        assert scores[fixture_id] == pytest.approx(0.0)


def test_user_authored_scope_excludes_required_system_event_evidence(baseline):
    """Reproduces the committed source-policy exclusion without a native run."""

    report = replay.replay_corpus(
        baseline, scope=HistoricalEvidenceScope.USER_AUTHORED
    )
    by_id = {item["probe_id"]: item for item in report["probes"]}

    assert "pf-e016" in by_id["pf-q008"]["missing_required"]
    assert "pf-e006" in by_id["pf-q003"]["missing_required"]
    for item in by_id["pf-q008"]["all_event_scores"]:
        if item["fixture_id"] == "pf-e016":
            assert item["source_allowed"] is False


def test_replay_is_deterministic(baseline):
    first = replay.replay_corpus(baseline)
    second = replay.replay_corpus(baseline)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_rejected_exp1_candidates_remain_reproducible(baseline):
    results = {
        candidate.candidate_id: exp1.evaluate_candidate(baseline, candidate)
        for candidate in exp1.CANDIDATES
    }

    assert results["uniform_query_coverage"]["retrieval_contract_met_count"] == 2
    assert results["ledger_idf_coverage"]["retrieval_contract_met_count"] == 2
    assert results["idf_cosine"]["retrieval_contract_met_count"] == 3
    assert results["saturated_matched_mass"]["retrieval_contract_met_count"] == 6
    assert results["bm25"]["retrieval_contract_met_count"] == 5
    assert results["general_saliency_damped_p05"]["retrieval_contract_met_count"] == 6
    assert results["damped_query_mass_p05"]["retrieval_contract_met_count"] == 5

    # The better headline counts are purchased by much higher irrelevant
    # admission, while cosine merely trades one failure family for another.
    assert results["idf_cosine"]["unknown_probe_clean"] is True
    for candidate_id in (
        "saturated_matched_mass",
        "bm25",
        "general_saliency_damped_p05",
        "damped_query_mass_p05",
    ):
        assert results[candidate_id]["noise_admitted"] >= 25


def test_exp1_machine_readable_report_is_deterministic():
    first = exp1.build_report()
    second = exp1.build_report()

    assert first == second
    assert first["status"] == "REJECTED_INSUFFICIENT_DISCRIMINATION"
    assert first["production_changed"] is False
    assert len(first["report_sha256"]) == 64
