"""Immutable filesystem mirror for canonical Prometheist events."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

ARTIFACT_SCHEMA_VERSION = 1


def artifact_root() -> Path:
    configured = os.environ.get("PROMETHEIST_ARTIFACT_ROOT", "").strip()
    return Path(configured) if configured else Path(".prometheist") / "artifacts"


def _event_dir() -> Path:
    return artifact_root() / "events"


def _record_path(event_id: UUID) -> Path:
    return _event_dir() / f"{event_id}.json"


def _commit_path(event_id: UUID) -> Path:
    return _event_dir() / f"{event_id}.commit.json"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"event artifact is not an object: {path}")
    return value


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = json.dumps(
        value,
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8") + b"\n"
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def _semantic_record(
    *,
    event_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    conversation_seq: int,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    payload_text: str | None,
) -> dict[str, Any]:
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "EVENT_RECORD",
        "event_id": str(event_id),
        "conversation_id": str(conversation_id),
        "correlation_id": str(correlation_id),
        "conversation_seq": conversation_seq,
        "event_type": event_type,
        "source": source,
        "payload": payload,
        "payload_text": payload_text,
    }


def write_event_record(
    *,
    event_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    conversation_seq: int,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    payload_text: str | None,
) -> dict[str, Any]:
    semantic = _semantic_record(
        event_id=event_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        conversation_seq=conversation_seq,
        event_type=event_type,
        source=source,
        payload=payload,
        payload_text=payload_text,
    )
    record = dict(semantic)
    record["record_hash"] = _digest(semantic)
    record["journaled_at"] = datetime.now(timezone.utc).isoformat()
    path = _record_path(event_id)
    if path.exists():
        existing = _load(path)
        existing_semantic = {
            key: existing.get(key)
            for key in semantic
        }
        if existing_semantic != semantic or existing.get("record_hash") != record["record_hash"]:
            raise ValueError(f"conflicting event artifact retry: {event_id}")
        return existing
    _atomic_write(path, record)
    return record


def write_event_commit(
    *,
    event_id: UUID,
    global_seq: int,
    conversation_seq: int,
    created_at: datetime,
    schema_version: int,
) -> dict[str, Any]:
    record_path = _record_path(event_id)
    if not record_path.exists():
        raise RuntimeError(f"event commit has no semantic artifact: {event_id}")
    record = _load(record_path)
    semantic = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "EVENT_DATABASE_COMMIT",
        "event_id": str(event_id),
        "record_hash": record["record_hash"],
        "global_seq": global_seq,
        "conversation_seq": conversation_seq,
        "created_at": created_at.isoformat(),
        "schema_version": schema_version,
    }
    commit = dict(semantic)
    commit["commit_hash"] = _digest(semantic)
    path = _commit_path(event_id)
    if path.exists():
        existing = _load(path)
        if existing != commit:
            raise ValueError(f"conflicting event commit artifact retry: {event_id}")
        return existing
    _atomic_write(path, commit)
    return commit


def verify_event_record(record: dict[str, Any]) -> bool:
    semantic = {
        key: value
        for key, value in record.items()
        if key not in {"record_hash", "journaled_at"}
    }
    return record.get("record_hash") == _digest(semantic)


def verify_event_commit(commit: dict[str, Any]) -> bool:
    semantic = {key: value for key, value in commit.items() if key != "commit_hash"}
    return commit.get("commit_hash") == _digest(semantic)


def iter_event_artifacts() -> list[dict[str, Any]]:
    directory = _event_dir()
    if not directory.exists():
        return []
    pairs: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        if path.name.endswith(".commit.json"):
            continue
        record = _load(path)
        if not verify_event_record(record):
            raise RuntimeError(f"event artifact hash verification failed: {path}")
        event_id = UUID(record["event_id"])
        commit_path = _commit_path(event_id)
        commit = _load(commit_path) if commit_path.exists() else None
        if commit is not None:
            if not verify_event_commit(commit):
                raise RuntimeError(f"event commit artifact hash verification failed: {commit_path}")
            if commit["record_hash"] != record["record_hash"]:
                raise RuntimeError(f"event record/commit hash mismatch: {event_id}")
        pairs.append({"record": record, "commit": commit})
    pairs.sort(
        key=lambda item: (
            int(item["commit"]["global_seq"]) if item["commit"] else 2**63 - 1,
            item["record"]["journaled_at"],
            item["record"]["event_id"],
        )
    )
    return pairs
