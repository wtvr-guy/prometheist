"""Run the frozen public person-fidelity baseline on the native v2 pipeline.

This runner intentionally resets a dedicated benchmark database before every
probe.  No probe can inherit another probe's prompt or response, and every model
invocation still travels through the production fresh-worker pipeline.

The JSON result separates structural provenance checks from pending human review.
It never treats phrase matching as evidence that Prometheist resembles a person.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from dotenv import load_dotenv

from jit_agent.person_fidelity_benchmark import (
    HOLDOUT_BENCHMARK_ID,
    FidelityProbe,
    PersonFidelityCorpus,
    canonical_seed_payload,
    chronological_life_events,
    deterministic_fixture_uuid,
    evaluate_structural_probe,
    load_person_fidelity_corpus,
    pending_human_review,
    successful_response_realization,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks" / "person_fidelity_public_v1.json"
HOLDOUT_CORPUS = ROOT / "benchmarks" / "person_fidelity_holdout_v1.json"
RESULT_DIR = ROOT / "benchmarks" / "results"
GENERATED_DIR = ROOT / "benchmarks" / "generated" / "person_fidelity"
HOLDOUT_GENERATED_DIR = ROOT / "benchmarks" / "generated" / "person_fidelity_holdout"
DATABASE_ENV = "PROMETHEIST_PERSON_FIDELITY_DATABASE_URL"


def _generated_dir(corpus: PersonFidelityCorpus) -> Path:
    """Keep holdout evidence in its own tree so neither fixture's bytes move."""

    return HOLDOUT_GENERATED_DIR if corpus.is_holdout else GENERATED_DIR


def _is_untracked_benchmark_evidence(status_line: str) -> bool:
    """Keep prior immutable evidence from invalidating the source-revision guard."""

    if not status_line.startswith("?? "):
        return False
    path = status_line[3:].replace("\\", "/")
    return (
        path.startswith("benchmarks/results/PERSON-FIDELITY-")
        and path.endswith(".json")
    ) or (
        path.startswith("benchmarks/generated/person_fidelity/")
        or path.startswith("benchmarks/generated/person_fidelity_holdout/")
        or path.startswith(".prometheist/artifacts/")
    )


def _require_clean_revision() -> str:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if revision.returncode != 0 or not revision.stdout.strip():
        raise RuntimeError("person-fidelity evidence requires a committed Git revision")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise RuntimeError("could not verify the benchmark worktree state")
    dirty_entries = [
        line
        for line in status.stdout.splitlines()
        if not _is_untracked_benchmark_evidence(line)
    ]
    if dirty_entries:
        raise RuntimeError(
            "person-fidelity native evidence requires a clean source worktree; commit "
            "or stash changes before running"
        )
    return revision.stdout.strip()


def _apply_schema_and_require_benchmark_database(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        database_name = str(cur.fetchone()[0])
    if "benchmark" not in database_name.casefold():
        raise RuntimeError(
            "Refusing person-fidelity resets against database "
            f"{database_name!r}; use a dedicated database whose name contains "
            "'benchmark'."
        )
    with conn.cursor() as cur:
        cur.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    return database_name


def _reset_database(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                cognitive_heads,
                attention_interactions,
                attention_worker_results,
                attention_worker_checkpoints,
                attention_worker_claims,
                attention_worker_claim_observations,
                attention_worker_steps,
                attention_resource_reservations,
                attention_preemption_events,
                attention_scheduling_epochs,
                attention_resource_observations,
                attention_assignments,
                attention_task_transitions,
                attention_scheduler_state,
                attention_tasks,
                attention_execution_resources,
                memory_association_entries,
                memory_projection_entries,
                memory_projection_runs,
                event_integrity,
                events,
                conversations
            RESTART IDENTITY CASCADE
            """
        )
        cur.execute("ALTER SEQUENCE attention_task_created_seq RESTART WITH 1")
    conn.commit()


def _seed_life_record(conn, corpus: PersonFidelityCorpus) -> dict[str, UUID]:
    from jit_agent import event_store

    event_ids: dict[str, UUID] = {}
    for fixture in chronological_life_events(corpus):
        conversation_id = deterministic_fixture_uuid(
            corpus,
            "conversation",
            fixture.conversation_id,
        )
        event_store.start_conversation(conn, conversation_id)
        event = event_store.record_event(
            conn,
            conversation_id=conversation_id,
            correlation_id=deterministic_fixture_uuid(
                corpus,
                "correlation",
                fixture.event_id,
            ),
            event_type=fixture.event_type,
            source=fixture.source,
            payload=canonical_seed_payload(corpus, fixture),
            payload_text=fixture.text,
            event_id=deterministic_fixture_uuid(corpus, "event", fixture.event_id),
        )
        event_ids[fixture.event_id] = event.event_id
    return event_ids


def _prompt_event(conn, conversation_id: UUID, prompt: str):
    from jit_agent import event_store
    from jit_agent.models import EventType

    matches = [
        event
        for event in event_store.get_events_by_conversation(conn, conversation_id)
        if event.event_type is EventType.USER_PROMPT
        and event.payload.get("text") == prompt
    ]
    return matches[-1] if matches else None


def _memory_packet_evidence_refs(
    conn,
    conversation_id: UUID,
    correlation_id: UUID,
) -> list[str]:
    from jit_agent import event_store
    from jit_agent.models import EventType

    references: set[str] = set()
    for event in event_store.get_events_by_conversation(conn, conversation_id):
        if (
            event.correlation_id != correlation_id
            or event.event_type is not EventType.MEMORY_PACKET
        ):
            continue
        for item in event.payload.get("packet", {}).get("items", []):
            source_event_id = item.get("source_event_id")
            if source_event_id:
                references.add(f"event:{source_event_id}")
    return sorted(references)


def _artifact_chain_receipt(
    artifacts: list[dict[str, Any]],
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Return a compact, content-addressed index into the full raw chain."""

    type_counts = Counter(str(item.get("artifact_type", "UNKNOWN")) for item in artifacts)
    stage_results = [
        {
            "artifact_id": item.get("artifact_id"),
            "artifact_hash": item.get("artifact_hash"),
            "journal_sequence": item.get("journal_sequence"),
            "stage": item.get("stage"),
        }
        for item in artifacts
        if item.get("artifact_type") == "STAGE_RESULT"
    ]
    llm_invocations = [
        {
            "artifact_id": item.get("artifact_id"),
            "artifact_hash": item.get("artifact_hash"),
            "journal_sequence": item.get("journal_sequence"),
            "stage": item.get("stage"),
            "kind": item.get("payload", {}).get("kind"),
            "model": item.get("payload", {}).get("model"),
            "error_type": item.get("payload", {}).get("error_type"),
        }
        for item in artifacts
        if item.get("artifact_type") == "LLM_INVOCATION"
    ]
    last = artifacts[-1] if artifacts else None
    return {
        "artifact_count": len(artifacts),
        "artifact_type_counts": dict(sorted(type_counts.items())),
        "chain_valid": bool(verification.get("valid")),
        "chain_complete": bool(verification.get("complete")),
        "chain_errors": list(verification.get("errors", [])),
        "stage_results": stage_results,
        "llm_invocations": llm_invocations,
        "terminal_artifact": (
            {
                "artifact_id": last.get("artifact_id"),
                "artifact_hash": last.get("artifact_hash"),
                "artifact_type": last.get("artifact_type"),
                "journal_sequence": last.get("journal_sequence"),
            }
            if last is not None
            else None
        ),
    }


def _run_probe(
    conn,
    corpus: PersonFidelityCorpus,
    probe: FidelityProbe,
    *,
    run_id: str,
    run_artifact_root: Path,
) -> dict[str, Any]:
    from jit_agent import artifact_journal
    from jit_agent.interaction_contracts import deterministic_interaction_id
    from jit_agent.percept_response_runtime import handle_percept_in_worker_processes

    _reset_database(conn)
    probe_artifact_root = run_artifact_root / probe.probe_id
    if probe_artifact_root.exists() and any(probe_artifact_root.iterdir()):
        raise RuntimeError(f"probe artifact directory is not empty: {probe_artifact_root}")
    os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(probe_artifact_root)
    event_ids = _seed_life_record(conn, corpus)

    conversation_id = uuid4()
    response_text: str | None = None
    execution_error: str | None = None
    started = perf_counter()
    try:
        response_text = handle_percept_in_worker_processes(
            conn,
            probe.prompt,
            conversation_id,
            scheduler_key=f"person-fidelity:{run_id}:{probe.probe_id}",
        )
    except Exception as exc:
        execution_error = f"{type(exc).__name__}: {exc}"
        conn.rollback()
    elapsed = perf_counter() - started

    prompt_event = _prompt_event(conn, conversation_id, probe.prompt)
    interaction_id = (
        deterministic_interaction_id(conversation_id, prompt_event.correlation_id)
        if prompt_event is not None
        else None
    )
    verification: dict[str, Any] = {"valid": False, "complete": False}
    artifacts: list[dict[str, Any]] = []
    artifact_error: str | None = None
    if interaction_id is not None:
        try:
            verification = artifact_journal.verify_interaction_chain(interaction_id)
            artifacts = artifact_journal.interaction_artifacts(interaction_id)
        except Exception as exc:
            artifact_error = f"{type(exc).__name__}: {exc}"

    realization = successful_response_realization(artifacts)
    realization_payload = realization.get("payload", {}) if realization else {}
    evidence_refs = list(realization_payload.get("evidence_refs", []))
    structural = evaluate_structural_probe(
        corpus,
        probe,
        event_ids_by_fixture=event_ids,
        response_text=response_text,
        artifact_chain_valid=bool(verification.get("valid")),
        artifact_chain_complete=bool(verification.get("complete")),
        admitted_evidence_refs=evidence_refs,
    )
    fixture_by_ref = {
        f"event:{event_id}": fixture_id
        for fixture_id, event_id in event_ids.items()
    }
    admitted_fixture_ids = sorted(
        fixture_by_ref[reference]
        for reference in evidence_refs
        if reference in fixture_by_ref
    )
    retrieved_refs = (
        _memory_packet_evidence_refs(
            conn,
            conversation_id,
            prompt_event.correlation_id,
        )
        if prompt_event is not None
        else []
    )
    retrieved_fixture_ids = sorted(
        fixture_by_ref[reference]
        for reference in retrieved_refs
        if reference in fixture_by_ref
    )
    missing_from_retrieval = sorted(
        set(probe.required_event_ids) - set(retrieved_fixture_ids)
    )
    return {
        "probe_id": probe.probe_id,
        "dimension": probe.dimension.value,
        "prompt": probe.prompt,
        "conversation_id": str(conversation_id),
        "prompt_event_id": str(prompt_event.event_id) if prompt_event else None,
        "interaction_id": str(interaction_id) if interaction_id else None,
        "response": response_text,
        "elapsed_seconds": round(elapsed, 6),
        "execution_error": execution_error,
        "artifact_error": artifact_error,
        "artifact_journal": _artifact_chain_receipt(artifacts, verification),
        "response_realization": {
            "artifact_id": realization.get("artifact_id") if realization else None,
            "kind": realization_payload.get("kind"),
            "model": realization_payload.get("model"),
            "transport_layout": realization_payload.get("transport_layout"),
            "admitted_fixture_event_ids": admitted_fixture_ids,
        },
        "memory_retrieval": {
            "retrieved_evidence_refs": retrieved_refs,
            "retrieved_fixture_event_ids": retrieved_fixture_ids,
            "missing_required_fixture_event_ids": missing_from_retrieval,
        },
        "structural_evidence": structural.model_dump(mode="json"),
        "human_review": pending_human_review(probe),
    }


def _validation_summary(corpus: PersonFidelityCorpus) -> dict[str, Any]:
    dimensions: dict[str, int] = {}
    for probe in corpus.probes:
        dimensions[probe.dimension.value] = dimensions.get(probe.dimension.value, 0) + 1
    return {
        "benchmark_id": corpus.benchmark_id,
        "benchmark_version": corpus.benchmark_version,
        "status": corpus.status,
        "fixture_sha256": corpus.fixture_sha256,
        "fictional_subject": corpus.subject.name,
        "life_event_count": len(corpus.life_events),
        "probe_count": len(corpus.probes),
        "dimension_counts": dict(sorted(dimensions.items())),
        "valid": True,
    }


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Match raw journals: explicit UTF-8/LF bytes avoid Windows text translation.
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _artifact_file_inventory(run_artifact_root: Path) -> list[dict[str, Any]]:
    """Inventory every raw benchmark artifact without rewriting its bytes."""

    entries: list[dict[str, Any]] = []
    for path in sorted(run_artifact_root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"benchmark artifact roots must not contain symlinks: {path}")
        if not path.is_file():
            continue
        if path.name == "run_manifest.json":
            continue
        if path.suffix.casefold() != ".json":
            raise RuntimeError(f"unexpected non-JSON benchmark artifact: {path}")
        raw = path.read_bytes()
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid JSON benchmark artifact: {path}") from exc
        if not isinstance(document, dict):
            raise RuntimeError(f"benchmark artifact is not a JSON object: {path}")
        relative = path.relative_to(run_artifact_root).as_posix()
        parts = Path(relative).parts
        if len(parts) < 3 or parts[1] not in {"events", "interactions"}:
            raise RuntimeError(f"unexpected benchmark artifact layout: {relative}")
        entries.append(
            {
                "relative_path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "artifact_type": document.get("artifact_type"),
                "artifact_id": document.get("artifact_id"),
                "artifact_hash": document.get("artifact_hash"),
                "event_id": document.get("event_id"),
                "record_hash": document.get("record_hash"),
                "commit_hash": document.get("commit_hash"),
                "interaction_id": document.get("interaction_id"),
                "journal_sequence": document.get("journal_sequence"),
                "stage": document.get("stage"),
            }
        )
    return entries


def _build_run_manifest(
    *,
    corpus: PersonFidelityCorpus,
    captured_at: datetime,
    revision: str,
    result_path: Path,
    run_artifact_root: Path,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a complete discovery and byte-integrity manifest for one native run."""

    files = _artifact_file_inventory(run_artifact_root)
    known_probes = {result["probe_id"] for result in results}
    discovered_probes = {Path(item["relative_path"]).parts[0] for item in files}
    if discovered_probes != known_probes:
        raise RuntimeError(
            "benchmark artifact probe directories do not match completed results: "
            f"expected={sorted(known_probes)}, discovered={sorted(discovered_probes)}"
        )

    probe_receipts: list[dict[str, Any]] = []
    for result in results:
        probe_id = str(result["probe_id"])
        probe_files = [
            item
            for item in files
            if Path(item["relative_path"]).parts[0] == probe_id
        ]
        type_counts = Counter(str(item["artifact_type"]) for item in probe_files)
        probe_receipts.append(
            {
                "probe_id": probe_id,
                "interaction_id": result.get("interaction_id"),
                "artifact_directory": probe_id,
                "file_count": len(probe_files),
                "total_bytes": sum(int(item["size_bytes"]) for item in probe_files),
                "artifact_type_counts": dict(sorted(type_counts.items())),
                "interaction_chain": result["artifact_journal"],
            }
        )

    type_counts = Counter(str(item["artifact_type"]) for item in files)
    return {
        "schema_version": 1,
        "artifact_type": "PERSON_FIDELITY_RUN_MANIFEST",
        "benchmark_id": corpus.benchmark_id,
        "benchmark_version": corpus.benchmark_version,
        "fixture_sha256": corpus.fixture_sha256,
        "captured_at": captured_at.isoformat(),
        "revision": revision,
        "privacy_classification": "PUBLIC_SYNTHETIC_FIXTURE",
        "retention_policy": "PERMANENT_APPEND_ONLY",
        "training_status": "UNREVIEWED_RAW_EVIDENCE",
        "result_artifact": _display_path(result_path),
        "artifact_root": _display_path(run_artifact_root),
        "manifest_scope": "Every JSON file below artifact_root except this manifest.",
        "file_count": len(files),
        "total_bytes": sum(int(item["size_bytes"]) for item in files),
        "artifact_type_counts": dict(sorted(type_counts.items())),
        "probe_receipts": probe_receipts,
        "files": files,
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not load JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON artifact is not an object: {path}")
    return value


def _resolve_recorded_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _verify_result_artifacts(result_path: Path) -> dict[str, Any]:
    """Verify the summary receipt, byte inventory, event mirrors, and chains."""

    from jit_agent import artifact_journal, event_artifact_store

    result = _load_json_object(result_path)
    if result.get("schema_version") != 2:
        raise RuntimeError("artifact verification requires a schema-v2 result")
    receipt = result.get("artifact_evidence")
    if not isinstance(receipt, dict):
        raise RuntimeError("result has no artifact_evidence receipt")
    manifest_path = _resolve_recorded_path(str(receipt.get("path", ""))).resolve()
    if not manifest_path.is_file():
        raise RuntimeError(f"artifact manifest does not exist: {manifest_path}")
    if _sha256_file(manifest_path) != receipt.get("sha256"):
        raise RuntimeError("artifact manifest SHA-256 does not match the result receipt")
    if manifest_path.stat().st_size != receipt.get("size_bytes"):
        raise RuntimeError("artifact manifest size does not match the result receipt")

    manifest = _load_json_object(manifest_path)
    if manifest.get("schema_version") != 1:
        raise RuntimeError("unsupported person-fidelity artifact manifest schema")
    if manifest.get("artifact_type") != "PERSON_FIDELITY_RUN_MANIFEST":
        raise RuntimeError("unexpected person-fidelity artifact manifest type")
    for key in ("benchmark_id", "benchmark_version", "fixture_sha256", "revision"):
        if manifest.get(key) != result.get(key):
            raise RuntimeError(f"artifact manifest {key} does not match result")
    for key in (
        "privacy_classification",
        "retention_policy",
        "training_status",
    ):
        if receipt.get(key) != manifest.get(key):
            raise RuntimeError(f"artifact manifest {key} does not match result receipt")

    root = manifest_path.parent.resolve()
    recorded_result = _resolve_recorded_path(str(manifest.get("result_artifact", "")))
    if recorded_result.resolve() != result_path.resolve():
        raise RuntimeError("artifact manifest points to a different result artifact")
    recorded_root = _resolve_recorded_path(str(manifest.get("artifact_root", "")))
    if recorded_root.resolve() != root:
        raise RuntimeError("artifact manifest points to a different artifact root")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise RuntimeError("artifact manifest files must be a list")
    expected_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("artifact manifest file entry is not an object")
        relative_text = str(entry.get("relative_path", ""))
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise RuntimeError(f"unsafe artifact manifest path: {relative_text!r}")
        if relative_text in expected_paths:
            raise RuntimeError(f"duplicate artifact manifest path: {relative_text}")
        expected_paths.add(relative_text)
        target = root.joinpath(*relative.parts).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise RuntimeError(f"manifested artifact does not exist: {relative_text}")
        if target.stat().st_size != entry.get("size_bytes"):
            raise RuntimeError(f"artifact size mismatch: {relative_text}")
        if _sha256_file(target) != entry.get("sha256"):
            raise RuntimeError(f"artifact SHA-256 mismatch: {relative_text}")

    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_paths != expected_paths:
        raise RuntimeError(
            "artifact manifest file set mismatch: "
            f"missing={sorted(expected_paths - actual_paths)}, "
            f"unexpected={sorted(actual_paths - expected_paths)}"
        )

    observed_total_bytes = sum(int(entry["size_bytes"]) for entry in entries)
    observed_type_counts = dict(
        sorted(Counter(str(entry.get("artifact_type")) for entry in entries).items())
    )
    if manifest.get("file_count") != len(entries):
        raise RuntimeError("artifact manifest file_count does not match its inventory")
    if manifest.get("total_bytes") != observed_total_bytes:
        raise RuntimeError("artifact manifest total_bytes does not match its inventory")
    if manifest.get("artifact_type_counts") != observed_type_counts:
        raise RuntimeError(
            "artifact manifest artifact_type_counts do not match its inventory"
        )
    if receipt.get("raw_artifact_file_count") != len(entries):
        raise RuntimeError("result receipt raw artifact count does not match manifest")
    if receipt.get("raw_artifact_total_bytes") != observed_total_bytes:
        raise RuntimeError("result receipt raw artifact bytes do not match manifest")

    result_probes = result.get("probes")
    probe_receipts = manifest.get("probe_receipts")
    if not isinstance(result_probes, list) or not isinstance(probe_receipts, list):
        raise RuntimeError("result probes and manifest probe_receipts must be lists")
    result_by_probe: dict[str, dict[str, Any]] = {}
    for probe in result_probes:
        if not isinstance(probe, dict) or not probe.get("probe_id"):
            raise RuntimeError("result contains an invalid probe record")
        probe_id = str(probe["probe_id"])
        if probe_id in result_by_probe:
            raise RuntimeError(f"duplicate result probe: {probe_id}")
        result_by_probe[probe_id] = probe
    receipt_by_probe: dict[str, dict[str, Any]] = {}
    for probe in probe_receipts:
        if not isinstance(probe, dict) or not probe.get("probe_id"):
            raise RuntimeError("manifest contains an invalid probe receipt")
        probe_id = str(probe["probe_id"])
        if probe_id in receipt_by_probe:
            raise RuntimeError(f"duplicate manifest probe receipt: {probe_id}")
        receipt_by_probe[probe_id] = probe
    if result_by_probe.keys() != receipt_by_probe.keys():
        raise RuntimeError("result and manifest describe different probe sets")

    prior_root = os.environ.get("PROMETHEIST_ARTIFACT_ROOT")
    verified_events = 0
    verified_interactions = 0
    complete_interactions = 0
    invalid_interactions = 0
    missing_interactions = 0
    try:
        for probe_id, probe in receipt_by_probe.items():
            result_probe = result_by_probe[probe_id]
            if probe.get("artifact_directory") != probe_id:
                raise RuntimeError(f"{probe_id}: artifact directory is not canonical")
            if probe.get("interaction_id") != result_probe.get("interaction_id"):
                raise RuntimeError(f"{probe_id}: interaction ID differs from result")
            expected_chain = probe.get("interaction_chain")
            if expected_chain != result_probe.get("artifact_journal"):
                raise RuntimeError(f"{probe_id}: interaction receipt differs from result")
            if not isinstance(expected_chain, dict):
                raise RuntimeError(f"{probe_id}: interaction receipt is invalid")
            probe_entries = [
                entry
                for entry in entries
                if PurePosixPath(str(entry["relative_path"])).parts[0] == probe_id
            ]
            probe_type_counts = dict(
                sorted(
                    Counter(
                        str(entry.get("artifact_type")) for entry in probe_entries
                    ).items()
                )
            )
            if probe.get("file_count") != len(probe_entries):
                raise RuntimeError(f"{probe_id}: artifact file count changed")
            if probe.get("total_bytes") != sum(
                int(entry["size_bytes"]) for entry in probe_entries
            ):
                raise RuntimeError(f"{probe_id}: artifact byte count changed")
            if probe.get("artifact_type_counts") != probe_type_counts:
                raise RuntimeError(f"{probe_id}: artifact type counts changed")

            probe_root = root / probe_id
            os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(probe_root)
            event_pairs = event_artifact_store.iter_event_artifacts()
            if any(pair["commit"] is None for pair in event_pairs):
                raise RuntimeError(f"{probe_id}: canonical event artifact lacks commit receipt")
            verified_events += len(event_pairs)
            if probe.get("interaction_id") is None:
                if expected_chain.get("artifact_count") != 0:
                    raise RuntimeError(
                        f"{probe_id}: artifacts exist without an interaction ID"
                    )
                missing_interactions += 1
                continue
            interaction_id = UUID(str(probe["interaction_id"]))
            verification = artifact_journal.verify_interaction_chain(interaction_id)
            if verification["artifact_count"] != expected_chain["artifact_count"]:
                raise RuntimeError(f"{probe_id}: interaction artifact count changed")
            if bool(verification["valid"]) != bool(expected_chain.get("chain_valid")):
                raise RuntimeError(f"{probe_id}: interaction validity receipt changed")
            if bool(verification["complete"]) != bool(
                expected_chain.get("chain_complete")
            ):
                raise RuntimeError(f"{probe_id}: interaction completeness receipt changed")
            if list(verification.get("errors", [])) != list(
                expected_chain.get("chain_errors", [])
            ):
                raise RuntimeError(f"{probe_id}: interaction error receipt changed")
            last = verification["last_artifact"]
            expected_last = expected_chain["terminal_artifact"]
            if (last is None) != (expected_last is None):
                raise RuntimeError(f"{probe_id}: interaction terminal receipt changed")
            if last is not None and last.get("artifact_hash") != expected_last.get(
                "artifact_hash"
            ):
                raise RuntimeError(f"{probe_id}: interaction terminal hash changed")
            if verification["valid"]:
                verified_interactions += 1
            else:
                invalid_interactions += 1
            if verification["complete"]:
                complete_interactions += 1
    finally:
        if prior_root is None:
            os.environ.pop("PROMETHEIST_ARTIFACT_ROOT", None)
        else:
            os.environ["PROMETHEIST_ARTIFACT_ROOT"] = prior_root

    fully_valid = (
        invalid_interactions == 0
        and missing_interactions == 0
        and complete_interactions == len(result_by_probe)
    )
    return {
        "status": (
            "VALID_COMPLETE"
            if fully_valid
            else "VALID_PRESERVED_PARTIAL_OR_FAILED_EXECUTION"
        ),
        "result_path": str(result_path.resolve()),
        "manifest_path": str(manifest_path),
        "manifest_sha256": receipt["sha256"],
        "artifact_file_count": len(entries),
        "verified_event_count": verified_events,
        "verified_interaction_count": verified_interactions,
        "complete_interaction_count": complete_interactions,
        "invalid_interaction_count": invalid_interactions,
        "missing_interaction_count": missing_interactions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--holdout",
        action="store_true",
        help="run the prospectively frozen holdout person instead of the public baseline",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument(
        "--verify-result",
        type=Path,
        help="verify a schema-v2 result and every raw artifact named by its manifest",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate the frozen fixture without PostgreSQL or Ollama",
    )
    args = parser.parse_args()
    if args.verify_result is not None:
        print(
            json.dumps(
                _verify_result_artifacts(args.verify_result),
                indent=2,
                sort_keys=True,
            )
        )
        return
    corpus = load_person_fidelity_corpus(
        HOLDOUT_CORPUS if args.holdout and args.corpus == DEFAULT_CORPUS else args.corpus
    )
    if args.holdout and corpus.benchmark_id != HOLDOUT_BENCHMARK_ID:
        raise SystemExit("--holdout requires the frozen holdout fixture")
    if args.validate_only:
        print(json.dumps(_validation_summary(corpus), indent=2, sort_keys=True))
        return

    # Resolve the dedicated connection before importing db, whose normal .env
    # loading otherwise happens too late for this benchmark's configuration gate.
    # Explicit process settings (including the PowerShell parameter) take priority.
    load_dotenv(ROOT / ".env", override=False)
    database_url = os.environ.get(DATABASE_ENV, "").strip()
    if not database_url:
        raise SystemExit(
            f"Set {DATABASE_ENV} in the repository .env or the current shell, "
            "or pass -DatabaseUrl to scripts/run_person_fidelity_baseline.ps1. "
            "It must select a dedicated resettable PostgreSQL database whose "
            "name contains 'benchmark', such as prometheist_fidelity_benchmark. "
            "The normal DATABASE_URL is not used as a fallback."
        )
    os.environ["DATABASE_URL"] = database_url

    captured_at = datetime.now(timezone.utc)
    run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")
    revision = _require_clean_revision()
    run_artifact_root = (args.artifact_root or _generated_dir(corpus) / run_id).resolve()
    if run_artifact_root.exists() and any(run_artifact_root.iterdir()):
        raise SystemExit(f"artifact root must be empty: {run_artifact_root}")
    output = args.output or RESULT_DIR / f"{corpus.benchmark_id}_{run_id}.json"
    if output.exists():
        raise SystemExit(f"result artifact already exists: {output}")
    if output.resolve().is_relative_to(run_artifact_root):
        raise SystemExit("result artifact must be outside the raw artifact root")
    manifest_path = run_artifact_root / "run_manifest.json"

    from jit_agent import db
    from jit_agent.ollama_runtime import configured_ollama_base_url, configured_ollama_model

    with db.get_connection() as conn:
        database_name = _apply_schema_and_require_benchmark_database(conn)
        results = []
        for index, probe in enumerate(corpus.probes, start=1):
            print(
                f"[{index}/{len(corpus.probes)}] {probe.probe_id} "
                f"({probe.dimension.value})",
                flush=True,
            )
            result = _run_probe(
                conn,
                corpus,
                probe,
                run_id=run_id,
                run_artifact_root=run_artifact_root,
            )
            results.append(result)
            print(
                "  structural="
                + ("PASS" if result["structural_evidence"]["passed"] else "FAIL"),
                flush=True,
            )

    structural_passes = sum(
        bool(result["structural_evidence"]["passed"])
        for result in results
    )
    manifest = _build_run_manifest(
        corpus=corpus,
        captured_at=captured_at,
        revision=revision,
        result_path=output,
        run_artifact_root=run_artifact_root,
        results=results,
    )
    _write_result(manifest_path, manifest)
    manifest_receipt = {
        "status": "CAPTURED_AND_INVENTORIED",
        "path": _display_path(manifest_path),
        "sha256": _sha256_file(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
        "raw_artifact_root": _display_path(run_artifact_root),
        "raw_artifact_file_count": manifest["file_count"],
        "raw_artifact_total_bytes": manifest["total_bytes"],
        "privacy_classification": manifest["privacy_classification"],
        "retention_policy": manifest["retention_policy"],
        "training_status": manifest["training_status"],
    }
    payload = {
        "schema_version": 2,
        "benchmark_id": corpus.benchmark_id,
        "benchmark_version": corpus.benchmark_version,
        "benchmark_status": corpus.status,
        "fixture_sha256": corpus.fixture_sha256,
        "captured_at": captured_at.isoformat(),
        "revision": revision,
        "runner": "benchmarks/run_person_fidelity_baseline.py",
        "environment": {
            "database_name": database_name,
            "platform": platform.platform(),
            "python": sys.version,
            "ollama_base_url": configured_ollama_base_url(),
            "configured_model": configured_ollama_model(),
            "artifact_root": str(run_artifact_root),
        },
        "result": (
            "PENDING_HUMAN_REVIEW"
            if structural_passes == len(results)
            else "STRUCTURAL_FAILURES_AND_PENDING_HUMAN_REVIEW"
        ),
        "claim_boundary": (
            "Structural passes establish evidence delivery and artifact integrity only. "
            "No identity-fidelity, identity-maturity, consciousness, or personal-continuity "
            "claim exists until the recorded responses receive independent human review."
        ),
        "structural_summary": {
            "passed": structural_passes,
            "total": len(results),
            "all_passed": structural_passes == len(results),
        },
        "review_protocol": corpus.review_protocol.model_dump(mode="json"),
        "artifact_evidence": manifest_receipt,
        "probes": results,
    }
    _write_result(output, payload)
    artifact_verification = _verify_result_artifacts(output)

    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    print(f"\nResult artifact: {output}")
    print(f"Raw artifact manifest: {manifest_path}")
    print(
        "Artifact verification: "
        f"{artifact_verification['status']} "
        f"({artifact_verification['artifact_file_count']} files, "
        f"{artifact_verification['verified_interaction_count']} interactions)"
    )
    print("HUMAN REVIEW REQUIRED: score every response using the embedded oracle.")


if __name__ == "__main__":
    main()
