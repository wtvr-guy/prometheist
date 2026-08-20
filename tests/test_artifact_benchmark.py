import json
import shutil
from pathlib import Path

import pytest

from jit_agent.artifact_benchmark import (
    materialize_associations,
    materialize_benchmark,
    verify_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks" / "jordan_vale_v2"
LEGACY_BENCHMARK = ROOT / "benchmarks" / "jordan_vale_v1.json"
LEGACY_ASSOCIATIONS = ROOT / "benchmarks" / "jordan_vale_associations_v1.json"


def test_artifactized_jordan_materializes_exact_legacy_semantics():
    legacy = json.loads(LEGACY_BENCHMARK.read_text(encoding="utf-8"))
    assert materialize_benchmark(DATASET) == legacy


def test_artifactized_associations_materialize_exactly():
    legacy = json.loads(LEGACY_ASSOCIATIONS.read_text(encoding="utf-8"))
    assert materialize_associations(DATASET) == legacy["associations"]


def test_manifest_indexes_one_artifact_per_occurrence():
    manifest = verify_manifest(DATASET)
    assert len(manifest["events"]) == 24
    assert len(manifest["questions"]) == 18
    assert len(manifest["associations"]) == 3

    paths = [
        manifest["profile"]["path"],
        manifest["oracle"]["path"],
        *(ref["path"] for ref in manifest["events"]),
        *(ref["path"] for ref in manifest["questions"]),
        *(ref["path"] for ref in manifest["associations"]),
    ]
    assert len(paths) == 47
    assert len(paths) == len(set(paths))
    assert all(ref["path"].startswith("events/") for ref in manifest["events"])
    assert all(ref["path"].startswith("questions/") for ref in manifest["questions"])
    assert all(ref["path"].startswith("associations/") for ref in manifest["associations"])


def test_manifest_hash_detects_single_artifact_tampering(tmp_path):
    copied = tmp_path / "jordan_vale_v2"
    shutil.copytree(DATASET, copied)
    event_path = copied / "events" / "e001.json"
    artifact = json.loads(event_path.read_text(encoding="utf-8"))
    artifact["payload"]["text"] = "tampered"
    event_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        verify_manifest(copied)


def test_open_world_unknown_remains_absent_from_artifact_memory():
    document = materialize_benchmark(DATASET)
    assert "blood_type" not in document["persona"]["oracle"]
    serialized_events = json.dumps(document["events"], sort_keys=True).casefold()
    assert "blood type" not in serialized_events
    assert "blood_type" not in serialized_events
