"""MEM-ADAPT-007: model-capacity crossover over frozen Composer v2.

This experiment freezes the adaptive retrieval controller and relevance-constrained
Evidence Composer v2 from MEM-ADAPT-006, then varies only the disposable local
response model. Each run tests exactly one model so Ollama never needs to keep two
large model targets resident for the comparison.

The benchmark is destructive and refuses any database whose name does not contain
``test`` or ``benchmark``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from time import perf_counter
import runpy

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app@localhost:5432/jit_agent_test",
)

from jit_agent import db
from jit_agent.attention_observation import SystemHostResourceProbe
from jit_agent.llm import OllamaClient
from jit_agent.native_policy import (
    MINISTRAL_3_8B_INSTRUCT_MODEL,
    QWEN3_4B_INSTRUCT_MODEL,
    native_resource_safety_policy,
)
from jit_agent.ollama_runtime import OllamaRuntimeProbe


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "benchmarks" / "results"
BASE = runpy.run_path(
    str(ROOT / "benchmarks" / "compare_memory_composition_cognition.py"),
    run_name="mem_adapt_007_base",
)

_prepare_database = BASE["_prepare_database"]
_duplicate_pressure_case = BASE["_duplicate_pressure_case"]
_correction_pair_case = BASE["_correction_pair_case"]
_distributed_clues_case = BASE["_distributed_clues_case"]
_numeric_core_case = BASE["_numeric_core_case"]
_novelty_bait_case = BASE["_novelty_bait_case"]
_stale_retained_case = BASE["_stale_retained_case"]
_association_bridge_case = BASE["_association_bridge_case"]
_abstention_case = BASE["_abstention_case"]
_retrieve_shared_pool = BASE["_retrieve_shared_pool"]
_packet_variants = BASE["_packet_variants"]
_normalize_answer = BASE["_normalize_answer"]
_required_ranks = BASE["_required_ranks"]

PACKET_LIMIT = BASE["PACKET_LIMIT"]
QUICK_DISTRACTORS = BASE["QUICK_DISTRACTORS"]
STRESS_DISTRACTORS = BASE["STRESS_DISTRACTORS"]
QUICK_POOL_LIMIT = BASE["QUICK_POOL_LIMIT"]
STRESS_POOL_LIMIT = BASE["STRESS_POOL_LIMIT"]
DEFAULT_MODEL = MINISTRAL_3_8B_INSTRUCT_MODEL
CONTROL_MODEL = QWEN3_4B_INSTRUCT_MODEL


def _safe_launch_preflight(model: str) -> dict[str, object]:
    """Fail closed unless current CPU/RAM pressure admits this model target.

    This mirrors the native host-safety arithmetic for a no-reservation benchmark
    process. Warm verified model residency receives the same ordinary-worker RAM
    credit used by the guarded interaction path; cold or unverified residency uses
    the full model-specific native cold-load estimate.
    """

    policy = native_resource_safety_policy(model=model)
    metrics = SystemHostResourceProbe().capture()
    runtime = OllamaRuntimeProbe(model=model).capture()
    required_memory_mib = runtime.incremental_process_memory_mib(policy)

    cpu_pressure = metrics.cpu_utilization_percent
    if metrics.load_1m is not None:
        cpu_pressure = max(
            cpu_pressure,
            min(100, round(metrics.load_1m * 100 / metrics.logical_cpu_count)),
        )
    idle_cpu_units = math.floor(
        metrics.logical_cpu_count * (100 - cpu_pressure) / 100
    )
    if cpu_pressure >= policy.max_cpu_pressure_percent:
        idle_cpu_units = 0
    raw_cpu = max(
        0,
        idle_cpu_units - policy.cpu_system_headroom_units(metrics.logical_cpu_count),
    )
    cpu_uncertainty = math.ceil(raw_cpu * policy.uncertainty_headroom_percent / 100)
    safe_cpu_units = max(0, raw_cpu - cpu_uncertainty)

    memory_headroom_mib = policy.memory_system_headroom_mib(metrics.memory_total_mib)
    raw_memory_mib = max(0, metrics.memory_available_mib - memory_headroom_mib)
    memory_uncertainty_mib = math.ceil(
        raw_memory_mib * policy.uncertainty_headroom_percent / 100
    )
    safe_memory_mib = max(0, raw_memory_mib - memory_uncertainty_mib)

    if safe_cpu_units < policy.default_process_cpu_units:
        raise RuntimeError(
            "MEM-ADAPT-007 resource gate denied model launch: "
            f"safe_cpu_units={safe_cpu_units} required_cpu_units="
            f"{policy.default_process_cpu_units} cpu_pressure_percent={cpu_pressure}"
        )
    if safe_memory_mib < required_memory_mib:
        raise RuntimeError(
            "MEM-ADAPT-007 resource gate denied model launch: "
            f"safe_memory_mib={safe_memory_mib} required_memory_mib={required_memory_mib} "
            f"available_memory_mib={metrics.memory_available_mib} "
            f"model={model} residency={runtime.residency_label}"
        )

    return {
        "policy_version": policy.policy_version,
        "model": model,
        "resident": runtime.resident,
        "residency_label": runtime.residency_label,
        "probe_ok": runtime.probe_ok,
        "cold_memory_budget_mib": policy.default_llm_process_memory_mib,
        "required_incremental_memory_mib": required_memory_mib,
        "host_memory_total_mib": metrics.memory_total_mib,
        "host_memory_available_mib": metrics.memory_available_mib,
        "safe_memory_for_new_work_mib": safe_memory_mib,
        "cpu_pressure_percent": cpu_pressure,
        "safe_cpu_units": safe_cpu_units,
        "llm_concurrency_limit": policy.llm_concurrency_limit,
    }


def _expected_atoms(expected_answer: str) -> tuple[str, ...]:
    return tuple(
        part.strip().strip("<>\"'")
        for part in expected_answer.split("|")
        if part.strip().strip("<>\"'")
    )


def _contains_atom(answer: str, atom: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9]){re.escape(atom)}(?![A-Za-z0-9])"
    return re.search(pattern, answer, flags=re.IGNORECASE) is not None


def _answer_value_complete(answer: str, expected_answer: str) -> bool:
    atoms = _expected_atoms(expected_answer)
    return bool(atoms) and all(_contains_atom(answer, atom) for atom in atoms)


def _evaluate_case(client: OllamaClient, scenario, pool) -> dict[str, object]:
    required_ids = tuple(scenario.corpus.required_event_ids)
    retained_ids = {item.source_event_id for item in scenario.retained}
    pool_ids = {item.source_event_id for item in pool.items}
    available = set(required_ids).issubset(pool_ids | retained_ids)

    packet = _packet_variants(
        pool,
        retained=scenario.retained,
    )["relevance_coverage_v2"]
    surfaced_ids = {item.source_event_id for item in packet.items}
    evidence_complete = set(required_ids).issubset(surfaced_ids)

    answer = ""
    error: str | None = None
    started = perf_counter()
    try:
        answer = client.respond(scenario.question, packet)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = round((perf_counter() - started) * 1000.0, 3)

    exact = error is None and (
        _normalize_answer(answer) == _normalize_answer(scenario.expected_answer)
    )
    value_complete = error is None and _answer_value_complete(
        answer,
        scenario.expected_answer,
    )
    format_only_failure = value_complete and not exact

    if not available:
        failure_layer = "retrieval_or_retention"
    elif not evidence_complete:
        failure_layer = "composition"
    elif error is not None:
        failure_layer = "model_runtime"
    elif not value_complete:
        failure_layer = "reasoning"
    elif not exact:
        failure_layer = "instruction_format"
    else:
        failure_layer = "success"

    return {
        "scenario_id": scenario.scenario_id,
        "purpose": scenario.purpose,
        "question": scenario.question,
        "retrieval_query": scenario.retrieval_query,
        "expected_answer": scenario.expected_answer,
        "required_event_ids": [str(value) for value in required_ids],
        "required_pool_ranks": _required_ranks(pool, required_ids),
        "required_available_to_composer": available,
        "shared_pool_item_count": len(pool.items),
        "packet_event_ids": [str(item.source_event_id) for item in packet.items],
        "packet_item_count": len(packet.items),
        "evidence_complete": evidence_complete,
        "answer": answer,
        "answer_value_complete": value_complete,
        "answer_exact": exact,
        "format_only_failure": format_only_failure,
        "elapsed_ms": elapsed_ms,
        "error": error,
        "failure_layer": failure_layer,
        "adaptive_policy": pool.retrieval_trace.get("adaptive_policy"),
    }


def _summary(cases: list[dict[str, object]]) -> dict[str, object]:
    return {
        "cases": len(cases),
        "evidence_complete": sum(bool(case["evidence_complete"]) for case in cases),
        "answer_value_complete": sum(
            bool(case["answer_value_complete"]) for case in cases
        ),
        "answer_exact": sum(bool(case["answer_exact"]) for case in cases),
        "format_only_failures": sum(
            bool(case["format_only_failure"]) for case in cases
        ),
        "reasoning_failures": sum(
            case["failure_layer"] == "reasoning" for case in cases
        ),
        "model_runtime_failures": sum(
            case["failure_layer"] == "model_runtime" for case in cases
        ),
        "composition_failures": sum(
            case["failure_layer"] == "composition" for case in cases
        ),
        "retrieval_or_retention_failures": sum(
            case["failure_layer"] == "retrieval_or_retention" for case in cases
        ),
        "mean_llm_elapsed_ms": round(
            sum(float(case["elapsed_ms"]) for case in cases) / len(cases),
            3,
        ) if cases else 0.0,
    }


def run_comparison(*, model: str, stress: bool) -> dict[str, object]:
    preflight = _safe_launch_preflight(model)
    conn = db.get_connection()
    try:
        database_name = _prepare_database(conn)
        distractors = STRESS_DISTRACTORS if stress else QUICK_DISTRACTORS
        pool_limit = STRESS_POOL_LIMIT if stress else QUICK_POOL_LIMIT
        builders = (
            _duplicate_pressure_case,
            _correction_pair_case,
            _distributed_clues_case,
            _numeric_core_case,
            _novelty_bait_case,
            _stale_retained_case,
            _association_bridge_case,
        )
        client = OllamaClient(model=model)
        cases: list[dict[str, object]] = []
        for builder in builders:
            scenario = builder(conn, distractors)
            pool = _retrieve_shared_pool(conn, scenario, pool_limit=pool_limit)
            cases.append(_evaluate_case(client, scenario, pool))

        abstention = _abstention_case(conn)
        abstention_pool = _retrieve_shared_pool(conn, abstention, pool_limit=pool_limit)
        cases.append(_evaluate_case(client, abstention, abstention_pool))

        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-007",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "model": model,
            "control_model": CONTROL_MODEL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "final_packet_limit": PACKET_LIMIT,
            "shared_pool_limit": pool_limit,
            "distractor_count": distractors,
            "resource_preflight": preflight,
            "stateless_llm_contract": (
                "Every answer is one fresh OllamaClient.respond invocation. The benchmark runs "
                "one model target per process and never carries model context between cases."
            ),
            "frozen_architecture": (
                "MEM-ADAPT-006 adaptive retrieval plus relevance-constrained Evidence Composer v2; "
                "only the disposable response model varies between MEM-ADAPT-007 runs."
            ),
            "evaluation_boundary": (
                "Evidence completeness, required-value correctness, exact instruction-format "
                "correctness, model-runtime failure, and latency are scored independently."
            ),
            "summary": _summary(cases),
            "cases": cases,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = run_comparison(model=args.model, stress=args.stress)
    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.model)
        output = RESULTS_DIR / f"MEM-ADAPT-007_{safe_model}_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "model": result["model"],
                "resource_preflight": result["resource_preflight"],
                "summary": result["summary"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
