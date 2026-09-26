from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from benchmarks import run_person_fidelity_baseline as native_runner
from benchmarks import run_self_memory_person_fidelity as self_memory_runner
from prometheist import artifact_journal, event_artifact_store
from prometheist.person_fidelity_benchmark import (
    REQUIRED_BASELINE_DIMENSIONS,
    canonical_seed_payload,
    chronological_life_events,
    deterministic_fixture_uuid,
    evaluate_structural_probe,
    fixture_digest,
    load_person_fidelity_corpus,
    successful_response_realization,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "benchmarks" / "person_fidelity_public_v1.json"
HOLDOUT_PATH = ROOT / "benchmarks" / "person_fidelity_holdout_v1.json"


def _corpus():
    return load_person_fidelity_corpus(CORPUS_PATH)


def _holdout():
    return load_person_fidelity_corpus(HOLDOUT_PATH)


def _event_ids(corpus):
    return {
        event.event_id: deterministic_fixture_uuid(corpus, "event", event.event_id)
        for event in corpus.life_events
    }


@pytest.mark.parametrize("shell_override", [False, True])
def test_native_entrypoint_loads_saved_benchmark_config_before_selecting_database(
    tmp_path, monkeypatch, shell_override,
):
    saved_url = "postgresql://fixture@localhost/saved_benchmark"
    shell_url = "postgresql://fixture@localhost/shell_benchmark"
    (tmp_path / ".env").write_text(
        f"{native_runner.DATABASE_ENV}={saved_url}\n"
        "DATABASE_URL=postgresql://fixture@localhost/normal_memory\n"
        "OLLAMA_MODEL=saved-model\n",
        encoding="utf-8",
    )
    environment = {"DATABASE_URL": "postgresql://fixture@localhost/normal_memory"}
    if shell_override:
        environment[native_runner.DATABASE_ENV] = shell_url
        environment["OLLAMA_MODEL"] = "shell-model"
    monkeypatch.setattr(os, "environ", environment)
    monkeypatch.setattr(native_runner, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_person_fidelity_baseline.py"])

    class ConfigurationResolved(Exception):
        pass

    def stop_before_execution():
        assert os.environ["DATABASE_URL"] == (shell_url if shell_override else saved_url)
        assert os.environ["OLLAMA_MODEL"] == (
            "shell-model" if shell_override else "saved-model"
        )
        raise ConfigurationResolved

    monkeypatch.setattr(native_runner, "_require_clean_revision", stop_before_execution)

    with pytest.raises(ConfigurationResolved):
        native_runner.main()


@pytest.mark.parametrize("dedicated_setting", [None, "   "])
def test_native_entrypoint_never_falls_back_to_the_application_database(
    tmp_path, monkeypatch, dedicated_setting,
):
    application_url = "postgresql://fixture@localhost/normal_memory"
    (tmp_path / ".env").write_text(
        f"DATABASE_URL={application_url}\n", encoding="utf-8"
    )
    environment = {}
    if dedicated_setting is not None:
        environment[native_runner.DATABASE_ENV] = dedicated_setting
    monkeypatch.setattr(os, "environ", environment)
    monkeypatch.setattr(native_runner, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_person_fidelity_baseline.py"])

    def unexpected_execution():
        pytest.fail("missing benchmark configuration must stop before native execution")

    monkeypatch.setattr(native_runner, "_require_clean_revision", unexpected_execution)
    with pytest.raises(SystemExit, match="repository .env or the current shell"):
        native_runner.main()
    assert os.environ["DATABASE_URL"] == application_url


def test_frozen_person_fidelity_fixture_is_complete_and_digest_verified():
    corpus = _corpus()

    assert corpus.subject.fictional is True
    assert {probe.dimension for probe in corpus.probes} == REQUIRED_BASELINE_DIMENSIONS
    assert any(probe.expect_no_seeded_evidence for probe in corpus.probes)
    assert any(len(probe.required_event_ids) >= 3 for probe in corpus.probes)
    ordered = chronological_life_events(corpus)
    assert [event.occurred_at for event in ordered] == sorted(
        event.occurred_at for event in corpus.life_events
    )


def test_frozen_holdout_fixture_is_complete_and_shares_no_material_with_baseline():
    holdout = _holdout()
    baseline = _corpus()

    assert holdout.status == "FROZEN_HOLDOUT"
    assert holdout.is_holdout is True
    assert baseline.is_holdout is False
    assert holdout.subject.fictional is True
    assert holdout.subject.name != baseline.subject.name
    assert {probe.dimension for probe in holdout.probes} == REQUIRED_BASELINE_DIMENSIONS
    assert any(probe.expect_no_seeded_evidence for probe in holdout.probes)
    assert any(len(probe.required_event_ids) >= 3 for probe in holdout.probes)

    assert not {event.event_id for event in holdout.life_events} & {
        event.event_id for event in baseline.life_events
    }
    assert not {probe.probe_id for probe in holdout.probes} & {
        probe.probe_id for probe in baseline.probes
    }
    assert not {event.text for event in holdout.life_events} & {
        event.text for event in baseline.life_events
    }
    assert not {probe.prompt for probe in holdout.probes} & {
        probe.prompt for probe in baseline.probes
    }
    # Seeded identifiers must not collide across fixtures sharing one database.
    assert not {
        deterministic_fixture_uuid(holdout, "event", event.event_id)
        for event in holdout.life_events
    } & {
        deterministic_fixture_uuid(baseline, "event", event.event_id)
        for event in baseline.life_events
    }


def test_holdout_digest_is_frozen_before_mechanism_selection():
    document = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))

    assert document["fixture_sha256"] == (
        "b54ec140641ac3bbe5ff25ff3c475a48124fc893dda5f1dc5255b17d6b8ca2b2"
    )
    assert fixture_digest(document) == document["fixture_sha256"]


def test_corpus_rejects_a_relabelled_or_unregistered_fixture_identity(tmp_path):
    document = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))
    relabelled = deepcopy(document)
    relabelled["status"] = "FROZEN_BASELINE"
    relabelled["fixture_sha256"] = fixture_digest(relabelled)
    relabelled_path = tmp_path / "relabelled.json"
    relabelled_path.write_text(json.dumps(relabelled), encoding="utf-8")

    unregistered = deepcopy(document)
    unregistered["benchmark_id"] = "PERSON-FIDELITY-999"
    unregistered["fixture_sha256"] = fixture_digest(unregistered)
    unregistered_path = tmp_path / "unregistered.json"
    unregistered_path.write_text(json.dumps(unregistered), encoding="utf-8")

    with pytest.raises(ValueError, match="must declare status"):
        load_person_fidelity_corpus(relabelled_path)
    with pytest.raises(ValueError, match="unregistered person-fidelity benchmark"):
        load_person_fidelity_corpus(unregistered_path)


def test_holdout_canonical_seed_payload_cannot_leak_probe_or_human_oracle():
    holdout = _holdout()
    for event in holdout.life_events:
        serialized = json.dumps(canonical_seed_payload(holdout, event), sort_keys=True)

        assert "human_oracle" not in serialized
        assert "reference_outcome" not in serialized
        assert all(probe.prompt not in serialized for probe in holdout.probes)


def test_fixture_digest_fails_closed_on_unversioned_oracle_or_stimulus_change():
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    tampered = deepcopy(document)
    tampered["probes"][0]["human_oracle"]["reference_outcome"] += " Tampered."

    assert fixture_digest(document) == document["fixture_sha256"]
    assert fixture_digest(tampered) != document["fixture_sha256"]


def test_canonical_seed_payload_cannot_leak_probe_or_human_oracle():
    corpus = _corpus()
    for event in corpus.life_events:
        payload = canonical_seed_payload(corpus, event)
        serialized = json.dumps(payload, sort_keys=True)

        assert payload["text"] == event.text
        assert payload["benchmark_fixture"]["fixture_event_id"] == event.event_id
        assert "human_oracle" not in serialized
        assert "reference_outcome" not in serialized
        assert "faithful_elements" not in serialized
        assert all(probe.prompt not in serialized for probe in corpus.probes)


def test_structural_pass_proves_evidence_delivery_not_semantic_fidelity():
    corpus = _corpus()
    probe = corpus.probes[0]
    event_ids = _event_ids(corpus)
    admitted = [f"event:{event_ids[event_id]}" for event_id in probe.required_event_ids]

    result = evaluate_structural_probe(
        corpus,
        probe,
        event_ids_by_fixture=event_ids,
        response_text="This answer can be semantically wrong and still have a valid receipt.",
        artifact_chain_valid=True,
        artifact_chain_complete=True,
        admitted_evidence_refs=admitted,
    )

    assert result.passed is True
    assert result.missing_required_refs == ()


def test_structural_evaluation_rejects_missing_and_unknown_case_evidence():
    corpus = _corpus()
    event_ids = _event_ids(corpus)
    answerable = corpus.probes[0]
    unknown = next(probe for probe in corpus.probes if probe.expect_no_seeded_evidence)

    missing = evaluate_structural_probe(
        corpus,
        answerable,
        event_ids_by_fixture=event_ids,
        response_text="Non-empty",
        artifact_chain_valid=True,
        artifact_chain_complete=True,
        admitted_evidence_refs=[],
    )
    unexpected = evaluate_structural_probe(
        corpus,
        unknown,
        event_ids_by_fixture=event_ids,
        response_text="I do not know.",
        artifact_chain_valid=True,
        artifact_chain_complete=True,
        admitted_evidence_refs=[f"event:{next(iter(event_ids.values()))}"],
    )

    assert missing.passed is False
    assert missing.missing_required_refs
    assert unexpected.passed is False
    assert unexpected.unexpected_seeded_refs


def test_response_realization_selects_only_last_successful_response_artifact():
    artifacts = [
        {
            "artifact_id": "wrong-stage",
            "artifact_type": "LLM_INVOCATION",
            "stage": "V2_COMPOSE_MEMORY",
            "payload": {"kind": "FINAL_RESPONSE_V2", "output": "ignored"},
        },
        {
            "artifact_id": "failed",
            "artifact_type": "LLM_INVOCATION",
            "stage": "V2_RESPOND",
            "payload": {
                "kind": "FINAL_RESPONSE_V2",
                "output": None,
                "error_type": "RuntimeError",
            },
        },
        {
            "artifact_id": "selected",
            "artifact_type": "LLM_INVOCATION",
            "stage": "V2_RESPOND",
            "payload": {
                "kind": "FINAL_RESPONSE_V2",
                "output": "response",
                "error_type": None,
            },
        },
    ]

    assert successful_response_realization(artifacts)["artifact_id"] == "selected"


def test_loader_rejects_a_changed_fixture_without_an_explicit_new_digest(tmp_path):
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    document["life_events"][0]["text"] += " Changed without versioning."
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="fixture digest mismatch"):
        load_person_fidelity_corpus(path)


def test_native_result_writer_never_overwrites_prior_evidence(tmp_path):
    path = tmp_path / "result.json"
    native_runner._write_result(path, {"result": "baseline"})

    with pytest.raises(FileExistsError):
        native_runner._write_result(path, {"result": "replacement"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"result": "baseline"}


def test_native_result_writer_preserves_utf8_lf_with_windows_text_defaults(
    tmp_path, monkeypatch,
):
    original_open = Path.open

    def windows_text_open(path, mode="r", *args, **kwargs):
        if "b" not in mode and any(flag in mode for flag in "wax"):
            kwargs.setdefault("newline", "\r\n")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", windows_text_open)
    path = tmp_path / "result.json"
    native_runner._write_result(path, {"response": "café"})

    assert path.read_bytes() == '{\n  "response": "café"\n}\n'.encode("utf-8")


def test_git_round_trip_preserves_legacy_and_new_evidence_bytes(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=repository, check=True, capture_output=True,
        ).stdout

    git("init", "--quiet")
    (repository / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    paths = [
        "benchmarks/results/PERSON-FIDELITY-001_example.json",
        "benchmarks/generated/person_fidelity/example/run_manifest.json",
        "benchmarks/generated/person_fidelity/example/pf-q001/events/event.json",
        ".prometheist/artifacts/interactions/example/artifact.json",
    ]
    expected = {}
    for index, relative in enumerate(paths):
        newline = b"\r\n" if index < 2 else b"\n"
        raw = b'{\n  "fixture": "caf\xc3\xa9"\n}\n'.replace(b"\n", newline)
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        expected[relative] = raw

    git("-c", "core.autocrlf=true", "add", ".")
    for relative, raw in expected.items():
        assert git("show", f":{relative}") == raw

    for setting in ("true", "false"):
        checkout = tmp_path / f"checkout-{setting}"
        git(
            "-c", f"core.autocrlf={setting}", "checkout-index", "--all",
            f"--prefix={checkout.as_posix()}/",
        )
        for relative, raw in expected.items():
            assert (checkout / relative).read_bytes() == raw


def test_benchmark_and_test_runtime_artifacts_are_git_visible():
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "benchmarks/generated/" not in ignore_rules
    assert not any(rule.startswith("benchmarks/generated/") for rule in ignore_rules)
    assert ".prometheist/" not in ignore_rules


def test_untracked_native_evidence_does_not_dirty_the_tested_source_revision():
    assert native_runner._is_untracked_benchmark_evidence(
        "?? benchmarks/generated/person_fidelity/20260914T214915Z/pf-q001/events/a.json"
    )
    assert native_runner._is_untracked_benchmark_evidence(
        "?? benchmarks/results/PERSON-FIDELITY-001_2026-09-14_144915.json"
    )
    assert native_runner._is_untracked_benchmark_evidence(
        "?? .prometheist/artifacts/interactions/example/000001-artifact.json"
    )
    assert not native_runner._is_untracked_benchmark_evidence(
        " M benchmarks/generated/person_fidelity/prior-evidence.json"
    )
    assert not native_runner._is_untracked_benchmark_evidence("?? src/unreviewed.py")


def test_artifact_chain_receipt_indexes_every_model_and_stage_boundary():
    artifacts = [
        {
            "artifact_id": "llm-1",
            "artifact_hash": "hash-1",
            "artifact_type": "LLM_INVOCATION",
            "journal_sequence": 1,
            "stage": "V2_COMPOSE_MEMORY",
            "payload": {
                "kind": "V2_MEMORY_SUFFICIENCY",
                "model": "fixture-model",
                "error_type": None,
            },
        },
        {
            "artifact_id": "stage-1",
            "artifact_hash": "hash-2",
            "artifact_type": "STAGE_RESULT",
            "journal_sequence": 2,
            "stage": "V2_COMPOSE_MEMORY",
            "payload": {},
        },
        {
            "artifact_id": "final-1",
            "artifact_hash": "hash-3",
            "artifact_type": "FINAL_DISPOSITION",
            "journal_sequence": 3,
            "stage": None,
            "payload": {},
        },
    ]

    receipt = native_runner._artifact_chain_receipt(
        artifacts,
        {"valid": True, "complete": True},
    )

    assert receipt["artifact_count"] == 3
    assert receipt["artifact_type_counts"] == {
        "FINAL_DISPOSITION": 1,
        "LLM_INVOCATION": 1,
        "STAGE_RESULT": 1,
    }
    assert receipt["llm_invocations"][0]["kind"] == "V2_MEMORY_SUFFICIENCY"
    assert receipt["chain_errors"] == []
    assert receipt["stage_results"][0]["stage"] == "V2_COMPOSE_MEMORY"
    assert receipt["terminal_artifact"]["artifact_hash"] == "hash-3"


def test_run_manifest_hashes_every_raw_artifact_and_labels_training_state(tmp_path):
    corpus = _corpus()
    run_root = tmp_path / "native-run"
    interaction_id = "839a7940-1202-4076-96cf-704c320d17ce"
    event_path = run_root / "pf-q001" / "events" / "event.json"
    interaction_path = (
        run_root
        / "pf-q001"
        / "interactions"
        / interaction_id
        / "000001-artifact.json"
    )
    native_runner._write_result(
        event_path,
        {"artifact_type": "EVENT_RECORD", "event_id": "event-1"},
    )
    native_runner._write_result(
        interaction_path,
        {
            "artifact_type": "FINAL_DISPOSITION",
            "artifact_id": "artifact-1",
            "artifact_hash": "chain-terminal-hash",
            "interaction_id": interaction_id,
            "journal_sequence": 1,
            "stage": None,
        },
    )
    chain_receipt = {
        "artifact_count": 1,
        "artifact_type_counts": {"FINAL_DISPOSITION": 1},
        "chain_valid": True,
        "chain_complete": True,
        "stage_results": [],
        "llm_invocations": [],
        "terminal_artifact": {
            "artifact_id": "artifact-1",
            "artifact_hash": "chain-terminal-hash",
            "artifact_type": "FINAL_DISPOSITION",
            "journal_sequence": 1,
        },
    }
    manifest = native_runner._build_run_manifest(
        corpus=corpus,
        captured_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        revision="a" * 40,
        result_path=tmp_path / "result.json",
        run_artifact_root=run_root,
        results=[
            {
                "probe_id": "pf-q001",
                "interaction_id": interaction_id,
                "artifact_journal": chain_receipt,
            }
        ],
    )

    assert manifest["privacy_classification"] == "PUBLIC_SYNTHETIC_FIXTURE"
    assert manifest["retention_policy"] == "PERMANENT_APPEND_ONLY"
    assert manifest["training_status"] == "UNREVIEWED_RAW_EVIDENCE"
    assert manifest["file_count"] == 2
    assert manifest["probe_receipts"][0]["interaction_chain"] == chain_receipt
    by_path = {item["relative_path"]: item for item in manifest["files"]}
    relative_event_path = "pf-q001/events/event.json"
    assert by_path[relative_event_path]["sha256"] == hashlib.sha256(
        event_path.read_bytes()
    ).hexdigest()


def test_self_memory_resource_preflight_distinguishes_warm_from_cold():
    from prometheist.attention_observation import HostResourceMetrics
    from prometheist.ollama_runtime import OllamaRuntimeState

    class FixedRuntimeProbe:
        def __init__(self, resident):
            self.resident = resident

        def capture(self):
            return OllamaRuntimeState(
                model="qwen3:4b-instruct-2507-q4_K_M",
                probe_ok=True,
                resident=self.resident,
                reported_name=(
                    "qwen3:4b-instruct-2507-q4_K_M"
                    if self.resident
                    else None
                ),
                size_bytes=3_000 * 1024 * 1024 if self.resident else None,
                size_vram_bytes=0 if self.resident else None,
            )

    class FixedHostProbe:
        def capture(self):
            return HostResourceMetrics(
                platform="test",
                logical_cpu_count=8,
                cpu_utilization_percent=10,
                load_1m=0,
                memory_total_mib=16_384,
                memory_available_mib=4_700,
            )

    warm = self_memory_runner._resource_preflight(
        runtime_probe=FixedRuntimeProbe(True),
        host_probe=FixedHostProbe(),
    )
    cold = self_memory_runner._resource_preflight(
        runtime_probe=FixedRuntimeProbe(False),
        host_probe=FixedHostProbe(),
    )

    assert warm["required_incremental_mib"] == 512
    assert warm["admissible"] is True
    assert cold["required_incremental_mib"] == 3_072
    assert cold["admissible"] is False
    assert warm["safe_available_mib"] == cold["safe_available_mib"]


def test_self_memory_resource_preflight_fails_before_execution_when_unsafe():
    with pytest.raises(SystemExit, match="before database reset"):
        self_memory_runner._require_resource_preflight(
            {
                "model": "fixture-model",
                "ollama_residency": "cold-nonresident",
                "physical_available_mib": 4_700,
                "safe_available_mib": 2_907,
                "required_incremental_mib": 3_072,
                "admissible": False,
            }
        )


def test_self_memory_inventory_accepts_learning_and_nested_probe_artifacts(
    tmp_path,
):
    root = tmp_path / "self-memory-run"
    learning_event = root / "learning" / "events" / "learn.json"
    probe_event = root / "probes" / "pf-q005" / "events" / "probe.json"
    probe_interaction = (
        root
        / "probes"
        / "pf-q005"
        / "interactions"
        / "interaction-id"
        / "000001-artifact.json"
    )
    native_runner._write_result(
        learning_event,
        {"artifact_type": "EVENT_RECORD", "event_id": "learn-event"},
    )
    native_runner._write_result(
        probe_event,
        {"artifact_type": "EVENT_DATABASE_COMMIT", "event_id": "probe-event"},
    )
    native_runner._write_result(
        probe_interaction,
        {
            "artifact_type": "FINAL_DISPOSITION",
            "artifact_id": "artifact-1",
            "interaction_id": "interaction-id",
        },
    )

    entries = self_memory_runner._self_memory_artifact_file_inventory(root)

    assert {item["relative_path"] for item in entries} == {
        "learning/events/learn.json",
        "probes/pf-q005/events/probe.json",
        (
            "probes/pf-q005/interactions/"
            "interaction-id/000001-artifact.json"
        ),
    }


def test_self_memory_inventory_rejects_unknown_nested_layout(tmp_path):
    root = tmp_path / "self-memory-run"
    unexpected = root / "probes" / "pf-q005" / "debug" / "trace.json"
    native_runner._write_result(unexpected, {"artifact_type": "DEBUG"})

    with pytest.raises(
        RuntimeError,
        match="unexpected self-memory benchmark artifact layout",
    ):
        self_memory_runner._self_memory_artifact_file_inventory(root)


def test_run_manifest_rejects_unexpected_files_in_artifact_tree(tmp_path):
    run_root = tmp_path / "native-run"
    unexpected = run_root / "pf-q001" / "debug.log"
    unexpected.parent.mkdir(parents=True)
    unexpected.write_text("not an immutable JSON artifact", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unexpected non-JSON benchmark artifact"):
        native_runner._artifact_file_inventory(run_root)


def test_result_verifier_checks_raw_events_and_interaction_chains(tmp_path, monkeypatch):
    corpus = _corpus()
    run_root = tmp_path / "native-run"
    probe_root = run_root / "pf-q001"
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(probe_root))

    event_id = uuid4()
    conversation_id = uuid4()
    correlation_id = uuid4()
    event_artifact_store.write_event_record(
        event_id=event_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        conversation_seq=1,
        event_type="USER_PROMPT",
        source="fixture",
        payload={"text": "fictional evidence"},
        payload_text="fictional evidence",
    )
    event_artifact_store.write_event_commit(
        event_id=event_id,
        global_seq=1,
        conversation_seq=1,
        created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        schema_version=1,
    )

    interaction_id = uuid4()
    task_id = uuid4()
    assignment_id = uuid4()
    artifact_journal.write_interaction_artifact(
        artifact_key="fixture-percept",
        artifact_type="PERCEPT",
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        payload={"text": "fictional prompt"},
        producer="fixture",
        task_id=task_id,
    )
    artifact_journal.write_final_disposition_artifact(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        response_required=True,
        response_text="fictional response",
    )
    artifacts = artifact_journal.interaction_artifacts(interaction_id)
    verification = artifact_journal.verify_interaction_chain(interaction_id)
    chain_receipt = native_runner._artifact_chain_receipt(artifacts, verification)
    result_path = tmp_path / "result.json"
    captured_at = datetime(2026, 9, 14, tzinfo=timezone.utc)
    manifest = native_runner._build_run_manifest(
        corpus=corpus,
        captured_at=captured_at,
        revision="a" * 40,
        result_path=result_path,
        run_artifact_root=run_root,
        results=[
            {
                "probe_id": "pf-q001",
                "interaction_id": str(interaction_id),
                "artifact_journal": chain_receipt,
            }
        ],
    )
    manifest_path = run_root / "run_manifest.json"
    native_runner._write_result(manifest_path, manifest)
    native_runner._write_result(
        result_path,
        {
            "schema_version": 2,
            "benchmark_id": corpus.benchmark_id,
            "benchmark_version": corpus.benchmark_version,
            "fixture_sha256": corpus.fixture_sha256,
            "revision": "a" * 40,
            "artifact_evidence": {
                "privacy_classification": manifest["privacy_classification"],
                "retention_policy": manifest["retention_policy"],
                "training_status": manifest["training_status"],
                "path": str(manifest_path),
                "sha256": native_runner._sha256_file(manifest_path),
                "size_bytes": manifest_path.stat().st_size,
                "raw_artifact_file_count": manifest["file_count"],
                "raw_artifact_total_bytes": manifest["total_bytes"],
            },
            "probes": [
                {
                    "probe_id": "pf-q001",
                    "interaction_id": str(interaction_id),
                    "artifact_journal": chain_receipt,
                }
            ],
        },
    )

    verified = native_runner._verify_result_artifacts(result_path)

    assert verified["status"] == "VALID_COMPLETE"
    assert verified["verified_event_count"] == 1
    assert verified["verified_interaction_count"] == 1

    event_path = next((probe_root / "events").glob("*.json"))
    event_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="artifact (size|SHA-256) mismatch"):
        native_runner._verify_result_artifacts(result_path)


def test_result_verifier_preserves_a_probe_that_failed_before_interaction_creation(
    tmp_path,
    monkeypatch,
):
    corpus = _corpus()
    run_root = tmp_path / "failed-native-run"
    probe_root = run_root / "pf-q001"
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(probe_root))
    event_artifact_store.write_event_record(
        event_id=uuid4(),
        conversation_id=uuid4(),
        correlation_id=uuid4(),
        conversation_seq=1,
        event_type="SYSTEM_EVENT",
        source="fixture",
        payload={"text": "evidence written before process failure"},
        payload_text="evidence written before process failure",
    )
    event_record = next((probe_root / "events").glob("*.json"))
    record = json.loads(event_record.read_text(encoding="utf-8"))
    event_artifact_store.write_event_commit(
        event_id=record["event_id"],
        global_seq=1,
        conversation_seq=1,
        created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        schema_version=1,
    )
    chain_receipt = native_runner._artifact_chain_receipt(
        [],
        {"valid": False, "complete": False, "errors": []},
    )
    probe_result = {
        "probe_id": "pf-q001",
        "interaction_id": None,
        "artifact_journal": chain_receipt,
    }
    result_path = tmp_path / "failed-result.json"
    manifest = native_runner._build_run_manifest(
        corpus=corpus,
        captured_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        revision="b" * 40,
        result_path=result_path,
        run_artifact_root=run_root,
        results=[probe_result],
    )
    manifest_path = run_root / "run_manifest.json"
    native_runner._write_result(manifest_path, manifest)
    native_runner._write_result(
        result_path,
        {
            "schema_version": 2,
            "benchmark_id": corpus.benchmark_id,
            "benchmark_version": corpus.benchmark_version,
            "fixture_sha256": corpus.fixture_sha256,
            "revision": "b" * 40,
            "artifact_evidence": {
                "privacy_classification": manifest["privacy_classification"],
                "retention_policy": manifest["retention_policy"],
                "training_status": manifest["training_status"],
                "path": str(manifest_path),
                "sha256": native_runner._sha256_file(manifest_path),
                "size_bytes": manifest_path.stat().st_size,
                "raw_artifact_file_count": manifest["file_count"],
                "raw_artifact_total_bytes": manifest["total_bytes"],
            },
            "probes": [probe_result],
        },
    )

    verified = native_runner._verify_result_artifacts(result_path)

    assert verified["status"] == "VALID_PRESERVED_PARTIAL_OR_FAILED_EXECUTION"
    assert verified["verified_event_count"] == 1
    assert verified["verified_interaction_count"] == 0
    assert verified["missing_interaction_count"] == 1
