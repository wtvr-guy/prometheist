"""Benchmark the known-good Voodisss Qwen3 reranker via llama.cpp /v1/rerank.

This is the final reranker viability probe for Prometheist v0.6. It deliberately
avoids generative yes/no logprob extraction. The Voodisss GGUF was converted
with llama.cpp's official reranker path and includes rank-pooling classifier
metadata/tensors, so llama.cpp can score it natively through /v1/rerank.

The script reuses cached 1536-dimension instructed embedding candidates when
available, preserving the exclusive-model policy and avoiding repeated Ollama
work during reranker debugging.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import time
from typing import Any

import httpx

import semantic_reranker_benchmark as benchmark
import semantic_reranker_benchmark_safe as cached


DEFAULT_RERANKER = "Voodisss/Qwen3-Reranker-4B-GGUF-llama_cpp:Q4_K_M"


def native_rerank(
    client: httpx.Client,
    query: str,
    documents: list[str],
) -> tuple[list[float], float]:
    started = time.perf_counter()
    body = benchmark.post(
        client,
        "/v1/rerank",
        {
            "query": query,
            "documents": documents,
            "top_n": len(documents),
        },
    )
    wall = time.perf_counter() - started
    results = body.get("results") or []
    if len(results) != len(documents):
        raise RuntimeError(
            f"Expected {len(documents)} rerank results, received {len(results)}: {body}"
        )
    scores: list[float | None] = [None] * len(documents)
    for row in results:
        index = int(row["index"])
        if index < 0 or index >= len(documents):
            raise RuntimeError(f"Invalid rerank result index {index}: {row}")
        scores[index] = float(row["relevance_score"])
    if any(score is None for score in scores):
        raise RuntimeError(f"Rerank response omitted document scores: {body}")
    return [float(score) for score in scores], wall


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-model", default=benchmark.DEFAULT_EMBED_MODEL)
    parser.add_argument("--embedding-dimensions", type=int, default=benchmark.DEFAULT_EMBED_DIMENSIONS)
    parser.add_argument("--reranker-hf", default=DEFAULT_RERANKER)
    parser.add_argument("--candidate-limit", type=int, default=5)
    parser.add_argument("--question-mode", choices=("hard", "semantic", "all"), default="hard")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()

    server_exe = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if not server_exe:
        raise SystemExit("llama-server is not on PATH")

    documents, questions = benchmark.load_corpora()
    print(f"Loaded {len(documents)} events and {len(questions)} questions.")
    print("Exclusive model mode is ON: embedding and reranker cannot be resident together.\n")

    candidates, embedding_memory = cached.build_candidates_cached(
        documents,
        questions,
        model=args.embedding_model,
        dimensions=args.embedding_dimensions,
        candidate_limit=args.candidate_limit,
        ollama_url=args.ollama_url,
    )
    selected = benchmark.choose_questions(questions, candidates, args.question_mode)
    print(f"Selected {len(selected)} questions for reranking ({args.question_mode} mode).")

    results_dir = benchmark.ROOT / "benchmark_results"
    results_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = results_dir / f"llama_native_reranker_{stamp}.log"
    json_path = results_dir / f"semantic_native_reranker_{stamp}.json"

    mem_before = benchmark.host_memory()
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
        "--reranking",
        "--pooling",
        "rank",
        "--embedding",
    ]
    print(f"\nStarting native reranker alone: {args.reranker_hf}")
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=180.0) as client:
            load_started = time.perf_counter()
            benchmark.wait_for_server(client, process)
            load_seconds = time.perf_counter() - load_started
            mem_loaded = benchmark.host_memory()
            print(
                f"  server ready in {load_seconds:.2f}s; available RAM="
                f"{benchmark.gib(mem_loaded['available_physical_bytes'])}"
            )

            sanity_scores, sanity_wall = native_rerank(
                client,
                "What is the capital of China?",
                [
                    "The capital of China is Beijing.",
                    "A bicycle has two wheels and uses pedals.",
                ],
            )
            positive, negative = sanity_scores
            print(f"  sanity: positive={positive:.6f}, negative={negative:.6f}")
            if not positive > negative:
                raise RuntimeError(
                    "Native reranker sanity check failed: relevant document did not outrank irrelevant document"
                )
            if positive <= 1e-6 and negative <= 1e-6:
                raise RuntimeError(
                    "Native reranker returned near-zero garbage scores; GGUF/runtime path is not viable"
                )

            question_rows: list[dict[str, Any]] = []
            batch_latencies: list[float] = [sanity_wall]
            effective_pair_latencies: list[float] = [sanity_wall / 2]

            for index, q in enumerate(selected, start=1):
                source_rows = candidates[q["id"]]
                scores, wall = native_rerank(
                    client,
                    q["query"],
                    [row["text"] for row in source_rows],
                )
                batch_latencies.append(wall)
                effective_pair_latencies.append(wall / len(source_rows))
                rows = [
                    {**candidate, "reranker_score": score}
                    for candidate, score in zip(source_rows, scores, strict=True)
                ]
                reranked = sorted(rows, key=lambda row: (-row["reranker_score"], row["event_id"]))
                required = set(q.get("required_event_ids") or q.get("relevant_event_ids") or [])
                reranker_rank = next(
                    (rank for rank, row in enumerate(reranked, start=1) if row["event_id"] in required),
                    None,
                )
                required_scores = [
                    row["reranker_score"] for row in reranked if row["event_id"] in required
                ]
                record = {
                    "question_id": q["id"],
                    "query": q["query"],
                    "expect_no_evidence": bool(q.get("expect_no_evidence")),
                    "embedding_required_rank": benchmark.embedding_rank(q, source_rows),
                    "reranker_required_rank": reranker_rank,
                    "best_required_reranker_score": max(required_scores) if required_scores else None,
                    "top_reranker_score": reranked[0]["reranker_score"],
                    "rerank_batch_wall_ms": wall * 1000,
                    "embedding_candidates": source_rows,
                    "reranked_candidates": reranked,
                }
                question_rows.append(record)
                print(
                    f"  [{index:02d}/{len(selected):02d}] {q['id']}: "
                    f"embed-rank={record['embedding_required_rank']} "
                    f"rerank={reranker_rank} top-score={record['top_reranker_score']:.6f} "
                    f"batch={record['rerank_batch_wall_ms']:.0f}ms"
                )

            summary = benchmark.evaluate(question_rows)
            summary["mean_rerank_batch_wall_ms"] = 1000 * statistics.fmean(batch_latencies)
            summary["median_rerank_batch_wall_ms"] = 1000 * statistics.median(batch_latencies)
            summary["mean_effective_pair_wall_ms"] = 1000 * statistics.fmean(effective_pair_latencies)
            summary["median_effective_pair_wall_ms"] = 1000 * statistics.median(effective_pair_latencies)

            print("\nSUMMARY")
            print(json.dumps(summary, indent=2))

            payload = {
                "benchmark": "prometheist-semantic-native-reranker-v1",
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
