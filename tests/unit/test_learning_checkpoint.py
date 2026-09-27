from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from prometheist import event_artifact_store
from prometheist.self_memory import SelfRepresentation

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))
from learning_checkpoint import (  # noqa: E402
    SELF_MEMORY_RECORD_KINDS, load_learning_bundle, reconstruct_snapshot, snapshot_digest,
)
from package_benchmark_run import package_run  # noqa: E402
from run_self_memory_person_fidelity import _composed_memory_from_artifacts  # noqa: E402


def learned_records(root, monkeypatch, *, journal=False, committed=True):
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(root))
    representation_id = uuid4()
    snapshot = {kind: [] for kind in SELF_MEMORY_RECORD_KINDS}
    for sequence, statement in enumerate(("I prefer mornings.", "I prefer afternoons."), 1):
        representation = SelfRepresentation(
            representation_id=representation_id, subject="self", kind="PREFERENCE",
            perspective="AVOWED", statement=statement, plasticity="MEDIUM",
            created_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        ).model_dump(mode="json")
        event_id, conversation_id, correlation_id = uuid4(), uuid4(), uuid4()
        event_artifact_store.write_event_record(
            event_id=event_id, conversation_id=conversation_id, correlation_id=correlation_id,
            conversation_seq=1, event_type="DERIVED_REPRESENTATION", source="cognitive_store",
            payload={"kind": "COGNITIVE_RECORD", "record_kind": "self_representation",
                     "record_key": str(representation_id), "data": representation},
            payload_text=None, journal_id=correlation_id if journal else None,
        )
        if committed:
            event_artifact_store.write_event_commit(
                event_id=event_id, global_seq=sequence, conversation_seq=1,
                created_at=datetime(2026, 9, 27, tzinfo=timezone.utc), schema_version=1,
                conversation_id=conversation_id, correlation_id=correlation_id,
            )
        snapshot["self_representation"] = [(str(representation_id), representation)]
    return snapshot


@pytest.mark.parametrize("journal", [False, True])
def test_reconstructs_latest_committed_heads_from_both_journal_layouts(tmp_path, monkeypatch, journal):
    expected = learned_records(tmp_path, monkeypatch, journal=journal)
    assert reconstruct_snapshot(tmp_path, snapshot_digest(expected)) == expected
    with pytest.raises(ValueError, match="frozen result"):
        reconstruct_snapshot(tmp_path, "wrong digest")


def test_uncommitted_learning_cannot_be_reused(tmp_path, monkeypatch):
    expected = learned_records(tmp_path, monkeypatch, committed=False)
    with pytest.raises(ValueError, match="uncommitted"):
        reconstruct_snapshot(tmp_path, snapshot_digest(expected))


def make_bundle(tmp_path, monkeypatch, **result_overrides):
    raw_root = tmp_path / "run"
    expected = learned_records(raw_root / "learning", monkeypatch)
    # This later probe state must never become the next run's learned state.
    learned_records(raw_root / "probes" / "pf-q001", monkeypatch)
    corpus = SimpleNamespace(benchmark_id="FIXTURE", benchmark_version=1, fixture_sha256="fixture")
    result_path = tmp_path / "result.json"
    task_id = uuid4()
    result = {
        "benchmark_id": "SELF-MEMORY-001", "source_fixture_id": corpus.benchmark_id,
        "source_fixture_version": corpus.benchmark_version, "fixture_sha256": corpus.fixture_sha256,
        "revision": "source-revision", "environment": {"configured_model": "test-model"},
        "learning": {"snapshot_sha256": snapshot_digest(expected), "representation_count": 1},
        **result_overrides,
    }
    manifest = {
        "artifact_type": "SELF_MEMORY_PERSON_FIDELITY_RUN_MANIFEST", "schema_version": 1,
        **{key: result[key] for key in ("benchmark_id", "fixture_sha256", "revision")},
        "artifact_root": str(raw_root), "result_artifact": str(result_path),
        "learning_task_ids": [str(task_id)],
        "files": [{"relative_path": path.relative_to(raw_root).as_posix(),
                   "size_bytes": path.stat().st_size,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in sorted(raw_root.rglob("*.jsonl"))],
    }
    manifest_path = raw_root / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result["artifact_evidence"] = {
        "path": str(manifest_path), "size_bytes": manifest_path.stat().st_size,
        "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    bundle = tmp_path / "source.zip"
    package_run(result_path, bundle)
    return bundle, corpus, expected, task_id, raw_root


def test_bundle_reuse_preserves_original_learning_and_excludes_probe_state(tmp_path, monkeypatch):
    bundle, corpus, expected, task_id, raw_root = make_bundle(tmp_path, monkeypatch)
    destination = tmp_path / "next-run" / "learning"
    snapshot, learning, tasks = load_learning_bundle(
        bundle, corpus=corpus, configured_model="test-model", learning_root=destination,
    )
    assert snapshot == expected
    assert tasks == [task_id]
    assert learning["execution"] == "REUSED_FROZEN_SNAPSHOT"
    assert learning["origin_revision"] == "source-revision"
    assert learning["snapshot_sha256"] == snapshot_digest(expected)
    assert not (destination.parent / "probes").exists()
    copied = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*.jsonl")}
    original = {p.relative_to(raw_root / "learning"): p.read_bytes()
                for p in (raw_root / "learning").rglob("*.jsonl")}
    assert copied == original


@pytest.mark.parametrize("changes,model,match", [
    ({"fixture_sha256": "different"}, "test-model", "different fixture"),
    ({"source_fixture_version": 2}, "test-model", "different fixture"),
    ({}, "another-model", "different model"),
    ({"learning": {"snapshot_sha256": "tampered"}}, "test-model", "frozen result"),
])
def test_incompatible_bundle_fails_before_copying(tmp_path, monkeypatch, changes, model, match):
    bundle, corpus, *_ = make_bundle(tmp_path, monkeypatch, **changes)
    destination = tmp_path / "next-run" / "learning"
    with pytest.raises(ValueError, match=match):
        load_learning_bundle(bundle, corpus=corpus, configured_model=model, learning_root=destination)
    assert not destination.exists()


def test_composed_evidence_report_uses_final_composer_stage():
    def stage(ref):
        return {"artifact_type": "STAGE_RESULT", "stage": "V2_COMPOSE_MEMORY",
                "payload": {"output": {"memory_package": {
                    "memory_packet": {"items": [{"source_event_id": ref}]}, "sufficient": True,
                }}}}
    artifacts = [stage("earlier"), stage("recovered-neighbor"), {"stage": "FINAL_RESPONSE"}]
    assert _composed_memory_from_artifacts(artifacts) == artifacts[1]["payload"]["output"]["memory_package"]
    assert _composed_memory_from_artifacts([]) == {}
