"""Collect target-host evidence for v0.7 environment-calibrated constraints.

This is a measurement harness, not an optimizer. It records host samples,
Ollama latency/output behavior across candidate token caps, and the duration of
the frozen worker/runtime acceptance block. A pilot run remains evidence to
inform calibration; it does not automatically rewrite production policy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any

import httpx

from jit_agent.attention_observation import ResourceSafetyPolicy, SystemHostResourceProbe

ROOT = Path(__file__).resolve().parents[1]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def measure_resources(samples: int) -> dict[str, Any]:
    probe = SystemHostResourceProbe()
    captured = [probe.capture() for _ in range(samples)]
    policy = ResourceSafetyPolicy()
    return {
        "benchmark_id": "RES-NATIVE-001",
        "result": "PILOT_NATIVE_MEASUREMENT",
        "sample_count": samples,
        "policy_under_measurement": policy.model_dump(mode="json"),
        "platforms": sorted({item.platform for item in captured}),
        "logical_cpu_counts": sorted({item.logical_cpu_count for item in captured}),
        "cpu_utilization_percent": _summary(
            [float(item.cpu_utilization_percent) for item in captured]
        ),
        "memory_total_mib": sorted({item.memory_total_mib for item in captured}),
        "memory_available_mib": _summary(
            [float(item.memory_available_mib) for item in captured]
        ),
        "raw_samples": [item.model_dump(mode="json") for item in captured],
        "decision": (
            "Pilot observations establish actual target-host pressure ranges. Repeat under the "
            "idle, CPU-pressure, memory-pressure, cold-model, and warm-model scenarios before "
            "changing or verifying admission margins."
        ),
    }


def measure_ollama(token_caps: tuple[int, ...]) -> dict[str, Any]:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    system = "Return valid JSON matching the schema. Preserve the requested literal exactly."
    literal = "VX-NATIVE-CALIBRATION-7F31A9"
    user = (
        "Return an answer that contains this exact literal and briefly states that this is a "
        f"native calibration probe: {literal}"
    )
    observations: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url, timeout=300.0, trust_env=False) as client:
        for cap in token_caps:
            started = time.monotonic()
            error: str | None = None
            content = ""
            body: dict[str, Any] = {}
            try:
                response = client.post(
                    "/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "format": schema,
                        "think": False,
                        "stream": False,
                        "options": {"num_predict": cap, "temperature": 0},
                    },
                )
                response.raise_for_status()
                body = response.json()
                content = str(body.get("message", {}).get("content", ""))
            except Exception as exc:  # measurement must preserve explicit failure evidence
                error = f"{type(exc).__name__}: {exc}"
            elapsed = time.monotonic() - started
            observations.append(
                {
                    "num_predict": cap,
                    "elapsed_seconds": round(elapsed, 6),
                    "http_or_parse_error": error,
                    "content_length": len(content),
                    "literal_preserved": literal in content,
                    "done_reason": body.get("done_reason"),
                    "prompt_eval_count": body.get("prompt_eval_count"),
                    "eval_count": body.get("eval_count"),
                }
            )
    return {
        "benchmark_id": "LLM-NATIVE-001",
        "result": "PILOT_NATIVE_MEASUREMENT",
        "base_url": base_url,
        "model": model,
        "token_caps": list(token_caps),
        "observations": observations,
        "decision": (
            "This pilot identifies truncation/latency behavior for a controlled structured call. "
            "Repeat cold/warm/contention and production-schema scenarios before verifying HTTP, "
            "token, or retry bounds."
        ),
    }


def measure_worker_runtime() -> dict[str, Any]:
    command = [
        "uv",
        "run",
        "--locked",
        "pytest",
        "-q",
        "tests/test_v07_increment_h.py",
        "tests/test_worker_protocol.py::test_forced_process_loss_recovers_same_step_from_postgres",
        "tests/test_cli.py",
        "tests/test_interaction_runtime.py",
    ]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    return {
        "benchmark_id": "WORKER-NATIVE-001",
        "result": "PILOT_NATIVE_MEASUREMENT",
        "elapsed_seconds": round(elapsed, 6),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "decision": (
            "One frozen runtime-block duration is a pilot only. Lease/timeout/retry verification "
            "requires repeated normal, slow, killed, spawn-failure, and resource-denial trials."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-samples", type=int, default=20)
    parser.add_argument(
        "--token-caps",
        default="16,24,32,48,64,128,256,512",
        help="comma-separated Ollama num_predict candidates",
    )
    parser.add_argument("--skip-resources", action="store_true")
    parser.add_argument("--skip-ollama", action="store_true")
    parser.add_argument("--skip-worker", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.resource_samples < 1:
        raise SystemExit("--resource-samples must be positive")
    token_caps = tuple(int(value) for value in args.token_caps.split(",") if value.strip())
    if not token_caps or any(value < 1 for value in token_caps):
        raise SystemExit("--token-caps must contain positive integers")

    results: dict[str, Any] = {}
    if not args.skip_resources:
        results["RES-NATIVE-001"] = measure_resources(args.resource_samples)
    if not args.skip_worker:
        results["WORKER-NATIVE-001"] = measure_worker_runtime()
    if not args.skip_ollama:
        results["LLM-NATIVE-001"] = measure_ollama(token_caps)

    payload = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "runner": "benchmarks/native_constraint_calibration.py",
        "results": results,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
