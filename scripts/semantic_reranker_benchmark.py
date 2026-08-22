"""Benchmark a local Qwen3 reranker without co-resident AI models.

The benchmark intentionally uses two sequential phases:
1. Qwen3-Embedding in Ollama generates a bounded candidate set, then is unloaded.
2. Qwen3-Reranker runs alone under llama.cpp and reranks those candidates.

Qwen3 rerankers are causal-LM yes/no judges. This script therefore uses Qwen's
published prompt contract and scores the constrained yes/no next-token
probabilities through llama.cpp's /completion endpoint. It does NOT use
llama.cpp's generic /v1/rerank endpoint, which is designed around rank-pooling
models and has produced incorrect scores for Qwen3-style causal rerankers.

Example (PowerShell):
    uv run python scripts/semantic_reranker_benchmark.py `
        --embedding-model qwen3-embedding:4b-q4_K_M `
        --embedding-dimensions 1536 `
        --reranker-hf QuantFactory/Qwen3-Reranker-4B-GGUF:Q4_K_M
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
CORPORA = (
    ROOT / "benchmarks" / "jordan_vale_v1.json",
    ROOT / "benchmarks" / "avery_chen_v1.json",
    ROOT / "benchmarks" / "morgan_reyes_v05_robustness.json",
    ROOT / "benchmarks" / "semantic_retrieval_v1.json",
)
DEFAULT_EMBED_MODEL = "qwen3-embedding:4b-q4_K_M"
DEFAULT_EMBED_DIMENSIONS = 1536
DEFAULT_RERANKER = "QuantFactory/Qwen3-Reranker-4B-GGUF:Q4_K_M"
DEFAULT_INSTRUCTION = (
    "Given an internal memory request, retrieve persisted events that contain "
    "evidence needed to satisfy the request."
)
RERANK_SYSTEM = (
    "Judge whether the Document meets the requirements based on the Query and "
    "the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."
)


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


def host_memory() -> dict[str, int | None]:
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


def gib(value: int | None) -> str:
    return "n/a" if value is None else f"{value / (1024 ** 3):.2f} GiB"


def post(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def running_ollama_models(client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get("/api/ps")
    response.raise_for_status()
    return list(response.json().get("models", []))


def unload_ollama_model(client: httpx.Client, model: str) -> None:
    try:
        post(client, "/api/generate", {"model": model, "keep_alive": 0, "stream": False})
    except httpx.HTTPStatusError:
        post(client, "/api/embed", {"model": model, "input": "", "keep_alive": 0})


def unload_all_ollama(client: httpx.Client) -> None:
    for item in running_ollama_models(client):
        name = str(item.get("name") or item.get("model") or "").strip()
        if name:
            print(f"  unloading Ollama model: {name}")
            unload_ollama_model(client, name)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not running_ollama_models(client):
            return
        time.sleep(0.25)
    raise RuntimeError("Ollama still has a model resident after unload request")


def load_corpora() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for path in CORPORA:
        payload = json.loads(path.read_text(encoding="utf-8"))
        namespace = path.stem
        for event in payload["events"]:
            documents.append(
                {
                    "id": f"{namespace}:{event['event_id']}",
                    "corpus": namespace,
                    "text": str(event["text"]),
                }
            )
        for question in payload["questions"]:
            q = dict(question)
            q["id"] = f"{namespace}:{q['id']}"
            q["corpus"] = namespace
            q["relevant_event_ids"] = [
                f"{namespace}:{value}" for value in q.get("relevant_event_ids", [])
            ]
            q["required_event_ids"] = [
                f"{namespace}:{value}" for value in q.get("required_event_ids", [])
            ]
            questions.append(q)
    return documents, questions


def embed_many(
    client: httpx.Client,
    model: str,
    texts: list[str],
    dimensions: int,
    *,
    batch_size: int = 8,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        body = post(
            client,
            "/api/embed",
            {
                "model": model,
                "input": batch,
                "dimensions": dimensions,
                "truncate": False,
                "keep_alive": "10m",
            },
        )
        chunk = body.get("embeddings") or []
        if len(chunk) != len(batch):
            raise RuntimeError("Ollama returned the wrong number of embeddings")
        vectors.extend(chunk)
    return vectors


def dot(left: list[float], right: list[float]) -> float:
    return math.fsum(a * b for a, b in zip(left, right, strict=True))


def build_candidates(
    documents: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    *,
    model: str,
    dimensions: int,
    candidate_limit: int,
    ollama_url: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int | None]]:
    with httpx.Client(base_url=ollama_url, timeout=120.0) as client:
        unload_all_ollama(client)
        mem_before = host_memory()
        print(f"Embedding phase: {model}, {dimensions} dimensions")
        started = time.perf_counter()
        doc_vectors = embed_many(client, model, [d["text"] for d in documents], dimensions)
        formatted_queries = [
            f"Instruct: {DEFAULT_INSTRUCTION}\nQuery:{q['query']}" for q in questions
        ]
        query_vectors = embed_many(client, model, formatted_queries, dimensions)
        elapsed = time.perf_counter() - started
        mem_loaded = host_memory()
        print(
            f"  generated {len(documents)} document + {len(questions)} query embeddings "
            f"in {elapsed:.2f}s; available RAM={gib(mem_loaded['available_physical_bytes'])}"
        )

        result: dict[str, list[dict[str, Any]]] = {}
        for q, qv in zip(questions, query_vectors, strict=True):
            scored = [
                {"event_id": d["id"], "text": d["text"], "similarity": dot(qv, dv)}
                for d, dv in zip(documents, doc_vectors, strict=True)
            ]
            scored.sort(key=lambda row: (-row["similarity"], row["event_id"]))
            result[q["id"]] = scored[:candidate_limit]

        unload_ollama_model(client, model)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and running_ollama_models(client):
            time.sleep(0.25)
        if running_ollama_models(client):
            raise RuntimeError("Embedding model remained resident; refusing to load reranker")
        print("  embedding model unloaded; Ollama has no resident models")
        return result, {
            "available_before_embedding": mem_before["available_physical_bytes"],
            "available_during_embedding": mem_loaded["available_physical_bytes"],
            "available_after_embedding": host_memory()["available_physical_bytes"],
        }


def qwen_prompt(query: str, document: str, instruction: str) -> str:
    return (
        f"<|im_start|>system\n{RERANK_SYSTEM}<|im_end|>\n"
        "<|im_start|>user\n"
        f"<Instruct>: {instruction}\n\n<Query>: {query}\n\n<Document>: {document}"
        "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def _yes_probability(body: dict[str, Any]) -> float:
    rows = body.get("completion_probabilities") or body.get("probs") or []
    if not rows:
        raise RuntimeError(f"llama.cpp returned no token probabilities: {body.keys()}")
    first = rows[0]
    options = first.get("top_probs") or first.get("top_logprobs") or first.get("probs") or []
    values: dict[str, float] = {}
    for item in options:
        token = str(item.get("token") or item.get("tok_str") or "").strip().lower()
        if token not in {"yes", "no"}:
            continue
        if "prob" in item:
            values[token] = float(item["prob"])
        elif "logprob" in item:
            values[token] = math.exp(float(item["logprob"]))
    if set(values) != {"yes", "no"}:
        raise RuntimeError(f"Expected constrained yes/no probabilities, got: {options}")
    total = values["yes"] + values["no"]
    return values["yes"] / total if total else 0.0


def rerank_score(client: httpx.Client, query: str, document: str) -> tuple[float, float]:
    started = time.perf_counter()
    body = post(
        client,
        "/completion",
        {
            "prompt": qwen_prompt(query, document, DEFAULT_INSTRUCTION),
            "n_predict": 1,
            "temperature": 1.0,
            "top_k": 0,
            "top_p": 1.0,
            "min_p": 0.0,
            "n_probs": 2,
            "post_sampling_probs": True,
            "grammar": 'root ::= "yes" | "no"',
            "cache_prompt": False,
        },
    )
    return _yes_probability(body), time.perf_counter() - started


def wait_for_server(client: httpx.Client, process: subprocess.Popen[str], timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited early with code {process.returncode}")
        try:
            response = client.get("/health")
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("llama-server did not become healthy")


def embedding_rank(question: dict[str, Any], candidates: list[dict[str, Any]]) -> int | None:
    required = set(question.get("required_event_ids") or question.get("relevant_event_ids") or [])
    for rank, row in enumerate(candidates, start=1):
        if row["event_id"] in required:
            return rank
    return None


def choose_questions(
    questions: list[dict[str, Any]],
    candidates: dict[str, list[dict[str, Any]]],
    mode: str,
) -> list[dict[str, Any]]:
    if mode == "all":
        return questions
    if mode == "semantic":
        return [q for q in questions if q["corpus"] == "semantic_retrieval_v1"]

    selected: list[dict[str, Any]] = []
    for q in questions:
        if q.get("expect_no_evidence"):
            selected.append(q)
            continue
        rank = embedding_rank(q, candidates[q["id"]])
        if rank is not None and rank > 1:
            selected.append(q)
            continue
        if q["id"] in {"semantic_retrieval_v1:sq02", "semantic_retrieval_v1:sq03"}:
            selected.append(q)
    return selected


def evaluate(question_rows: list[dict[str, Any]]) -> dict[str, Any]:
    known = [row for row in question_rows if not row["expect_no_evidence"]]
    unknown = [row for row in question_rows if row["expect_no_evidence"]]
    emb_ranks = [row["embedding_required_rank"] for row in known if row["embedding_required_rank"]]
    rerank_ranks = [row["reranker_required_rank"] for row in known if row["reranker_required_rank"]]
    return {
        "known_questions": len(known),
        "unknown_questions": len(unknown),
        "embedding_recall_at_1": sum(rank == 1 for rank in emb_ranks) / len(known) if known else None,
        "reranker_recall_at_1": sum(rank == 1 for rank in rerank_ranks) / len(known) if known else None,
        "embedding_mrr": statistics.fmean(1 / rank for rank in emb_ranks) if emb_ranks else None,
        "reranker_mrr": statistics.fmean(1 / rank for rank in rerank_ranks) if rerank_ranks else None,
        "unknown_max_reranker_score": max((row["top_reranker_score"] for row in unknown), default=None),
        "known_min_best_required_reranker_score": min(
            (row["best_required_reranker_score"] for row in known if row["best_required_reranker_score"] is not None),
            default=None,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--embedding-dimensions", type=int, default=DEFAULT_EMBED_DIMENSIONS)
    parser.add_argument("--reranker-hf", default=DEFAULT_RERANKER)
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument("--question-mode", choices=("hard", "semantic", "all"), default="hard")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()

    server_exe = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if not server_exe:
        raise SystemExit(
            "llama-server is not on PATH. On Windows install current llama.cpp with: "
            "winget install llama.cpp"
        )

    documents, questions = load_corpora()
    print(f"Loaded {len(documents)} events and {len(questions)} questions.")
    print("Exclusive model mode is ON: embedding and reranker cannot be resident together.\n")

    candidates, embedding_memory = build_candidates(
        documents,
        questions,
        model=args.embedding_model,
        dimensions=args.embedding_dimensions,
        candidate_limit=args.candidate_limit,
        ollama_url=args.ollama_url,
    )
    selected = choose_questions(questions, candidates, args.question_mode)
    print(f"Selected {len(selected)} questions for reranking ({args.question_mode} mode).")

    results_dir = ROOT / "benchmark_results"
    results_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = results_dir / f"llama_reranker_{stamp}.log"
    json_path = results_dir / f"semantic_reranker_{stamp}.json"

    mem_before = host_memory()
    command = [
        server_exe,
        "-hf",
        args.reranker_hf,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--no-webui",
        "-c",
        "4096",
        "-np",
        "1",
    ]
    print(f"\nStarting reranker alone: {args.reranker_hf}")
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=120.0) as client:
            load_started = time.perf_counter()
            wait_for_server(client, process)
            load_seconds = time.perf_counter() - load_started
            mem_loaded = host_memory()
            print(
                f"  server ready in {load_seconds:.2f}s; available RAM="
                f"{gib(mem_loaded['available_physical_bytes'])}"
            )

            positive, positive_wall = rerank_score(
                client,
                "What is the capital of China?",
                "The capital of China is Beijing.",
            )
            negative, negative_wall = rerank_score(
                client,
                "What is the capital of China?",
                "A bicycle has two wheels and uses pedals.",
            )
            print(f"  sanity: positive={positive:.4f}, negative={negative:.4f}")
            if not positive > negative:
                raise RuntimeError(
                    "Reranker sanity check failed. Refusing to benchmark an invalid scoring path."
                )

            question_rows: list[dict[str, Any]] = []
            pair_latencies: list[float] = [positive_wall, negative_wall]
            for index, q in enumerate(selected, start=1):
                rows = []
                for candidate in candidates[q["id"]]:
                    score, wall = rerank_score(client, q["query"], candidate["text"])
                    pair_latencies.append(wall)
                    rows.append({**candidate, "reranker_score": score})
                reranked = sorted(rows, key=lambda row: (-row["reranker_score"], row["event_id"]))
                required = set(q.get("required_event_ids") or q.get("relevant_event_ids") or [])
                reranker_rank = next(
                    (rank for rank, row in enumerate(reranked, start=1) if row["event_id"] in required),
                    None,
                )
                required_scores = [row["reranker_score"] for row in reranked if row["event_id"] in required]
                question_rows.append(
                    {
                        "question_id": q["id"],
                        "query": q["query"],
                        "expect_no_evidence": bool(q.get("expect_no_evidence")),
                        "embedding_required_rank": embedding_rank(q, candidates[q["id"]]),
                        "reranker_required_rank": reranker_rank,
                        "best_required_reranker_score": max(required_scores) if required_scores else None,
                        "top_reranker_score": reranked[0]["reranker_score"],
                        "embedding_candidates": candidates[q["id"]],
                        "reranked_candidates": reranked,
                    }
                )
                print(
                    f"  [{index:02d}/{len(selected):02d}] {q['id']}: "
                    f"embed-rank={question_rows[-1]['embedding_required_rank']} "
                    f"rerank={reranker_rank} top-score={reranked[0]['reranker_score']:.4f}"
                )

            summary = evaluate(question_rows)
            summary["mean_pair_wall_ms"] = 1000 * statistics.fmean(pair_latencies)
            summary["median_pair_wall_ms"] = 1000 * statistics.median(pair_latencies)
            print("\nSUMMARY")
            print(json.dumps(summary, indent=2))

            payload = {
                "benchmark": "prometheist-semantic-reranker-v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "host": {
                    "platform": platform.platform(),
                    "logical_cpu_count": __import__("os").cpu_count(),
                    "memory_before_reranker": mem_before,
                    "memory_during_reranker": mem_loaded,
                    "embedding_memory": embedding_memory,
                },
                "embedding_model": args.embedding_model,
                "embedding_dimensions": args.embedding_dimensions,
                "reranker_hf": args.reranker_hf,
                "candidate_limit": args.candidate_limit,
                "question_mode": args.question_mode,
                "reranker_load_wall_seconds": load_seconds,
                "sanity": {"positive": positive, "negative": negative},
                "summary": summary,
                "questions": question_rows,
            }
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"\nWrote {json_path}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log_handle.close()
        print(f"Reranker stopped. Server log: {log_path}")


if __name__ == "__main__":
    main()
