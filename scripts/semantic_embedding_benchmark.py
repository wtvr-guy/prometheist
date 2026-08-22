"""Benchmark local embedding models for Prometheist semantic memory.

This runner is intentionally independent of pgvector. It measures whether an
embedding model/quantization/dimension is worth integrating before database
plumbing can affect the result.

Safety policy for small machines:
- exactly one Ollama model is allowed to remain loaded during a model run;
- any already-loaded Ollama models are explicitly unloaded first;
- the benchmarked model is explicitly unloaded before the next model starts;
- no generation model or reranker is loaded alongside the embedding model.

Example:
    uv run python scripts/semantic_embedding_benchmark.py \
        --models qwen3-embedding:4b-q4_K_M \
        --dimensions 512 1024 1536 2560
"""
from __future__ import annotations

import argparse
import csv
import ctypes
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Iterable

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPORA = (
    ROOT / "benchmarks" / "jordan_vale_v1.json",
    ROOT / "benchmarks" / "avery_chen_v1.json",
    ROOT / "benchmarks" / "morgan_reyes_v05_robustness.json",
    ROOT / "benchmarks" / "semantic_retrieval_v1.json",
)
DEFAULT_MODEL = "qwen3-embedding:4b-q4_K_M"
DEFAULT_DIMENSIONS = (512, 1024, 1536, 2560)
DEFAULT_INSTRUCTION = (
    "Given an internal memory request, retrieve persisted events that contain "
    "evidence needed to satisfy the request."
)
TOP_KS = (1, 3, 5, 10)


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _host_memory() -> dict[str, int | None]:
    if sys.platform != "win32":
        return {"total_physical_bytes": None, "available_physical_bytes": None}
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"total_physical_bytes": None, "available_physical_bytes": None}
    return {
        "total_physical_bytes": int(status.ullTotalPhys),
        "available_physical_bytes": int(status.ullAvailPhys),
    }


def _gib(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) / (1024 ** 3):.2f} GiB"


def _seconds(ns: int | float | None) -> float:
    return float(ns or 0) / 1_000_000_000.0


def _percent(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def _mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def _median(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.median(values) if values else None


def _dot(left: list[float], right: list[float]) -> float:
    return math.fsum(a * b for a, b in zip(left, right, strict=True))


def _api_get(client: httpx.Client, path: str) -> dict[str, Any]:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def _api_post(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def _running_models(client: httpx.Client) -> list[dict[str, Any]]:
    return list(_api_get(client, "/api/ps").get("models", []))


def _installed_model_names(client: httpx.Client) -> set[str]:
    models = _api_get(client, "/api/tags").get("models", [])
    names: set[str] = set()
    for model in models:
        for key in ("name", "model"):
            value = model.get(key)
            if value:
                names.add(str(value))
    return names


def _show_model(client: httpx.Client, model: str) -> dict[str, Any]:
    return _api_post(client, "/api/show", {"model": model})


def _embedding_dimension(show: dict[str, Any]) -> int | None:
    info = show.get("model_info") or {}
    for key, value in info.items():
        if str(key).endswith(".embedding_length"):
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return None


def _unload_model(client: httpx.Client, model: str) -> None:
    # Ollama documents /api/generate with keep_alive=0 as the generic unload
    # mechanism. Embedding-only models can reject generation, so fall back to
    # the embedding endpoint, which also accepts keep_alive.
    try:
        _api_post(client, "/api/generate", {"model": model, "keep_alive": 0, "stream": False})
    except httpx.HTTPStatusError:
        _api_post(
            client,
            "/api/embed",
            {"model": model, "input": "", "keep_alive": 0},
        )


def _wait_unloaded(client: httpx.Client, model: str | None = None, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        loaded = _running_models(client)
        if model is None and not loaded:
            return
        if model is not None and all(item.get("name") != model and item.get("model") != model for item in loaded):
            return
        time.sleep(0.25)
    names = [item.get("name") or item.get("model") for item in _running_models(client)]
    raise RuntimeError(f"Ollama model unload timed out; still loaded: {names}")


def _unload_everything(client: httpx.Client) -> None:
    loaded = _running_models(client)
    for item in loaded:
        name = str(item.get("name") or item.get("model") or "").strip()
        if name:
            print(f"  unloading pre-existing model: {name}")
            _unload_model(client, name)
    _wait_unloaded(client)


def _pull_model(client: httpx.Client, model: str) -> None:
    print(f"  pulling missing model: {model}")
    response = client.post(
        "/api/pull",
        json={"model": model, "stream": False},
        timeout=None,
    )
    response.raise_for_status()


def _embed(
    client: httpx.Client,
    *,
    model: str,
    inputs: list[str],
    dimensions: int,
    keep_alive: str | int,
) -> tuple[list[list[float]], dict[str, Any], float]:
    started = time.perf_counter()
    body = _api_post(
        client,
        "/api/embed",
        {
            "model": model,
            "input": inputs,
            "dimensions": dimensions,
            "truncate": False,
            "keep_alive": keep_alive,
        },
    )
    wall = time.perf_counter() - started
    vectors = body.get("embeddings") or []
    if len(vectors) != len(inputs):
        raise RuntimeError(
            f"Expected {len(inputs)} embeddings from {model}, received {len(vectors)}"
        )
    if vectors and len(vectors[0]) != dimensions:
        raise RuntimeError(
            f"Requested {dimensions} dimensions from {model}, received {len(vectors[0])}"
        )
    return vectors, body, wall


def _batched(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _embed_many(
    client: httpx.Client,
    *,
    model: str,
    texts: list[str],
    dimensions: int,
    batch_size: int,
    keep_alive: str,
) -> tuple[list[list[float]], dict[str, Any]]:
    vectors: list[list[float]] = []
    total_wall = 0.0
    total_api = 0.0
    total_load = 0.0
    total_tokens = 0
    calls = 0
    for batch in _batched(texts, batch_size):
        batch_vectors, body, wall = _embed(
            client,
            model=model,
            inputs=batch,
            dimensions=dimensions,
            keep_alive=keep_alive,
        )
        vectors.extend(batch_vectors)
        total_wall += wall
        total_api += _seconds(body.get("total_duration"))
        total_load += _seconds(body.get("load_duration"))
        total_tokens += int(body.get("prompt_eval_count") or 0)
        calls += 1
    return vectors, {
        "calls": calls,
        "wall_seconds": total_wall,
        "api_total_seconds": total_api,
        "api_load_seconds": total_load,
        "prompt_eval_count": total_tokens,
    }


def _load_corpora(paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "events" not in payload or "questions" not in payload:
            raise ValueError(f"Benchmark corpus lacks events/questions: {path}")
        namespace = path.stem
        for event in payload["events"]:
            event_id = f"{namespace}:{event['event_id']}"
            documents.append(
                {
                    "id": event_id,
                    "corpus": namespace,
                    "text": str(event["text"]),
                    "event_type": event.get("event_type"),
                }
            )
        for question in payload["questions"]:
            question = dict(question)
            question["id"] = f"{namespace}:{question['id']}"
            question["corpus"] = namespace
            question["relevant_event_ids"] = [
                f"{namespace}:{value}" for value in question.get("relevant_event_ids", [])
            ]
            question["required_event_ids"] = [
                f"{namespace}:{value}" for value in question.get("required_event_ids", [])
            ]
            questions.append(question)
    return documents, questions


def _format_query(query: str, instruction: str, instructed: bool) -> str:
    if not instructed:
        return query
    # Qwen3 Embedding's documented retrieval format applies an instruction only
    # to query embeddings; retrieval documents remain unmodified.
    return f"Instruct: {instruction}\nQuery:{query}"


def _evaluate(
    documents: list[dict[str, Any]],
    doc_vectors: list[list[float]],
    questions: list[dict[str, Any]],
    query_vectors: list[list[float]],
) -> dict[str, Any]:
    doc_ids = [document["id"] for document in documents]
    known_rows: list[dict[str, Any]] = []
    unknown_rows: list[dict[str, Any]] = []
    per_question: list[dict[str, Any]] = []

    for question, query_vector in zip(questions, query_vectors, strict=True):
        scored = [
            (doc_id, _dot(query_vector, doc_vector))
            for doc_id, doc_vector in zip(doc_ids, doc_vectors, strict=True)
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))
        rank_by_id = {doc_id: rank for rank, (doc_id, _) in enumerate(scored, start=1)}
        score_by_id = dict(scored)
        top_id, top_score = scored[0]

        expect_none = bool(question.get("expect_no_evidence"))
        required_ids = list(question.get("required_event_ids") or question.get("relevant_event_ids") or [])
        relevant_ids = list(question.get("relevant_event_ids") or required_ids)
        row: dict[str, Any] = {
            "question_id": question["id"],
            "corpus": question["corpus"],
            "query": question["query"],
            "expect_no_evidence": expect_none,
            "top_event_id": top_id,
            "top_similarity": top_score,
            "top5": [
                {"event_id": doc_id, "similarity": score}
                for doc_id, score in scored[:5]
            ],
        }

        if expect_none:
            unknown_rows.append(row)
        else:
            required_ranks = [rank_by_id[value] for value in required_ids if value in rank_by_id]
            relevant_ranks = [rank_by_id[value] for value in relevant_ids if value in rank_by_id]
            required_scores = [score_by_id[value] for value in required_ids if value in score_by_id]
            row.update(
                {
                    "best_required_rank": min(required_ranks) if required_ranks else None,
                    "worst_required_rank": max(required_ranks) if required_ranks else None,
                    "best_relevant_rank": min(relevant_ranks) if relevant_ranks else None,
                    "best_required_similarity": max(required_scores) if required_scores else None,
                }
            )
            known_rows.append(row)
        per_question.append(row)

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"known_questions": 0}
        best_ranks = [int(row["best_required_rank"]) for row in rows if row.get("best_required_rank")]
        worst_ranks = [int(row["worst_required_rank"]) for row in rows if row.get("worst_required_rank")]
        required_scores = [
            float(row["best_required_similarity"])
            for row in rows
            if row.get("best_required_similarity") is not None
        ]
        summary: dict[str, Any] = {
            "known_questions": len(rows),
            "mrr_required": _mean(1.0 / rank for rank in best_ranks),
            "median_best_required_rank": _median(float(rank) for rank in best_ranks),
            "median_best_required_similarity": _median(required_scores),
            "min_best_required_similarity": min(required_scores) if required_scores else None,
        }
        for k in TOP_KS:
            summary[f"required_any_recall_at_{k}"] = _mean(
                1.0 if row.get("best_required_rank") and row["best_required_rank"] <= k else 0.0
                for row in rows
            )
            summary[f"required_all_recall_at_{k}"] = _mean(
                1.0 if row.get("worst_required_rank") and row["worst_required_rank"] <= k else 0.0
                for row in rows
            )
        return summary

    overall = summarize(known_rows)
    unknown_scores = [float(row["top_similarity"]) for row in unknown_rows]
    overall.update(
        {
            "unknown_questions": len(unknown_rows),
            "unknown_top1_similarity_max": max(unknown_scores) if unknown_scores else None,
            "unknown_top1_similarity_median": _median(unknown_scores),
        }
    )
    known_floor = overall.get("min_best_required_similarity")
    unknown_ceiling = overall.get("unknown_top1_similarity_max")
    overall["raw_similarity_separation_margin"] = (
        float(known_floor) - float(unknown_ceiling)
        if known_floor is not None and unknown_ceiling is not None
        else None
    )

    by_corpus: dict[str, Any] = {}
    for corpus in sorted({question["corpus"] for question in questions}):
        corpus_known = [row for row in known_rows if row["corpus"] == corpus]
        corpus_unknown = [row for row in unknown_rows if row["corpus"] == corpus]
        corpus_summary = summarize(corpus_known)
        scores = [float(row["top_similarity"]) for row in corpus_unknown]
        corpus_summary.update(
            {
                "unknown_questions": len(corpus_unknown),
                "unknown_top1_similarity_max": max(scores) if scores else None,
            }
        )
        by_corpus[corpus] = corpus_summary

    return {"summary": overall, "by_corpus": by_corpus, "questions": per_question}


def _ps_entry(client: httpx.Client, model: str) -> dict[str, Any] | None:
    for item in _running_models(client):
        if item.get("name") == model or item.get("model") == model:
            return item
    return None


def _print_run_summary(run: dict[str, Any]) -> None:
    summary = run["quality"]["summary"]
    print(
        f"    mode={run['query_mode']:<10} "
        f"R@1={_percent(summary['required_any_recall_at_1'])} "
        f"R@5={_percent(summary['required_any_recall_at_5'])} "
        f"MRR={summary['mrr_required']:.3f} "
        f"unknown-max={summary['unknown_top1_similarity_max']!s}"
    )


def _benchmark_model(
    client: httpx.Client,
    *,
    model: str,
    dimensions: list[int],
    documents: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    instruction: str,
    batch_size: int,
    keep_alive: str,
) -> dict[str, Any]:
    print(f"\nMODEL {model}")
    _unload_everything(client)
    before_memory = _host_memory()
    show = _show_model(client, model)
    max_dimension = _embedding_dimension(show)
    if max_dimension is not None:
        dimensions = [value for value in dimensions if value <= max_dimension]
    if not dimensions:
        raise ValueError(f"No requested dimensions are supported by {model}; max={max_dimension}")

    # Cold start is measured separately. The model remains resident for all
    # dimensions of this one model, then is explicitly removed before switching.
    _, cold_body, cold_wall = _embed(
        client,
        model=model,
        inputs=["Prometheist semantic benchmark warmup"],
        dimensions=dimensions[0],
        keep_alive=keep_alive,
    )
    loaded = _running_models(client)
    if len(loaded) != 1 or _ps_entry(client, model) is None:
        names = [item.get("name") or item.get("model") for item in loaded]
        raise RuntimeError(
            f"Exclusive model invariant violated after loading {model}; resident={names}"
        )
    resident = _ps_entry(client, model) or {}
    after_load_memory = _host_memory()
    print(
        f"  cold load: {cold_wall:.2f}s wall / {_seconds(cold_body.get('load_duration')):.2f}s Ollama load; "
        f"resident={_gib(resident.get('size'))}, VRAM={_gib(resident.get('size_vram'))}"
    )

    model_result: dict[str, Any] = {
        "model": model,
        "details": show.get("details", {}),
        "capabilities": show.get("capabilities", []),
        "max_embedding_dimension": max_dimension,
        "cold_start": {
            "wall_seconds": cold_wall,
            "ollama_load_seconds": _seconds(cold_body.get("load_duration")),
            "ollama_total_seconds": _seconds(cold_body.get("total_duration")),
        },
        "resident": {
            "size_bytes": resident.get("size"),
            "size_vram_bytes": resident.get("size_vram"),
            "context_length": resident.get("context_length"),
        },
        "host_memory_before_load": before_memory,
        "host_memory_after_load": after_load_memory,
        "runs": [],
    }

    document_texts = [document["text"] for document in documents]
    raw_queries = [str(question["query"]) for question in questions]

    try:
        for dimension in dimensions:
            print(f"  DIMENSIONS {dimension}")
            doc_vectors, doc_perf = _embed_many(
                client,
                model=model,
                texts=document_texts,
                dimensions=dimension,
                batch_size=batch_size,
                keep_alive=keep_alive,
            )
            print(
                f"    documents: {len(documents)} in {doc_perf['wall_seconds']:.2f}s "
                f"({doc_perf['prompt_eval_count']} input tokens)"
            )

            for instructed in (True, False):
                mode = "instructed" if instructed else "plain"
                query_texts = [
                    _format_query(query, instruction, instructed)
                    for query in raw_queries
                ]
                query_vectors, query_perf = _embed_many(
                    client,
                    model=model,
                    texts=query_texts,
                    dimensions=dimension,
                    batch_size=batch_size,
                    keep_alive=keep_alive,
                )
                quality = _evaluate(documents, doc_vectors, questions, query_vectors)
                run = {
                    "dimensions": dimension,
                    "query_mode": mode,
                    "instruction": instruction if instructed else None,
                    "document_embedding": doc_perf,
                    "query_embedding": query_perf,
                    "average_query_embedding_wall_ms": (
                        1000.0 * query_perf["wall_seconds"] / len(questions)
                        if questions
                        else None
                    ),
                    "quality": quality,
                }
                model_result["runs"].append(run)
                _print_run_summary(run)
    finally:
        unload_started = time.perf_counter()
        _unload_model(client, model)
        _wait_unloaded(client, model)
        model_result["unload_wall_seconds"] = time.perf_counter() - unload_started
        model_result["host_memory_after_unload"] = _host_memory()
        remaining = _running_models(client)
        if remaining:
            raise RuntimeError(
                "Exclusive model invariant violated after unload; resident="
                + str([item.get("name") or item.get("model") for item in remaining])
            )
        print(f"  unloaded {model} ({model_result['unload_wall_seconds']:.2f}s)")

    return model_result


def _write_results(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"semantic_embedding_{stamp}.json"
    csv_path = output_dir / f"semantic_embedding_{stamp}.csv"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    rows: list[dict[str, Any]] = []
    for model in result["models"]:
        for run in model["runs"]:
            summary = run["quality"]["summary"]
            rows.append(
                {
                    "model": model["model"],
                    "quantization": model.get("details", {}).get("quantization_level"),
                    "dimensions": run["dimensions"],
                    "query_mode": run["query_mode"],
                    "required_any_recall_at_1": summary.get("required_any_recall_at_1"),
                    "required_any_recall_at_3": summary.get("required_any_recall_at_3"),
                    "required_any_recall_at_5": summary.get("required_any_recall_at_5"),
                    "required_any_recall_at_10": summary.get("required_any_recall_at_10"),
                    "required_all_recall_at_5": summary.get("required_all_recall_at_5"),
                    "mrr_required": summary.get("mrr_required"),
                    "unknown_top1_similarity_max": summary.get("unknown_top1_similarity_max"),
                    "raw_similarity_separation_margin": summary.get("raw_similarity_separation_margin"),
                    "average_query_embedding_wall_ms": run.get("average_query_embedding_wall_ms"),
                    "document_embedding_wall_seconds": run["document_embedding"].get("wall_seconds"),
                    "resident_size_bytes": model["resident"].get("size_bytes"),
                    "resident_size_vram_bytes": model["resident"].get("size_vram_bytes"),
                    "cold_start_wall_seconds": model["cold_start"].get("wall_seconds"),
                }
            )
    fieldnames = list(rows[0]) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local embedding models one-at-a-time through Ollama."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[DEFAULT_MODEL],
        help="Ollama embedding model tags. Models are loaded and unloaded sequentially.",
    )
    parser.add_argument(
        "--dimensions",
        nargs="+",
        type=int,
        default=list(DEFAULT_DIMENSIONS),
        help="MRL output dimensions to test; values above a model's maximum are skipped.",
    )
    parser.add_argument(
        "--corpora",
        nargs="+",
        type=Path,
        default=list(DEFAULT_CORPORA),
        help="Benchmark JSON files with events and questions.",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--keep-alive", default="10m")
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    parser.add_argument(
        "--ollama-base-url",
        default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "benchmark_results",
    )
    parser.add_argument(
        "--pull-missing",
        action="store_true",
        help="Download missing model tags before benchmarking them.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")
    if any(value < 32 for value in args.dimensions):
        raise SystemExit("Qwen3 MRL dimensions must be >= 32")

    corpora = [path.resolve() for path in args.corpora]
    documents, questions = _load_corpora(corpora)
    print(
        f"Loaded {len(documents)} events and {len(questions)} questions from "
        f"{len(corpora)} corpora."
    )
    print("Exclusive Ollama mode is ON: no two models will remain loaded together.")

    base_url = args.ollama_base_url.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=300.0) as client:
        try:
            _api_get(client, "/api/tags")
        except Exception as exc:
            raise SystemExit(f"Ollama is not reachable at {base_url}: {exc}") from exc

        installed = _installed_model_names(client)
        for model in args.models:
            if model not in installed:
                if args.pull_missing:
                    _pull_model(client, model)
                    installed = _installed_model_names(client)
                else:
                    raise SystemExit(
                        f"Model {model!r} is not installed. Run `ollama pull {model}` "
                        "or add --pull-missing."
                    )

        result: dict[str, Any] = {
            "benchmark": "prometheist-semantic-embedding-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "host": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "processor": platform.processor(),
                "logical_cpu_count": os.cpu_count(),
                **_host_memory(),
            },
            "ollama_base_url": base_url,
            "corpora": [str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path) for path in corpora],
            "event_count": len(documents),
            "question_count": len(questions),
            "models": [],
        }

        try:
            for model in args.models:
                model_result = _benchmark_model(
                    client,
                    model=model,
                    dimensions=sorted(set(args.dimensions)),
                    documents=documents,
                    questions=questions,
                    instruction=args.instruction,
                    batch_size=args.batch_size,
                    keep_alive=args.keep_alive,
                )
                result["models"].append(model_result)
        finally:
            # Best-effort cleanup even after an exception. This is intentionally
            # aggressive because the benchmark is for memory-constrained hosts.
            try:
                _unload_everything(client)
            except Exception as exc:
                print(f"WARNING: final Ollama cleanup failed: {exc}", file=sys.stderr)

    json_path, csv_path = _write_results(result, args.output_dir)
    print("\nBenchmark complete.")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")


if __name__ == "__main__":
    main()
