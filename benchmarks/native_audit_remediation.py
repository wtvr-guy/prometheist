"""Native evidence added by the first Constitutional Audit remediation.

These scenarios broaden Article 25 evidence without changing policy: one binds
contention accounting to a real host resource snapshot, and one explicitly
measures configured-Ollama cold versus warm startup. The harness fails unless
both requested native scenarios produce evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
import uuid

import httpx

from jit_agent.attention_observation import (
    SystemHostResourceProbe,
    build_resource_observation,
    discover_local_execution_resources,
)
from jit_agent.attention_resources import (
    ExecutionResourceClass,
    ResourceReservation,
    deterministic_reservation_id,
)
from jit_agent.native_policy import native_resource_safety_policy
from jit_agent.ollama_runtime import (
    OllamaRuntimeProbe,
    configured_ollama_base_url,
    configured_ollama_model,
)


def measure_resource_contention() -> dict[str, Any]:
    """Exhaust a real host snapshot's safe scheduler envelope."""
    policy = native_resource_safety_policy()
    probe = SystemHostResourceProbe()
    metrics = probe.capture()
    resources = discover_local_execution_resources(metrics, policy=policy)
    baseline = build_resource_observation(
        scheduler_cycle=1,
        captured_at=datetime.now(timezone.utc),
        resources=resources,
        reservations=[],
        policy=policy,
        metrics=metrics,
        host_id="native-contention",
    )

    task_id = uuid.uuid4()
    reservations: list[ResourceReservation] = []
    reserved_resources: list[str] = []
    for capacity in baseline.capacities:
        if capacity.resource_class not in {
            ExecutionResourceClass.CPU_GENERAL,
            ExecutionResourceClass.MEMORY_RAM,
            ExecutionResourceClass.LLM_INFERENCE,
        }:
            continue
        units = capacity.available_for_new_work
        if units < 1:
            continue
        reservations.append(
            ResourceReservation(
                reservation_id=deterministic_reservation_id(task_id, capacity.resource_id),
                task_id=task_id,
                resource_id=capacity.resource_id,
                resource_class=capacity.resource_class,
                units=units,
            )
        )
        reserved_resources.append(capacity.resource_id)

    post_metrics = probe.capture()
    contended = build_resource_observation(
        scheduler_cycle=2,
        captured_at=datetime.now(timezone.utc),
        resources=resources,
        reservations=reservations,
        policy=policy,
        metrics=metrics,
        host_id="native-contention",
    )
    contended_by_id = contended.capacity_by_resource_id()
    residual = {
        resource_id: contended_by_id[resource_id].available_for_new_work
        for resource_id in reserved_resources
    }
    accepted = bool(reserved_resources) and all(value == 0 for value in residual.values())
    return {
        "benchmark_id": "RES-CONTENTION-001",
        "result": "NATIVE_ACCEPTANCE" if accepted else "NO_NATIVE_EVIDENCE",
        "policy_under_measurement": policy.model_dump(mode="json"),
        "baseline_metrics": metrics.model_dump(mode="json"),
        "post_measurement_metrics": post_metrics.model_dump(mode="json"),
        "baseline_observation": baseline.model_dump(mode="json"),
        "reservations": [item.model_dump(mode="json") for item in reservations],
        "contended_observation": contended.model_dump(mode="json"),
        "residual_new_work_capacity": residual,
        "decision": (
            "Fully reserving the measured safe CPU/RAM/LLM envelope leaves no "
            "capacity for additional work under the same real-host observation; "
            "system headroom remains outside the reservable envelope."
        ),
    }


def _wait_for_residency(
    probe: OllamaRuntimeProbe,
    *,
    resident: bool,
    attempts: int = 40,
    delay_seconds: float = 0.25,
) -> dict[str, Any]:
    last = probe.capture()
    for _ in range(attempts):
        if last.probe_ok and last.resident is resident:
            return {"matched": True, "state": last.model_dump(mode="json")}
        time.sleep(delay_seconds)
        last = probe.capture()
    return {"matched": False, "state": last.model_dump(mode="json")}


def measure_ollama_cold_warm_start() -> dict[str, Any]:
    """Force unload, then record one cold and one warm generation."""
    base_url = configured_ollama_base_url()
    model = configured_ollama_model()
    runtime_probe = OllamaRuntimeProbe(base_url=base_url, model=model)
    observations: dict[str, Any] = {}

    with httpx.Client(base_url=base_url, timeout=300.0, trust_env=False) as client:
        unload_started = time.monotonic()
        unload_error: str | None = None
        try:
            response = client.post(
                "/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
            )
            response.raise_for_status()
        except Exception as exc:
            unload_error = f"{type(exc).__name__}: {exc}"
        observations["unload"] = {
            "elapsed_seconds": round(time.monotonic() - unload_started, 6),
            "error": unload_error,
        }
        nonresident = _wait_for_residency(runtime_probe, resident=False)
        observations["nonresident_before_cold"] = nonresident

        def generate(label: str) -> dict[str, Any]:
            started = time.monotonic()
            error: str | None = None
            body: dict[str, Any] = {}
            try:
                response = client.post(
                    "/api/generate",
                    json={
                        "model": model,
                        "prompt": "Reply with OK.",
                        "stream": False,
                        "think": False,
                        "keep_alive": "5m",
                        "options": {"num_predict": 8, "temperature": 0},
                    },
                )
                response.raise_for_status()
                body = response.json()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            return {
                "label": label,
                "elapsed_seconds": round(time.monotonic() - started, 6),
                "error": error,
                "done": body.get("done"),
                "done_reason": body.get("done_reason"),
                "total_duration_ns": body.get("total_duration"),
                "load_duration_ns": body.get("load_duration"),
                "prompt_eval_duration_ns": body.get("prompt_eval_duration"),
                "eval_duration_ns": body.get("eval_duration"),
            }

        observations["cold"] = generate("cold")
        resident_after_cold = _wait_for_residency(runtime_probe, resident=True)
        observations["resident_after_cold"] = resident_after_cold
        observations["warm"] = generate("warm")

    accepted = (
        unload_error is None
        and bool(nonresident.get("matched"))
        and observations["cold"]["error"] is None
        and bool(resident_after_cold.get("matched"))
        and observations["warm"]["error"] is None
    )
    return {
        "benchmark_id": "OLLAMA-COLD-WARM-001",
        "result": "NATIVE_ACCEPTANCE" if accepted else "NO_NATIVE_EVIDENCE",
        "base_url": base_url,
        "model": model,
        "observations": observations,
        "decision": (
            "The configured model is explicitly unloaded before the cold call and "
            "kept resident for the warm call. Record wall-clock and Ollama-reported "
            "load durations; do not infer a universal timeout from one host/run."
        ),
    }


def evidence_complete(results: dict[str, Any]) -> tuple[bool, list[str]]:
    failures = [
        benchmark_id
        for benchmark_id in ("RES-CONTENTION-001", "OLLAMA-COLD-WARM-001")
        if results.get(benchmark_id, {}).get("result") != "NATIVE_ACCEPTANCE"
    ]
    return not failures, failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-resource-contention", action="store_true")
    parser.add_argument("--skip-cold-warm", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results: dict[str, Any] = {}
    if not args.skip_resource_contention:
        results["RES-CONTENTION-001"] = measure_resource_contention()
    if not args.skip_cold_warm:
        results["OLLAMA-COLD-WARM-001"] = measure_ollama_cold_warm_start()

    complete, failures = evidence_complete(results)
    payload = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "runner": "benchmarks/native_audit_remediation.py",
        "requested_measurements_complete": complete,
        "completion_failures": failures,
        "results": results,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if not complete:
        raise SystemExit("constitutional-audit native remediation evidence is incomplete")


if __name__ == "__main__":
    main()
