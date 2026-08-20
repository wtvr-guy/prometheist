"""Load and verify artifactized benchmark fixtures.

This module is intentionally benchmark-focused. It demonstrates an indexed,
artifact-per-occurrence representation without replacing the production event
store. The manifest explicitly names every artifact; loaders never discover
history by recursively scanning directories.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _safe_path(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError(f"artifact path must be relative: {relative_path}")
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes dataset root: {relative_path}") from exc
    return resolved


def _load_ref(root: Path, reference: Mapping[str, Any]) -> dict[str, Any]:
    path = _safe_path(root, str(reference["path"]))
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = str(reference["canonical_sha256"])
    actual = canonical_sha256(value)
    if actual != expected:
        raise ValueError(
            f"artifact hash mismatch for {reference['path']}: "
            f"expected={expected} actual={actual}"
        )
    return value


def _assert_unique(values: list[str], *, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label} in artifactized dataset")


def verify_manifest(dataset_root: str | Path) -> dict[str, Any]:
    root = Path(dataset_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    all_refs = [
        manifest["profile"],
        manifest["oracle"],
        *manifest.get("events", []),
        *manifest.get("questions", []),
        *manifest.get("associations", []),
    ]
    paths = [str(ref["path"]) for ref in all_refs]
    _assert_unique(paths, label="artifact paths")

    artifacts = [_load_ref(root, ref) for ref in all_refs]
    artifact_ids = [str(artifact["artifact_id"]) for artifact in artifacts]
    _assert_unique(artifact_ids, label="artifact IDs")
    return manifest


def materialize_benchmark(dataset_root: str | Path) -> dict[str, Any]:
    root = Path(dataset_root)
    manifest = verify_manifest(root)

    profile = _load_ref(root, manifest["profile"])
    oracle = _load_ref(root, manifest["oracle"])
    if profile["artifact_type"] != "PERSONA_PROFILE":
        raise ValueError("profile artifact has wrong artifact_type")
    if oracle["artifact_type"] != "EVALUATOR_ORACLE":
        raise ValueError("oracle artifact has wrong artifact_type")

    events: list[dict[str, Any]] = []
    for ref in manifest["events"]:
        artifact = _load_ref(root, ref)
        payload = artifact["payload"]
        events.append(
            {
                "event_id": artifact["artifact_id"],
                "global_seq": artifact["global_seq"],
                "conversation_id": artifact["conversation_id"],
                "conversation_seq": artifact["conversation_seq"],
                "event_type": artifact["artifact_type"],
                "source": artifact["source"],
                "created_at": artifact["created_at"],
                "text": payload["text"],
                "payload": {key: value for key, value in payload.items() if key != "text"},
            }
        )

    questions: list[dict[str, Any]] = []
    for ref in manifest["questions"]:
        artifact = _load_ref(root, ref)
        if artifact["artifact_type"] != "BENCHMARK_QUERY":
            raise ValueError("question artifact has wrong artifact_type")
        questions.append({"id": artifact["artifact_id"], **artifact["payload"]})

    return {
        "benchmark_version": manifest["materializes_benchmark_version"],
        "persona": {**profile["payload"], "oracle": oracle["payload"]},
        "events": events,
        "questions": questions,
    }


def materialize_associations(dataset_root: str | Path) -> list[dict[str, Any]]:
    root = Path(dataset_root)
    manifest = verify_manifest(root)
    result: list[dict[str, Any]] = []
    for ref in manifest["associations"]:
        artifact = _load_ref(root, ref)
        if artifact["artifact_type"] != "MEMORY_ASSOCIATION":
            raise ValueError("association artifact has wrong artifact_type")
        result.append({"association_id": artifact["artifact_id"], **artifact["payload"]})
    return result
