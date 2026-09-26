"""Native person-fidelity benchmark that actually learns and uses Self-Memory.

Unlike PERSON-FIDELITY-001/002, this runner performs one production consolidation
and self-reflection learning phase before probing. The resulting self-memory heads
are frozen, then restored into a freshly reset benchmark database for every probe.
That keeps probes isolated without paying for repeated LLM consolidation and without
allowing one probe's prompt/response to train a later probe.

Structural evidence treats an admitted self representation as derived evidence whose
canonical support/opposition roots remain its provenance. Direct episodic evidence
and transitive self-schema roots are reported separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from dotenv import load_dotenv

BENCHMARK_DIR = Path(__file__).resolve().parent
ROOT = BENCHMARK_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

from run_person_fidelity_baseline import (  # noqa: E402
    DEFAULT_CORPUS,
    HOLDOUT_CORPUS,
    DATABASE_ENV,
    _apply_schema_and_require_benchmark_database,
    _artifact_chain_receipt,
    _display_path,
    _memory_packet_evidence_refs,
    _prompt_event,
    _reset_database,
    _sha256_file,
    _write_result,
)
from prometheist.person_fidelity_benchmark import (  # noqa: E402
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

PUBLIC_BENCHMARK_ID = "SELF-MEMORY-001"
HOLDOUT_SELF_BENCHMARK_ID = "SELF-MEMORY-002-HOLDOUT"
GENERATED_DIR = ROOT / "benchmarks" / "generated" / "self_memory_person_fidelity"
RESULT_DIR = ROOT / "benchmarks" / "results"
SELF_MEMORY_RECORD_KINDS = (
    "self_representation",
    "self_evidence",
    "self_resolution",
    "self_edge",
    "self_prediction",
)


def _is_allowed_untracked_evidence(status_line: str) -> bool:
    if not status_line.startswith("?? "):
        return False
    path = status_line[3:].replace("\\", "/")
    return (
        (
            path.startswith("benchmarks/results/SELF-MEMORY-")
            and path.endswith(".json")
        )
        or path.startswith("benchmarks/generated/self_memory_person_fidelity/")
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
        raise RuntimeError("self-memory benchmark requires a committed Git revision")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise RuntimeError("could not verify benchmark worktree state")
    dirty = [
        line
        for line in status.stdout.splitlines()
        if not _is_allowed_untracked_evidence(line)
    ]
    if dirty:
        raise RuntimeError(
            "self-memory evidence requires a clean source worktree; commit or "
            "stash source changes before running"
        )
    return revision.stdout.strip()


def _benchmark_id(corpus: PersonFidelityCorpus) -> str:
    return HOLDOUT_SELF_BENCHMARK_ID if corpus.is_holdout else PUBLIC_BENCHMARK_ID


def _resource_preflight(
    *,
    runtime_probe=None,
    host_probe=None,
    policy=None,
) -> dict[str, Any]:
    """Evaluate the exact native RAM policy before mutating benchmark state."""

    from prometheist.attention_observation import (
        HOST_MEMORY_RESOURCE_ID,
        SystemHostResourceProbe,
        build_resource_observation,
        discover_local_execution_resources,
    )
    from prometheist.native_policy import native_resource_safety_policy
    from prometheist.ollama_runtime import OllamaRuntimeProbe

    effective_policy = policy or native_resource_safety_policy()
    runtime = (runtime_probe or OllamaRuntimeProbe()).capture()
    metrics = (host_probe or SystemHostResourceProbe()).capture()
    resources = discover_local_execution_resources(
        metrics,
        policy=effective_policy,
    )
    snapshot = build_resource_observation(
        scheduler_cycle=1,
        captured_at=datetime.now(timezone.utc),
        resources=resources,
        reservations=[],
        policy=effective_policy,
        metrics=metrics,
    )
    memory = snapshot.capacity_by_resource_id()[HOST_MEMORY_RESOURCE_ID]
    required_mib = runtime.incremental_process_memory_mib(effective_policy)
    safe_available_mib = memory.available_for_new_work
    return {
        "model": runtime.model,
        "ollama_probe_ok": runtime.probe_ok,
        "ollama_resident": runtime.resident,
        "ollama_residency": runtime.residency_label,
        "ollama_error": runtime.error,
        "physical_available_mib": metrics.memory_available_mib,
        "safe_available_mib": safe_available_mib,
        "required_incremental_mib": required_mib,
        "admissible": safe_available_mib >= required_mib,
        "policy_version": effective_policy.policy_version,
    }


def _require_resource_preflight(preflight: dict[str, Any]) -> None:
    if preflight["admissible"]:
        return
    raise SystemExit(
        "Self-memory benchmark resource preflight denied before database reset. "
        f"model={preflight['model']} "
        f"ollama={preflight['ollama_residency']} "
        f"physical_available={preflight['physical_available_mib']} MiB "
        f"safe_available={preflight['safe_available_mib']} MiB "
        f"required={preflight['required_incremental_mib']} MiB. "
        "Free enough RAM for the governed cold-load budget, or intentionally "
        "preload the configured model and verify it appears in ollama ps; "
        "then rerun. Prometheist will use the smaller warm-resident incremental "
        "reservation only after residency is verified."
    )


def _seed_life_record(
    conn,
    corpus: PersonFidelityCorpus,
    *,
    form_situations: bool,
) -> dict[str, UUID]:
    """Seed one equivalent life record with observable behavior as percept evidence."""

    from prometheist import event_store
    from prometheist.models import EventType
    from prometheist.percept_context import PerceptContext
    from prometheist.percept_intake import install_source_policy
    from prometheist.perception import (
        PerceptKind,
        PerceptModality,
        PerceptSource,
        normalize_percept,
    )
    from prometheist.percept_triage import SourcePolicy
    from prometheist.situations import persist_situations

    event_ids: dict[str, UUID] = {}
    installed_observation_sources: set[str] = set()
    for fixture in chronological_life_events(corpus):
        conversation_id = deterministic_fixture_uuid(
            corpus,
            "conversation",
            fixture.conversation_id,
        )
        correlation_id = deterministic_fixture_uuid(
            corpus,
            "correlation",
            fixture.event_id,
        )
        event_id = deterministic_fixture_uuid(corpus, "event", fixture.event_id)
        event_store.start_conversation(conn, conversation_id)
        fixture_context = PerceptContext(
            task_refs=(
                deterministic_fixture_uuid(
                    corpus,
                    "situation-context",
                    fixture.conversation_id,
                ),
            )
        )

        if fixture.event_type is EventType.USER_PROMPT:
            event = event_store.record_event(
                conn,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                event_type=EventType.USER_PROMPT,
                source=fixture.source,
                payload=canonical_seed_payload(corpus, fixture),
                payload_text=fixture.text,
                event_id=event_id,
            )
            if form_situations:
                percept = normalize_percept(
                    source=PerceptSource(
                        source_id="user",
                        kind=PerceptKind.USER_INTERACTION,
                        modality=PerceptModality.TEXT,
                        interface="chat",
                    ),
                    observation=fixture.text,
                    observed_at=fixture.occurred_at,
                    correlation_id=correlation_id,
                    source_event_id=event.event_id,
                    conversation_id=conversation_id,
                    response_required=True,
                    context=fixture_context,
                )
                persist_situations(conn, percept)
        else:
            source_id = f"person-fidelity-observation:{fixture.source}"
            source = PerceptSource(
                source_id=source_id,
                kind=PerceptKind.SYSTEM_OBSERVATION,
                modality=PerceptModality.TEXT,
                interface="person-fidelity-fixture",
            )
            if form_situations and source_id not in installed_observation_sources:
                install_source_policy(
                    conn,
                    SourcePolicy(
                        source_id=source_id,
                        kind=PerceptKind.SYSTEM_OBSERVATION,
                        modalities=(PerceptModality.TEXT,),
                        self_model_evidence=True,
                    ),
                )
                installed_observation_sources.add(source_id)
            percept = normalize_percept(
                source=source,
                observation=fixture.text,
                observed_at=fixture.occurred_at,
                source_event_id=event_id,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                response_required=False,
                context=fixture_context,
            )
            payload = canonical_seed_payload(corpus, fixture)
            payload.update(
                {
                    "observation": fixture.text,
                    "percept": percept.model_dump(mode="json"),
                }
            )
            event = event_store.record_event(
                conn,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                event_type=EventType.PERCEPT_OBSERVATION,
                source=source_id,
                payload=payload,
                payload_text=fixture.text,
                event_id=event_id,
            )
            if form_situations:
                persist_situations(conn, percept)

        event_ids[fixture.event_id] = event.event_id
    return event_ids


def _learn_self_memory(
    conn,
    corpus: PersonFidelityCorpus,
    *,
    run_id: str,
    learning_root: Path,
) -> tuple[dict[str, UUID], list[UUID]]:
    from prometheist.consolidation import (
        ConsolidationSchedule,
        emit_due_consolidations,
        schedule_consolidation,
    )
    from prometheist.situation_runtime import run_situation_task, submit_situation_page

    os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(learning_root)
    event_ids = _seed_life_record(conn, corpus, form_situations=True)
    due_at = datetime.now(timezone.utc)
    schedule_id = deterministic_fixture_uuid(
        corpus,
        "self-memory-consolidation",
        run_id,
    )
    schedule_consolidation(
        conn,
        ConsolidationSchedule(
            schedule_id=schedule_id,
            due_at=due_at,
        ),
    )
    emit_due_consolidations(conn, now=due_at)

    scheduler_key = f"self-memory-learning:{run_id}"
    task_ids = submit_situation_page(conn, scheduler_key=scheduler_key)
    if not task_ids:
        raise RuntimeError("self-memory consolidation produced no runnable situation task")
    completed: list[UUID] = []
    for task_id in task_ids:
        result = run_situation_task(
            conn,
            task_id,
            scheduler_key=scheduler_key,
        )
        if result is None:
            raise RuntimeError(
                "self-memory consolidation remained queued under resource admission"
            )
        completed.append(task_id)
    return event_ids, completed


def _all_head_records(conn, kind: str) -> list[tuple[str, dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT record_key, payload
        FROM cognitive_heads
        WHERE record_kind = %s
        ORDER BY record_key
        """,
        (kind,),
    ).fetchall()
    return [(str(key), dict(payload)) for key, payload in rows]


def _snapshot_self_memory(conn) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    snapshot = {
        kind: _all_head_records(conn, kind)
        for kind in SELF_MEMORY_RECORD_KINDS
    }
    if not snapshot["self_representation"]:
        raise RuntimeError(
            "self-memory learning completed without producing any self representations"
        )
    return snapshot


def _snapshot_digest(
    snapshot: dict[str, list[tuple[str, dict[str, Any]]]],
) -> str:
    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _restore_self_memory(
    conn,
    snapshot: dict[str, list[tuple[str, dict[str, Any]]]],
) -> None:
    from prometheist.cognitive_store import put_record

    digest = _snapshot_digest(snapshot)
    for kind in SELF_MEMORY_RECORD_KINDS:
        for key, payload in snapshot[kind]:
            put_record(
                conn,
                kind,
                key,
                payload,
                revision=f"benchmark-self-snapshot:{digest}",
            )


def _learning_summary(
    conn,
    corpus: PersonFidelityCorpus,
    event_ids: dict[str, UUID],
) -> dict[str, Any]:
    from prometheist.self_memory import (
        SELF_REPRESENTATION_KIND,
        SelfRepresentation,
        current_self_resolution,
        self_evidence,
    )

    fixture_by_event = {
        event_id: fixture_id for fixture_id, event_id in event_ids.items()
    }
    representations: list[dict[str, Any]] = []
    for _key, payload in _all_head_records(conn, SELF_REPRESENTATION_KIND):
        representation = SelfRepresentation.model_validate(payload)
        resolution = current_self_resolution(conn, representation.representation_id)
        evidence = self_evidence(conn, representation.representation_id)
        representations.append(
            {
                "representation_id": str(representation.representation_id),
                "kind": representation.kind.value,
                "perspective": representation.perspective.value,
                "statement": representation.statement,
                "plasticity": representation.plasticity.value,
                "context_tags": list(representation.context_tags),
                "relationship_ref": representation.relationship_ref,
                "future_orientation": (
                    representation.future_orientation.value
                    if representation.future_orientation is not None
                    else None
                ),
                "status": resolution.status.value if resolution else None,
                "identity_centrality": (
                    resolution.identity_centrality.value if resolution else None
                ),
                "metrics": (
                    resolution.metrics.model_dump(mode="json")
                    if resolution
                    else None
                ),
                "canonical_root_fixture_ids": sorted(
                    {
                        fixture_by_event[item.root_event_id]
                        for item in evidence
                        if item.root_event_id in fixture_by_event
                    }
                ),
                "evidence_relations": [
                    {
                        "fixture_event_id": fixture_by_event.get(item.root_event_id),
                        "root_event_id": str(item.root_event_id),
                        "relation": item.relation.value,
                        "origin": item.origin.value,
                        "observed_at": item.observed_at.isoformat(),
                        "known_at": item.known_at.isoformat(),
                    }
                    for item in evidence
                ],
            }
        )
    return {
        "subject": corpus.subject.name,
        "representation_count": len(representations),
        "status_counts": dict(
            sorted(Counter(
                item["status"] or "NONE" for item in representations
            ).items())
        ),
        "representations": representations,
    }


def _expand_self_evidence_refs(
    conn,
    evidence_refs: list[str],
) -> tuple[list[str], list[str]]:
    from prometheist.self_memory import self_evidence

    rooted = {
        reference
        for reference in evidence_refs
        if reference.startswith("event:")
    }
    activated_self: list[str] = []
    for reference in evidence_refs:
        if not reference.startswith("self:"):
            continue
        representation_id = UUID(reference.removeprefix("self:"))
        activated_self.append(str(representation_id))
        rooted.update(
            f"event:{item.root_event_id}"
            for item in self_evidence(conn, representation_id)
        )
    return sorted(rooted), sorted(set(activated_self))


def _active_self_context_from_artifacts(
    artifacts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        item
        for item in artifacts
        if item.get("artifact_type") == "STAGE_RESULT"
        and item.get("stage") == "V2_PRECOGNITIVE"
    ]
    if not candidates:
        return None
    output = candidates[-1].get("payload", {}).get("output", {})
    value = output.get("self_context")
    return value if isinstance(value, dict) else None


def _run_probe(
    conn,
    corpus: PersonFidelityCorpus,
    probe: FidelityProbe,
    *,
    run_id: str,
    run_artifact_root: Path,
    snapshot: dict[str, list[tuple[str, dict[str, Any]]]],
) -> dict[str, Any]:
    from prometheist import artifact_journal
    from prometheist.interaction_contracts import deterministic_interaction_id
    from prometheist.percept_response_runtime import handle_percept_in_worker_processes

    _reset_database(conn)
    probe_root = run_artifact_root / "probes" / probe.probe_id
    if probe_root.exists() and any(probe_root.iterdir()):
        raise RuntimeError(f"probe artifact directory is not empty: {probe_root}")
    os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(probe_root)
    event_ids = _seed_life_record(conn, corpus, form_situations=False)
    _restore_self_memory(conn, snapshot)

    conversation_id = uuid4()
    response_text: str | None = None
    execution_error: str | None = None
    started = perf_counter()
    try:
        response_text = handle_percept_in_worker_processes(
            conn,
            probe.prompt,
            conversation_id,
            scheduler_key=f"self-memory-fidelity:{run_id}:{probe.probe_id}",
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
    direct_refs = list(realization_payload.get("evidence_refs", []))
    rooted_refs, activated_self = _expand_self_evidence_refs(conn, direct_refs)
    structural = evaluate_structural_probe(
        corpus,
        probe,
        event_ids_by_fixture=event_ids,
        response_text=response_text,
        artifact_chain_valid=bool(verification.get("valid")),
        artifact_chain_complete=bool(verification.get("complete")),
        admitted_evidence_refs=rooted_refs,
    )
    fixture_by_ref = {
        f"event:{event_id}": fixture_id
        for fixture_id, event_id in event_ids.items()
    }
    admitted_fixture_ids = sorted(
        fixture_by_ref[reference]
        for reference in rooted_refs
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
            "direct_evidence_refs": direct_refs,
            "rooted_evidence_refs": rooted_refs,
            "admitted_fixture_event_ids": admitted_fixture_ids,
            "activated_self_representation_ids": activated_self,
        },
        "working_self": _active_self_context_from_artifacts(artifacts),
        "memory_retrieval": {
            "retrieved_evidence_refs": retrieved_refs,
            "retrieved_fixture_event_ids": retrieved_fixture_ids,
            "missing_required_fixture_event_ids": sorted(
                set(probe.required_event_ids) - set(retrieved_fixture_ids)
            ),
        },
        "structural_evidence": structural.model_dump(mode="json"),
        "human_review": pending_human_review(probe),
    }


def _self_memory_artifact_file_inventory(
    artifact_root: Path,
) -> list[dict[str, Any]]:
    """Inventory the learning tree plus isolated probe trees without rewriting bytes."""

    entries: list[dict[str, Any]] = []
    for path in sorted(artifact_root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(
                f"benchmark artifact roots must not contain symlinks: {path}"
            )
        if not path.is_file():
            continue
        if path.name == "run_manifest.json":
            continue
        if path.suffix.casefold() != ".json":
            raise RuntimeError(f"unexpected non-JSON benchmark artifact: {path}")

        relative = path.relative_to(artifact_root).as_posix()
        parts = Path(relative).parts
        valid_learning = (
            len(parts) >= 3
            and parts[0] == "learning"
            and parts[1] in {"events", "interactions"}
        )
        valid_probe = (
            len(parts) >= 4
            and parts[0] == "probes"
            and parts[2] in {"events", "interactions"}
        )
        if not (valid_learning or valid_probe):
            raise RuntimeError(
                f"unexpected self-memory benchmark artifact layout: {relative}"
            )

        raw = path.read_bytes()
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid JSON benchmark artifact: {path}") from exc
        if not isinstance(document, dict):
            raise RuntimeError(f"benchmark artifact is not a JSON object: {path}")

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


def _manifest(
    *,
    benchmark_id: str,
    corpus: PersonFidelityCorpus,
    revision: str,
    captured_at: datetime,
    result_path: Path,
    artifact_root: Path,
    results: list[dict[str, Any]],
    learning_task_ids: list[UUID],
) -> dict[str, Any]:
    files = _self_memory_artifact_file_inventory(artifact_root)
    type_counts = Counter(str(item["artifact_type"]) for item in files)
    return {
        "schema_version": 1,
        "artifact_type": "SELF_MEMORY_PERSON_FIDELITY_RUN_MANIFEST",
        "benchmark_id": benchmark_id,
        "source_fixture_id": corpus.benchmark_id,
        "source_fixture_version": corpus.benchmark_version,
        "fixture_sha256": corpus.fixture_sha256,
        "captured_at": captured_at.isoformat(),
        "revision": revision,
        "privacy_classification": "PUBLIC_SYNTHETIC_FIXTURE",
        "retention_policy": "PERMANENT_APPEND_ONLY",
        "training_status": "UNREVIEWED_RAW_EVIDENCE",
        "result_artifact": _display_path(result_path),
        "artifact_root": _display_path(artifact_root),
        "learning_task_ids": [str(value) for value in learning_task_ids],
        "probe_interaction_ids": {
            item["probe_id"]: item["interaction_id"] for item in results
        },
        "file_count": len(files),
        "total_bytes": sum(int(item["size_bytes"]) for item in files),
        "artifact_type_counts": dict(sorted(type_counts.items())),
        "files": files,
    }


def _validation_summary(corpus: PersonFidelityCorpus) -> dict[str, Any]:
    return {
        "benchmark_id": _benchmark_id(corpus),
        "source_fixture_id": corpus.benchmark_id,
        "source_fixture_version": corpus.benchmark_version,
        "fixture_sha256": corpus.fixture_sha256,
        "fictional_subject": corpus.subject.name,
        "life_event_count": len(corpus.life_events),
        "probe_count": len(corpus.probes),
        "valid": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--probe-id", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    corpus = load_person_fidelity_corpus(
        HOLDOUT_CORPUS
        if args.holdout and args.corpus == DEFAULT_CORPUS
        else args.corpus
    )
    if args.holdout and corpus.benchmark_id != HOLDOUT_BENCHMARK_ID:
        raise SystemExit("--holdout requires the frozen holdout fixture")
    if args.validate_only:
        print(json.dumps(_validation_summary(corpus), indent=2, sort_keys=True))
        return

    selected = [
        probe for probe in corpus.probes
        if not args.probe_id or probe.probe_id in set(args.probe_id)
    ]
    unknown = set(args.probe_id) - {probe.probe_id for probe in corpus.probes}
    if unknown:
        raise SystemExit(f"unknown probe IDs: {sorted(unknown)}")
    if not selected:
        raise SystemExit("no probes selected")

    load_dotenv(ROOT / ".env", override=False)
    database_url = os.environ.get(DATABASE_ENV, "").strip()
    if not database_url:
        raise SystemExit(
            f"Set {DATABASE_ENV} to a dedicated resettable PostgreSQL database "
            "whose name contains 'benchmark'."
        )
    os.environ["DATABASE_URL"] = database_url

    resource_preflight = _resource_preflight()
    print(
        "[preflight] "
        f"ollama={resource_preflight['ollama_residency']} "
        f"safe_ram={resource_preflight['safe_available_mib']}MiB "
        f"required={resource_preflight['required_incremental_mib']}MiB",
        flush=True,
    )
    if args.preflight_only:
        print(json.dumps(resource_preflight, indent=2, sort_keys=True))
        return
    _require_resource_preflight(resource_preflight)

    captured_at = datetime.now(timezone.utc)
    run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")
    revision = _require_clean_revision()
    benchmark_id = _benchmark_id(corpus)
    artifact_root = (
        args.artifact_root
        or GENERATED_DIR / benchmark_id.casefold() / run_id
    ).resolve()
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise SystemExit(f"artifact root must be empty: {artifact_root}")
    output = (
        args.output
        or RESULT_DIR / f"{benchmark_id}_{captured_at.strftime('%Y-%m-%d_%H%M%S')}.json"
    )
    if output.exists():
        raise SystemExit(f"result artifact already exists: {output}")

    from prometheist import db
    from prometheist.ollama_runtime import (
        configured_ollama_base_url,
        configured_ollama_model,
    )

    with db.get_connection() as conn:
        database_name = _apply_schema_and_require_benchmark_database(conn)
        _reset_database(conn)
        learning_root = artifact_root / "learning"
        print("[learning] building self memory through production consolidation", flush=True)
        learned_event_ids, learning_task_ids = _learn_self_memory(
            conn,
            corpus,
            run_id=run_id,
            learning_root=learning_root,
        )
        snapshot = _snapshot_self_memory(conn)
        learning = _learning_summary(conn, corpus, learned_event_ids)
        learning["snapshot_sha256"] = _snapshot_digest(snapshot)
        print(
            f"  representations={learning['representation_count']} "
            f"statuses={learning['status_counts']}",
            flush=True,
        )

        results = []
        for index, probe in enumerate(selected, start=1):
            print(
                f"[{index}/{len(selected)}] {probe.probe_id} "
                f"({probe.dimension.value})",
                flush=True,
            )
            result = _run_probe(
                conn,
                corpus,
                probe,
                run_id=run_id,
                run_artifact_root=artifact_root,
                snapshot=snapshot,
            )
            results.append(result)
            print(
                "  structural="
                + ("PASS" if result["structural_evidence"]["passed"] else "FAIL")
                + (
                    " self="
                    f"{len(result['response_realization']['activated_self_representation_ids'])}"
                ),
                flush=True,
            )

    structural_passes = sum(
        bool(item["structural_evidence"]["passed"]) for item in results
    )
    manifest_path = artifact_root / "run_manifest.json"
    manifest = _manifest(
        benchmark_id=benchmark_id,
        corpus=corpus,
        revision=revision,
        captured_at=captured_at,
        result_path=output,
        artifact_root=artifact_root,
        results=results,
        learning_task_ids=learning_task_ids,
    )
    _write_result(manifest_path, manifest)
    manifest_receipt = {
        "status": "CAPTURED_AND_INVENTORIED",
        "path": _display_path(manifest_path),
        "sha256": _sha256_file(manifest_path),
        "size_bytes": manifest_path.stat().st_size,
        "raw_artifact_root": _display_path(artifact_root),
        "raw_artifact_file_count": manifest["file_count"],
        "raw_artifact_total_bytes": manifest["total_bytes"],
        "privacy_classification": manifest["privacy_classification"],
        "retention_policy": manifest["retention_policy"],
        "training_status": manifest["training_status"],
    }
    payload = {
        "schema_version": 1,
        "benchmark_id": benchmark_id,
        "source_fixture_id": corpus.benchmark_id,
        "source_fixture_version": corpus.benchmark_version,
        "benchmark_status": "EXPERIMENTAL_SELF_MEMORY_V1",
        "fixture_sha256": corpus.fixture_sha256,
        "captured_at": captured_at.isoformat(),
        "revision": revision,
        "runner": "benchmarks/run_self_memory_person_fidelity.py",
        "environment": {
            "database_name": database_name,
            "platform": platform.platform(),
            "python": sys.version,
            "ollama_base_url": configured_ollama_base_url(),
            "configured_model": configured_ollama_model(),
            "resource_preflight": resource_preflight,
            "ollama_keep_alive": os.environ.get(
                "PROMETHEIST_OLLAMA_KEEP_ALIVE"
            ),
            "artifact_root": str(artifact_root),
        },
        "learning": learning,
        "result": (
            "PENDING_HUMAN_REVIEW"
            if structural_passes == len(results)
            else "STRUCTURAL_FAILURES_AND_PENDING_HUMAN_REVIEW"
        ),
        "claim_boundary": (
            "This experiment establishes only whether production self-learning "
            "formed provenance-grounded representations and whether those "
            "representations improved evidence delivery. Human review is required "
            "for person-fidelity conclusions."
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

    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    print(f"\nResult artifact: {output}")
    print(f"Raw artifact manifest: {manifest_path}")
    print("HUMAN REVIEW REQUIRED: score every response using the frozen fixture oracle.")


if __name__ == "__main__":
    main()
