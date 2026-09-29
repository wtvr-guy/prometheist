"""Reuse a verified, frozen learning phase without admitting probe-time state."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from uuid import UUID
from zipfile import ZipFile

from prometheist import event_artifact_store, percept_journal
from prometheist.self_memory import (
    SELF_MEMORY_POLICY, SelfRepresentation, SelfEvidence, SelfResolution,
    SelfEdge, SelfPrediction,
)

SELF_MEMORY_RECORD_KINDS = (
    "self_representation", "self_evidence", "self_resolution", "self_edge", "self_prediction",
)
_MODELS = dict(zip(SELF_MEMORY_RECORD_KINDS, (
    SelfRepresentation, SelfEvidence, SelfResolution, SelfEdge, SelfPrediction,
), strict=True))


def snapshot_digest(snapshot: dict) -> str:
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def reconstruct_snapshot(learning_root: Path, expected_digest: str) -> dict:
    """Replay only committed cognitive records from the pre-probe learning tree."""
    records: dict[str, dict] = {}
    commits: dict[str, dict] = {}

    def collect(record: dict, commit: dict | None) -> None:
        if commit is None:
            raise ValueError("learning checkpoint contains an uncommitted event")
        if (not event_artifact_store.verify_event_record(record)
            or not event_artifact_store.verify_event_commit(commit)
            or commit["record_hash"] != record["record_hash"]
            or commit["event_id"] != record["event_id"]):
            raise ValueError("learning checkpoint event provenance failed verification")
        event_id = record["event_id"]
        if event_id in records and (records[event_id] != record or commits[event_id] != commit):
            raise ValueError("conflicting learning event copies")
        records[event_id], commits[event_id] = record, commit

    for path in sorted((learning_root / "events").glob("*.jsonl")):
        collect(*event_artifact_store.read_event_file(path))
    for path in sorted((learning_root / "percepts").glob("*.jsonl")):
        entries = percept_journal.read(path)
        committed = {
            entry["event_id"]: entry for entry in entries
            if entry.get("artifact_type") == "EVENT_DATABASE_COMMIT"
        }
        for entry in entries:
            if entry.get("artifact_type") == "EVENT_RECORD":
                collect(entry, committed.get(entry["event_id"]))

    heads: dict[str, dict] = {kind: {} for kind in SELF_MEMORY_RECORD_KINDS}
    for event_id in sorted(records, key=lambda key: (commits[key]["global_seq"], key)):
        record = records[event_id]
        payload = record.get("payload", {})
        kind = payload.get("record_kind")
        if kind not in heads:
            continue
        if record.get("event_type") != "DERIVED_REPRESENTATION" or payload.get("kind") != "COGNITIVE_RECORD":
            raise ValueError("self-memory checkpoint has an invalid record role")
        data = payload["data"]
        _MODELS[kind].model_validate(data)
        if "policy_version" in data and data["policy_version"] != SELF_MEMORY_POLICY:
            raise ValueError("learning checkpoint self-memory policy is incompatible; relearn")
        heads[kind][payload["record_key"]] = data
    snapshot = {kind: sorted(heads[kind].items()) for kind in SELF_MEMORY_RECORD_KINDS}
    if not snapshot["self_representation"] or snapshot_digest(snapshot) != expected_digest:
        raise ValueError("reconstructed learning snapshot does not match the frozen result")
    return snapshot


def load_learning_bundle(
    bundle_path: Path,
    *,
    corpus,
    configured_model: str,
    learning_root: Path,
) -> tuple[dict, dict, list[UUID]]:
    """Verify before copying; exclude every probe subtree from the restored state."""
    from package_benchmark_run import verify_bundle

    bundle_digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    verification = verify_bundle(bundle_path)
    if learning_root.exists():
        raise ValueError("learning destination must be new")
    with ZipFile(bundle_path) as bundle, tempfile.TemporaryDirectory() as temp:
        result = json.loads(bundle.read(verification["result"]))
        manifest = json.loads(bundle.read("artifacts/run_manifest.json"))
        if manifest.get("artifact_type") != "SELF_MEMORY_PERSON_FIDELITY_RUN_MANIFEST":
            raise ValueError("learning reuse requires a self-memory benchmark bundle")
        if (result.get("fixture_sha256") != corpus.fixture_sha256
            or result.get("source_fixture_id") != corpus.benchmark_id
            or result.get("source_fixture_version") != corpus.benchmark_version):
            raise ValueError("learning bundle belongs to a different fixture; run fresh learning")
        if result.get("environment", {}).get("configured_model") != configured_model:
            raise ValueError("learning bundle used a different model; run fresh learning")
        for key in ("benchmark_id", "fixture_sha256", "revision"):
            if manifest.get(key) != result.get(key):
                raise ValueError("learning manifest and result disagree")
        staged = Path(temp) / "learning"
        prefix = "artifacts/learning/"
        for name in bundle.namelist():
            if not name.startswith(prefix):
                continue
            relative = Path(name.removeprefix(prefix))
            if len(relative.parts) != 2 or relative.parts[0] not in {"events", "percepts", "interactions"}:
                raise ValueError("unsupported learning artifact layout")
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
        learning = result["learning"]
        snapshot = reconstruct_snapshot(staged, learning["snapshot_sha256"])
        if hashlib.sha256(bundle_path.read_bytes()).hexdigest() != bundle_digest:
            raise ValueError("learning bundle changed while being read")
        origin = learning.get("origin_revision", result["revision"])
        learning = {
            **learning,
            "origin_revision": origin,
            "execution": "REUSED_FROZEN_SNAPSHOT",
            "reused_from": {"bundle_sha256": bundle_digest, "result_revision": result["revision"]},
        }
        task_ids = [UUID(value) for value in manifest["learning_task_ids"]]
        shutil.copytree(staged, learning_root)
    return snapshot, learning, task_ids
