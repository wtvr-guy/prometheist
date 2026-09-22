from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

from benchmarks import person_fidelity_exp1_lexical_candidates as exp1
from benchmarks import run_person_fidelity_mechanism_experiments as mechanism


def test_mechanism_fixture_is_frozen_and_independent_of_person_holdout_content():
    fixture, fixture_hash = mechanism.load_fixture()

    assert fixture.status == "FROZEN_BEFORE_NATIVE_V2_EXECUTION"
    assert len(fixture.composer_cases) == 17
    assert len(fixture.source_policy_cases) == 19
    assert len(fixture_hash) == 64

    serialized = mechanism.FIXTURE_PATH.read_text(encoding="utf-8").casefold()
    assert "mara" not in serialized
    assert "wren" not in serialized
    assert len({case["case_id"] for case in fixture.composer_cases}) == 17
    assert len({case["case_id"] for case in fixture.source_policy_cases}) == 19
    assert {
        case["evaluation_group"] for case in fixture.composer_cases
    } == {"V1_RETEST", "V2_PROSPECTIVE_HOLDOUT"}
    assert {
        case["evaluation_group"] for case in fixture.source_policy_cases
    } == {"V1_RETEST", "V2_PROSPECTIVE_HOLDOUT"}

    v1_fixture, _v1_hash = mechanism.load_fixture(mechanism.FIXTURE_PATH_V1)
    assert v1_fixture.status == "FROZEN_BEFORE_NATIVE_CANDIDATE_SELECTION"
    assert len(v1_fixture.composer_cases) == 10
    assert len(v1_fixture.source_policy_cases) == 11


def test_composer_candidate_distinguishes_generic_answerability_from_person_support():
    prompt = " ".join(mechanism.COMPOSER_CANDIDATE_PROMPT.split()).casefold()

    assert "this particular person's prior history" in prompt
    assert "current prompt is direct evidence" in prompt
    assert "material-slot check" in prompt
    assert "diagnostic for the requested context" in prompt
    assert "compatible with materially different answers" in prompt
    assert "empty packet" in prompt
    assert "only one side of a requested comparison" in prompt
    assert "bounded adaptive recall" in prompt
    assert mechanism.COMPOSER_CANDIDATE_PROMPT_V1 != mechanism.COMPOSER_CANDIDATE_PROMPT_V2


def test_source_policy_candidate_adds_one_narrow_person_history_domain():
    prompt = " ".join(mechanism.SOURCE_POLICY_CANDIDATE_PROMPT.split()).casefold()
    scopes = mechanism.ExperimentalHistoricalEvidenceScope

    assert scopes.PERSON_HISTORY.value == "PERSON_HISTORY"
    assert "both direct self-report and observed/system-recorded life evidence" in prompt
    assert "external producer beats system_record" in prompt
    assert "internal derivation beats system_record" in prompt
    assert "raw operational control-plane state" in prompt
    assert "narrowest domain that is sufficient" in prompt
    assert "truth or trust verdict" in prompt
    assert (
        mechanism.SOURCE_POLICY_CANDIDATE_PROMPT_V1
        != mechanism.SOURCE_POLICY_CANDIDATE_PROMPT_V2
    )


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


def test_evaluation_groups_report_retest_and_prospective_results_separately():
    summary = mechanism._evaluation_group_summary(
        [
            {"evaluation_group": "V1_RETEST", "all_trials_matched": True},
            {"evaluation_group": "V1_RETEST", "all_trials_matched": False},
            {"evaluation_group": "V2_PROSPECTIVE_HOLDOUT", "all_trials_matched": True},
        ]
    )

    assert summary == {
        "V1_RETEST": {"correct_case_count": 1, "case_count": 2},
        "V2_PROSPECTIVE_HOLDOUT": {"correct_case_count": 1, "case_count": 1},
    }


def test_committed_exp1_report_matches_reproducible_candidate_code():
    committed = json.loads(exp1.RESULT_PATH.read_text(encoding="utf-8"))
    assert committed == exp1.build_report()


def test_v1_native_results_remain_verifiable_across_fixture_line_endings():
    result_names = (
        "PERSON-FIDELITY-EXP2-COMPOSER-SUFFICIENCY_2026-09-21_130207.json",
        "PERSON-FIDELITY-EXP3-HISTORICAL-SOURCE-POLICY_2026-09-21_130846.json",
    )

    for result_name in result_names:
        verification = mechanism.verify_result(mechanism.RESULT_DIR / result_name)
        assert verification["valid"] is True
        assert verification["candidate_version"] == "v1"
        assert verification["legacy_fixture_eol_accepted"] is True


def test_v2_fixture_hash_is_lf_canonical():
    _fixture, fixture_hash = mechanism.load_fixture(mechanism.FIXTURE_PATH_V2)
    raw = mechanism.FIXTURE_PATH_V2.read_bytes()

    assert b"\r\n" not in raw
    assert fixture_hash == mechanism._sha256_bytes(raw)


def test_deterministic_attempt_writes_complete_chain_without_fake_llm_invocation(
    tmp_path,
):
    fixture, fixture_hash = mechanism.load_fixture()
    case = next(
        item for item in fixture.source_policy_cases if item["case_id"] == "sp-005-prior-assistant"
    )
    artifact_root = tmp_path / "artifacts"
    artifact_run = {
        "run_id": "test-run",
        "artifact_root": artifact_root,
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "fixture_sha256": fixture_hash,
        "revision": "test-revision",
    }

    result = mechanism._run_source_policy_variant(
        object(),
        [case],
        variant="baseline",
        trials=1,
        artifact_run=artifact_run,
    )

    receipt = result["cases"][0]["attempts"][0]["artifact_journal"]
    assert receipt["chain_valid"] is True
    assert receipt["chain_complete"] is True
    assert receipt["artifact_type_counts"] == {
        "BENCHMARK_CASE_INPUT": 1,
        "BENCHMARK_EVALUATION": 1,
        "FINAL_DISPOSITION": 1,
        "STAGE_RESULT": 1,
    }


def test_model_attempt_journals_exact_llm_invocation(tmp_path, monkeypatch):
    fixture, fixture_hash = mechanism.load_fixture()
    case = fixture.composer_cases[0]
    artifact_run = {
        "run_id": "model-test-run",
        "artifact_root": tmp_path / "artifacts",
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "fixture_sha256": fixture_hash,
        "revision": "test-revision",
    }

    monkeypatch.setattr(
        mechanism.OllamaClient,
        "_structured_with_evidence",
        lambda *args, **kwargs: json.dumps(
            {"sufficient": case["expected_sufficient"], "memory_deficit": None}
        ),
    )
    result = mechanism._run_composer_variant(
        mechanism.OllamaClient(),
        [case],
        variant="baseline",
        trials=1,
        artifact_run=artifact_run,
    )

    receipt = result["cases"][0]["attempts"][0]["artifact_journal"]
    assert receipt["artifact_type_counts"]["LLM_INVOCATION"] == 1
    invocation_path = next(
        path
        for path in (tmp_path / "artifacts").rglob("*.json")
        if json.loads(path.read_text(encoding="utf-8"))["artifact_type"]
        == "LLM_INVOCATION"
    )
    payload = json.loads(invocation_path.read_text(encoding="utf-8"))["payload"]
    assert payload["system_prompt"] == mechanism._USER_PROMPT_COMPOSER
    assert payload["user_prompt"].endswith(case["prompt"])
    assert payload["output"] is not None
    assert payload["evidence_prompt"] is not None


def test_artifact_manifest_verification_detects_raw_artifact_mutation(tmp_path):
    fixture, fixture_hash = mechanism.load_fixture()
    case = next(
        item for item in fixture.source_policy_cases if item["case_id"] == "sp-005-prior-assistant"
    )
    artifact_root = tmp_path / "raw"
    artifact_run = {
        "run_id": "manifest-test-run",
        "artifact_root": artifact_root,
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "fixture_sha256": fixture_hash,
        "revision": "test-revision",
    }
    baseline = mechanism._run_source_policy_variant(
        object(), [case], variant="baseline", trials=1, artifact_run=artifact_run
    )
    candidate = mechanism._run_source_policy_variant(
        object(), [case], variant="candidate", trials=1, artifact_run=artifact_run
    )
    report = {
        "schema_version": 3,
        "run_id": "manifest-test-run",
        "experiment_version": mechanism.EXPERIMENT_VERSION_V2,
        "candidate_version": "v2",
        "captured_at": "2026-09-21T00:00:00+00:00",
        "revision": "test-revision",
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "fixture_sha256": fixture_hash,
        "fixture_hash_normalization": "LF_CANONICAL",
        "experiments": {
            "historical_source_policy": {
                "baseline": baseline,
                "candidate": candidate,
            }
        },
    }
    result_path = tmp_path / "result.json"
    manifest_path = artifact_root / "run_manifest.json"
    manifest = mechanism._build_run_manifest(
        report=report,
        result_path=result_path,
        run_artifact_root=artifact_root,
    )
    mechanism._write_json_exclusive(manifest_path, manifest)
    report["artifact_evidence"] = mechanism._manifest_receipt(manifest_path, manifest)
    report["report_sha256"] = mechanism._sha256_bytes(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    )
    mechanism._write_json_exclusive(result_path, report)

    assert mechanism.verify_result(result_path)["valid"] is True
    raw_artifact = next(
        path for path in artifact_root.rglob("*.json") if path != manifest_path
    )
    raw_artifact.write_bytes(raw_artifact.read_bytes() + b" ")
    verification = mechanism.verify_result(result_path)
    assert verification["valid"] is False
    assert verification["checks"]["artifact_evidence_valid"] is False


def test_attempt_artifact_paths_fit_windows_path_budget():
    fixture, _fixture_hash = mechanism.load_fixture()
    case = fixture.composer_cases[0]
    contexts = [
        mechanism._attempt_artifact_context(
            run_id="20260921T215914Z",
            run_artifact_root=Path("unused"),
            experiment="composer_sufficiency",
            variant=variant,
            case=case,
            trial=trial,
        )
        for variant in ("baseline", "candidate")
        for trial in range(1, 4)
    ]

    directories = {context.artifact_directory for context in contexts}
    assert len(directories) == 6
    assert all(directory.startswith("a-") for directory in directories)
    assert all("/" not in directory and "\\" not in directory for directory in directories)

    representative_root = PureWindowsPath(
        r"C:\Users\gy0d8\OneDrive\Documents\jit_agent_prototype"
    ) / "benchmarks" / "generated" / "pfmx" / "2026-09-21_215914"
    longest_atomic_target = (
        representative_root
        / contexts[0].artifact_directory
        / "interactions"
        / "d9166ac6-e9d7-51c1-a3ff-87865dd3e642"
        / ".000001-a1e92c0267b25b97b6c524ed59ce8f0c.json.4294967295.tmp"
    )
    assert len(str(longest_atomic_target)) < 240
