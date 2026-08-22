"""Compatibility wrapper for the Qwen3 reranker benchmark.

This wrapper addresses two llama.cpp integration details while preserving the
base benchmark's exclusive-model policy:

1. Qwen3-Reranker scores relevance from the pairwise logits of the complete
   single-token answers ``yes`` and ``no``. We resolve their exact model token
   IDs through /tokenize, apply the same large positive bias to both IDs, request
   post-sampling probabilities, and renormalize only those two probabilities.
   Equal additive bias preserves their pairwise softmax ratio exactly.
2. Repeated reranker-debug runs should not waste ~45-55 seconds regenerating
   embedding candidates. When a compatible semantic_embedding_*.json exists in
   benchmark_results, its instructed top-5 rankings are reused and the Ollama
   embedding phase is skipped. If no compatible cache exists, the original
   embedding path is used unchanged.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Any

import httpx

import semantic_reranker_benchmark as benchmark


PROBABILITY_WINDOW = 8
TARGET_LOGIT_BIAS = 80.0
_TARGET_IDS: dict[str, int] | None = None
_ORIGINAL_BUILD_CANDIDATES = benchmark.build_candidates


def _token_id(client: httpx.Client, text: str) -> int:
    body = benchmark.post(
        client,
        "/tokenize",
        {
            "content": text,
            "add_special": False,
            "parse_special": True,
            "with_pieces": True,
        },
    )
    tokens = body.get("tokens") or []
    if len(tokens) != 1:
        raise RuntimeError(
            f"Qwen reranker answer {text!r} must be a single token; tokenizer returned {tokens}"
        )
    token = tokens[0]
    token_id = token.get("id") if isinstance(token, dict) else token
    try:
        return int(token_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid tokenization result for {text!r}: {tokens}") from exc


def _target_ids(client: httpx.Client) -> dict[str, int]:
    global _TARGET_IDS
    if _TARGET_IDS is None:
        _TARGET_IDS = {"yes": _token_id(client, "yes"), "no": _token_id(client, "no")}
        if _TARGET_IDS["yes"] == _TARGET_IDS["no"]:
            raise RuntimeError(f"yes/no unexpectedly share a token ID: {_TARGET_IDS}")
        print(
            "  reranker answer token IDs: "
            f"yes={_TARGET_IDS['yes']} no={_TARGET_IDS['no']}"
        )
    return _TARGET_IDS


def _yes_probability(body: dict[str, Any], target_ids: dict[str, int]) -> float:
    rows = body.get("completion_probabilities") or body.get("probs") or []
    if not rows:
        raise RuntimeError(f"llama.cpp returned no token probabilities: {body.keys()}")

    first = rows[0]
    options = first.get("top_probs") or first.get("top_logprobs") or first.get("probs") or []
    by_id: dict[int, float] = {}
    for item in options:
        raw_id = item.get("id")
        if raw_id is None:
            continue
        try:
            token_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if "prob" in item and item.get("prob") is not None:
            by_id[token_id] = float(item["prob"])
        elif "logprob" in item and item.get("logprob") is not None:
            by_id[token_id] = math.exp(float(item["logprob"]))

    values = {
        answer: by_id[token_id]
        for answer, token_id in target_ids.items()
        if token_id in by_id
    }
    missing = {"yes", "no"} - set(values)
    if missing:
        compact = [
            {
                "id": item.get("id"),
                "token": item.get("token") or item.get("tok_str"),
                "prob": item.get("prob"),
                "logprob": item.get("logprob"),
            }
            for item in options
        ]
        raise RuntimeError(
            "Qwen reranker scoring requires complete yes/no token probabilities; "
            f"target_ids={target_ids} missing={sorted(missing)} after equal ID bias: {compact}"
        )

    # Equal additive bias cancels exactly in the pairwise softmax:
    # exp(y+B)/(exp(y+B)+exp(n+B)) == exp(y)/(exp(y)+exp(n)).
    total = values["yes"] + values["no"]
    if total <= 0:
        raise RuntimeError(f"Invalid yes/no probability mass: {values}")
    return values["yes"] / total


def rerank_score(client: httpx.Client, query: str, document: str) -> tuple[float, float]:
    target_ids = _target_ids(client)
    started = time.perf_counter()
    body = benchmark.post(
        client,
        "/completion",
        {
            "prompt": benchmark.qwen_prompt(query, document, benchmark.DEFAULT_INSTRUCTION),
            "n_predict": 1,
            "temperature": 1.0,
            "top_k": 0,
            "top_p": 1.0,
            "min_p": 0.0,
            "n_probs": PROBABILITY_WINDOW,
            "post_sampling_probs": True,
            "logit_bias": [
                [target_ids["yes"], TARGET_LOGIT_BIAS],
                [target_ids["no"], TARGET_LOGIT_BIAS],
            ],
            "cache_prompt": False,
        },
    )
    return _yes_probability(body, target_ids), time.perf_counter() - started


def _cached_candidates(
    documents: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    *,
    model: str,
    dimensions: int,
    candidate_limit: int,
) -> tuple[dict[str, list[dict[str, Any]]], Path] | None:
    if candidate_limit > 5:
        return None
    result_dir = benchmark.ROOT / "benchmark_results"
    paths = sorted(result_dir.glob("semantic_embedding_*.json"), reverse=True)
    doc_text = {document["id"]: document["text"] for document in documents}
    expected_questions = {question["id"] for question in questions}

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        model_rows = [row for row in payload.get("models", []) if row.get("model") == model]
        for model_row in model_rows:
            for run in model_row.get("runs", []):
                if run.get("dimensions") != dimensions or run.get("query_mode") != "instructed":
                    continue
                question_rows = run.get("quality", {}).get("questions", [])
                candidates: dict[str, list[dict[str, Any]]] = {}
                valid = True
                for row in question_rows:
                    qid = row.get("question_id")
                    top = row.get("top5") or []
                    if not qid or len(top) < candidate_limit:
                        valid = False
                        break
                    enriched: list[dict[str, Any]] = []
                    for candidate in top[:candidate_limit]:
                        event_id = candidate.get("event_id")
                        if event_id not in doc_text:
                            valid = False
                            break
                        enriched.append(
                            {
                                "event_id": event_id,
                                "text": doc_text[event_id],
                                "similarity": float(candidate["similarity"]),
                            }
                        )
                    if not valid:
                        break
                    candidates[qid] = enriched
                if valid and expected_questions.issubset(candidates):
                    return candidates, path
    return None


def build_candidates_cached(
    documents: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    *,
    model: str,
    dimensions: int,
    candidate_limit: int,
    ollama_url: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    cached = _cached_candidates(
        documents,
        questions,
        model=model,
        dimensions=dimensions,
        candidate_limit=candidate_limit,
    )
    if cached is None:
        return _ORIGINAL_BUILD_CANDIDATES(
            documents,
            questions,
            model=model,
            dimensions=dimensions,
            candidate_limit=candidate_limit,
            ollama_url=ollama_url,
        )

    candidates, path = cached
    with httpx.Client(base_url=ollama_url, timeout=120.0) as client:
        benchmark.unload_all_ollama(client)
    available = benchmark.host_memory()["available_physical_bytes"]
    print(f"Embedding phase: reused cached candidates from {path.name}")
    print("  Ollama has no resident models; skipping embedding model load")
    return candidates, {
        "available_before_embedding": available,
        "available_during_embedding": None,
        "available_after_embedding": available,
        "reused_embedding_results": str(path),
    }


benchmark.rerank_score = rerank_score
benchmark.build_candidates = build_candidates_cached


if __name__ == "__main__":
    benchmark.main()
