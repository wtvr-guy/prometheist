"""Independent immutable JSON artifact journal for Prometheist.

PostgreSQL remains the indexed operational store, but it is not the sole surviving
representation of cognition or execution.  Every meaningful interaction boundary
and every canonical event can be mirrored here as an atomically-written,
content-hashed JSON artifact.  Interaction artifacts form a hash-linked chain.

The journal deliberately lives outside the database so it remains inspectable and
usable for recovery when scheduler tables or the database itself are unavailable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import UUID, uuid5

from jit_agent.perception import Percept, SalienceAssessment

ARTIFACT_SCHEMA_VERSION = 1
_ARTIFACT_NAMESPACE = UUID("b983b0b7-a203-5c60-96f0-b17d2d94bf1a")
_SAFE_KEY = re.compile(r"[^a-zA-Z0-9_.-]+")


def artifact_root() -> Path:
    """Return the user-controlled local artifact root."""

    configured = os.environ.get("PROMETHEIST_ARTIFACT_ROOT", "").strip()
    return Path(configured) if configured else Path(".prometheist") / "artifacts"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_key(value: str) -> str:
    normalized = _SAFE_KEY.sub("-", value.strip()).strip("-.")
    return normalized or "artifact"


def _fsync_parent(path: Path) -> None:
    """Best-effort directory fsync; Windows does not expose POSIX directory fsync."""

    try:
        fd = os.open(path, os.O_RDONLY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
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
    _fsync_parent(path.parent)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"artifact is not a JSON object: {path}")
    return value


def _interaction_dir(interaction_id: UUID) -> Path:
    return artifact_root() / "interactions" / str(interaction_id)


def _event_dir() -> Path:
    return artifact_root() / "events"


def interaction_artifacts(interaction_id: UUID) -> list[dict[str, Any]]:
    directory = _interaction_dir(interaction_id)
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        record = _load_json(path)
        record["_path"] = str(path)
        records.append(record)
    records.sort(key=lambda item: int(item["journal_sequence"]))
    return records


def _find_artifact_by_key(interaction_id: UUID, artifact_key: str) -> dict[str, Any] | None:
    for artifact in interaction_artifacts(interaction_id):
        if artifact.get("artifact_key") == artifact_key:
            return artifact
    return None


def write_interaction_artifact(
    *,
    artifact_key: str,
    artifact_type: str,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    payload: dict[str, Any],
    producer: str,
    task_id: UUID | None = None,
    assignment_id: UUID | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """Append one immutable artifact to an interaction hash chain.

    ``artifact_key`` is the idempotency identity.  Repeating the same key with
    identical semantic content returns the existing artifact.  Conflicting retry
    content fails closed.
    """

    existing = _find_artifact_by_key(interaction_id, artifact_key)
    payload_hash = _sha256(payload)
    if existing is not None:
        expected = {
            "artifact_type": artifact_type,
            "conversation_id": str(conversation_id),
            "correlation_id": str(correlation_id),
            "task_id": str(task_id) if task_id else None,
            "assignment_id": str(assignment_id) if assignment_id else None,
            "stage": stage,
            "producer": producer,
            "payload_hash": payload_hash,
        }
        actual = {key: existing.get(key) for key in expected}
        if actual != expected:
            raise ValueError(f"conflicting immutable artifact retry: {artifact_key}")
        return existing

    prior = interaction_artifacts(interaction_id)
    previous = prior[-1] if prior else None
    sequence = int(previous["journal_sequence"]) + 1 if previous else 1
    artifact_id = uuid5(_ARTIFACT_NAMESPACE, f"{interaction_id}:{artifact_key}")
    envelope: dict[str, Any] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_id": str(artifact_id),
        "artifact_key": artifact_key,
        "artifact_type": artifact_type,
        "interaction_id": str(interaction_id),
        "conversation_id": str(conversation_id),
        "correlation_id": str(correlation_id),
        "task_id": str(task_id) if task_id else None,
        "assignment_id": str(assignment_id) if assignment_id else None,
        "stage": stage,
        "producer": producer,
        "journal_sequence": sequence,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "previous_artifact_id": previous.get("artifact_id") if previous else None,
        "previous_artifact_hash": previous.get("artifact_hash") if previous else None,
        "payload_hash": payload_hash,
        "payload": payload,
    }
    envelope["artifact_hash"] = _sha256(envelope)
    filename = f"{sequence:06d}-{_safe_key(artifact_key)}.json"
    target = _interaction_dir(interaction_id) / filename
    if target.exists():
        # A sequence collision can occur only if two writers raced.  Preserve
        # append-only semantics by retrying with the next free sequence.
        while target.exists():
            sequence += 1
            envelope["journal_sequence"] = sequence
            filename = f"{sequence:06d}-{_safe_key(artifact_key)}.json"
            target = _interaction_dir(interaction_id) / filename
        previous = interaction_artifacts(interaction_id)[-1]
        envelope["previous_artifact_id"] = previous.get("artifact_id")
        envelope["previous_artifact_hash"] = previous.get("artifact_hash")
        envelope["artifact_hash"] = _sha256({k: v for k, v in envelope.items() if k != "artifact_hash"})
    _atomic_write_json(target, envelope)
    envelope["_path"] = str(target)
    return envelope


def write_percept_artifact(
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_id: UUID,
    user_text: str,
    user_prompt_event_id: UUID,
    percept: Percept | None = None,
    salience_assessment: SalienceAssessment | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_text": user_text,
        "user_prompt_event_id": str(user_prompt_event_id),
    }
    if percept is not None:
        payload["normalized_percept"] = percept.model_dump(mode="json")
    if salience_assessment is not None:
        payload["salience_assessment"] = salience_assessment.model_dump(mode="json")
    return write_interaction_artifact(
        artifact_key="percept",
        artifact_type="PERCEPT",
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=None,
        stage=None,
        producer="percept_response_v2",
        payload=payload,
    )


def write_stage_result_artifact(
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_id: UUID,
    assignment_id: UUID,
    stage: str,
    output: dict[str, Any],
    output_refs: Iterable[str],
) -> dict[str, Any]:
    return write_interaction_artifact(
        artifact_key=f"stage-result:{stage}",
        artifact_type="STAGE_RESULT",
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage=stage,
        producer="percept_response_v2",
        payload={"output": output, "output_refs": list(output_refs)},
    )


def write_stage_error_artifact(
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_id: UUID,
    assignment_id: UUID,
    stage: str,
    claim_id: UUID,
    error_type: str,
    message: str,
) -> dict[str, Any]:
    return write_interaction_artifact(
        artifact_key=f"stage-error:{stage}:{claim_id}",
        artifact_type="STAGE_ERROR",
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage=stage,
        producer="percept_response_v2",
        payload={
            "claim_id": str(claim_id),
            "error_type": error_type,
            "message": message,
        },
    )


def load_stage_result_artifact(interaction_id: UUID, stage: str) -> dict[str, Any] | None:
    artifact = _find_artifact_by_key(interaction_id, f"stage-result:{stage}")
    if artifact is None:
        return None
    payload = artifact.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("output"), dict):
        raise ValueError(f"invalid stage artifact for {stage}")
    return payload


def write_final_disposition_artifact(
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_id: UUID,
    assignment_id: UUID,
    response_required: bool,
    response_text: str | None,
) -> dict[str, Any]:
    chain = interaction_artifacts(interaction_id)
    references = [
        {
            "artifact_id": item["artifact_id"],
            "artifact_key": item["artifact_key"],
            "artifact_type": item["artifact_type"],
            "journal_sequence": item["journal_sequence"],
            "artifact_hash": item["artifact_hash"],
            "stage": item.get("stage"),
        }
        for item in chain
    ]
    return write_interaction_artifact(
        artifact_key="final-disposition",
        artifact_type="FINAL_DISPOSITION",
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage=None,
        producer="percept_response_v2",
        payload={
            "status": "COMPLETED",
            "last_completed_stage": "V2_PERSIST_RESULT",
            "response_required": response_required,
            "response_text": response_text,
            "artifact_chain": references,
        },
    )


def verify_interaction_chain(interaction_id: UUID) -> dict[str, Any]:
    artifacts = interaction_artifacts(interaction_id)
    previous_id: str | None = None
    previous_hash: str | None = None
    errors: list[str] = []
    for expected_sequence, artifact in enumerate(artifacts, start=1):
        sequence = int(artifact.get("journal_sequence", 0))
        if sequence != expected_sequence:
            errors.append(
                f"sequence gap: expected {expected_sequence}, found {sequence}"
            )
        if artifact.get("previous_artifact_id") != previous_id:
            errors.append(f"previous artifact id mismatch at sequence {sequence}")
        if artifact.get("previous_artifact_hash") != previous_hash:
            errors.append(f"previous artifact hash mismatch at sequence {sequence}")
        payload = artifact.get("payload")
        if artifact.get("payload_hash") != _sha256(payload):
            errors.append(f"payload hash mismatch at sequence {sequence}")
        stored_hash = artifact.get("artifact_hash")
        without_hash = {
            key: value
            for key, value in artifact.items()
            if key not in {"artifact_hash", "_path"}
        }
        if stored_hash != _sha256(without_hash):
            errors.append(f"artifact hash mismatch at sequence {sequence}")
        previous_id = artifact.get("artifact_id")
        previous_hash = stored_hash
    return {
        "interaction_id": str(interaction_id),
        "artifact_count": len(artifacts),
        "valid": not errors,
        "errors": errors,
        "complete": any(item.get("artifact_type") == "FINAL_DISPOSITION" for item in artifacts),
        "last_artifact": artifacts[-1] if artifacts else None,
    }


def inspect_interaction(interaction_id: UUID) -> dict[str, Any]:
    artifacts = interaction_artifacts(interaction_id)
    return {
        "verification": verify_interaction_chain(interaction_id),
        "artifacts": artifacts,
    }


def latest_interaction_id(*, complete: bool | None = None) -> UUID | None:
    directory = artifact_root() / "interactions"
    if not directory.exists():
        return None
    candidates: list[tuple[float, UUID]] = []
    for child in directory.iterdir():
        if not child.is_dir():
            continue
        try:
            interaction_id = UUID(child.name)
        except ValueError:
            continue
        artifacts = interaction_artifacts(interaction_id)
        if not artifacts:
            continue
        is_complete = any(item.get("artifact_type") == "FINAL_DISPOSITION" for item in artifacts)
        if complete is not None and is_complete is not complete:
            continue
        newest = max(Path(item["_path"]).stat().st_mtime for item in artifacts)
        candidates.append((newest, interaction_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].hex), reverse=True)
    return candidates[0][1]


def _event_record_path(event_id: UUID) -> Path:
    return _event_dir() / f"{event_id}.json"


def _event_commit_path(event_id: UUID) -> Path:
    return _event_dir() / f"{event_id}.commit.json"


def write_event_record_artifact(
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
    record = {
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
        "journaled_at": datetime.now(timezone.utc).isoformat(),
    }
    record["record_hash"] = _sha256(record)
    path = _event_record_path(event_id)
    if path.exists():
        existing = _load_json(path)
        comparable_existing = {k: v for k, v in existing.items() if k != "journaled_at"}
        comparable_new = {k: v for k, v in record.items() if k != "journaled_at"}
        if comparable_existing != comparable_new:
            raise ValueError(f"conflicting event artifact retry: {event_id}")
        return existing
    _atomic_write_json(path, record)
    return record


def write_event_commit_artifact(
    *,
    event_id: UUID,
    global_seq: int,
    conversation_seq: int,
    created_at: datetime,
    schema_version: int,
) -> dict[str, Any]:
    record_path = _event_record_path(event_id)
    if not record_path.exists():
        raise RuntimeError(f"event commit has no event record artifact: {event_id}")
    event_record = _load_json(record_path)
    commit = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "EVENT_DATABASE_COMMIT",
        "event_id": str(event_id),
        "record_hash": event_record["record_hash"],
        "global_seq": global_seq,
        "conversation_seq": conversation_seq,
        "created_at": created_at.isoformat(),
        "schema_version": schema_version,
    }
    commit["commit_hash"] = _sha256(commit)
    path = _event_commit_path(event_id)
    if path.exists():
        existing = _load_json(path)
        if existing != commit:
            raise ValueError(f"conflicting event commit artifact retry: {event_id}")
        return existing
    _atomic_write_json(path, commit)
    return commit


def iter_event_artifacts() -> list[dict[str, Any]]:
    directory = _event_dir()
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in directory.glob("*.json"):
        if path.name.endswith(".commit.json"):
            continue
        record = _load_json(path)
        event_id = UUID(str(record["event_id"]))
        commit_path = _event_commit_path(event_id)
        commit = _load_json(commit_path) if commit_path.exists() else None
        records.append({"record": record, "commit": commit})
    records.sort(
        key=lambda item: (
            int(item["commit"]["global_seq"]) if item["commit"] else 2**63 - 1,
            item["record"]["journaled_at"],
            item["record"]["event_id"],
        )
    )
    return records
