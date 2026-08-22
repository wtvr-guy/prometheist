"""Compatibility wrapper for the Qwen3 reranker benchmark.

Qwen3-Reranker defines relevance from the pairwise logits of the complete
single-token answers ``yes`` and ``no``. llama.cpp's ``n_probs`` response only
returns the top-N tokens, and grammar-constrained sampling can still expose
prefix/variant tokens (``y``, ``No``, ``false``...) while omitting one of the
complete target tokens.

This wrapper avoids that ambiguity by applying the same large positive
``logit_bias`` to the exact token strings ``yes`` and ``no``. Adding the same
constant to both target logits preserves their pairwise softmax ratio exactly,
while forcing both tokens into a small returned probability window. The final
score is then renormalized over only ``yes`` and ``no``, matching Qwen's
published scoring rule.
"""
from __future__ import annotations

import math
import time
from typing import Any

import httpx

import semantic_reranker_benchmark as benchmark


PROBABILITY_WINDOW = 8
TARGET_LOGIT_BIAS = 80.0


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
            f"missing={sorted(missing)} after equal target logit bias: {compact}"
        )

    # Equal additive bias cancels exactly in the pairwise softmax:
    # exp(y+B)/(exp(y+B)+exp(n+B)) == exp(y)/(exp(y)+exp(n)).
    total = values["yes"] + values["no"]
    if total <= 0:
        raise RuntimeError(f"Invalid yes/no probability mass: {values}")
    return values["yes"] / total


def rerank_score(client: httpx.Client, query: str, document: str) -> tuple[float, float]:
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
            "post_sampling_probs": False,
            "logit_bias": [["yes", TARGET_LOGIT_BIAS], ["no", TARGET_LOGIT_BIAS]],
            "cache_prompt": False,
        },
    )
    return _yes_probability(body), time.perf_counter() - started


benchmark._yes_probability = _yes_probability
benchmark.rerank_score = rerank_score


if __name__ == "__main__":
    benchmark.main()
