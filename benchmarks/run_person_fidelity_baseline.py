"""Run the frozen public person-fidelity baseline on the native v2 pipeline.

This runner intentionally resets a dedicated benchmark database before every
probe.  No probe can inherit another probe's prompt or response, and every model
invocation still travels through the production fresh-worker pipeline.

The JSON result separates structural provenance checks from pending human review.
It never treats phrase matching as evidence that Prometheist resembles a person.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from jit_agent.person_fidelity_benchmark import (
    BENCHMARK_ID,
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
RESULT_DIR = ROOT / "benchmarks" / "results"
GENERATED_DIR = ROOT / "benchmarks" / "generated" / "person_fidelity"
DATABASE_ENV = "PROMETHEIST_PERSON_FIDELITY_DATABASE_URL"


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
        if not (
            line.startswith("?? benchmarks/results/PERSON-FIDELITY-001_")
            and line.endswith(".json")
        )
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
    with path.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate the frozen fixture without PostgreSQL or Ollama",
    )
    args = parser.parse_args()
    corpus = load_person_fidelity_corpus(args.corpus)
    if args.validate_only:
        print(json.dumps(_validation_summary(corpus), indent=2, sort_keys=True))
        return

    database_url = os.environ.get(DATABASE_ENV, "").strip()
    if not database_url:
        raise SystemExit(
            f"{DATABASE_ENV} is required and must select a dedicated resettable "
            "PostgreSQL database whose name contains 'benchmark'."
        )
    os.environ["DATABASE_URL"] = database_url

    captured_at = datetime.now(timezone.utc)
    run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")
    revision = _require_clean_revision()
    run_artifact_root = (args.artifact_root or GENERATED_DIR / run_id).resolve()
    if run_artifact_root.exists() and any(run_artifact_root.iterdir()):
        raise SystemExit(f"artifact root must be empty: {run_artifact_root}")

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
    payload = {
        "schema_version": 1,
        "benchmark_id": BENCHMARK_ID,
        "benchmark_version": corpus.benchmark_version,
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
        "probes": results,
    }
    output = args.output or RESULT_DIR / f"{BENCHMARK_ID}_{run_id}.json"
    _write_result(output, payload)

    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    print(f"\nResult artifact: {output}")
    print("HUMAN REVIEW REQUIRED: score every response using the embedded oracle.")


if __name__ == "__main__":
    main()
