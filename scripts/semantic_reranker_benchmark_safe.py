"""Compatibility wrapper for the Qwen3 reranker benchmark.

llama.cpp grammars operate on token text prefixes, so the grammar
``root ::= "yes" | "no"`` can admit tokens such as ``y`` or ``n`` in addition
to the complete Qwen3 reranker answer tokens ``yes`` and ``no``.  The original
benchmark requested only the top two post-sampling probabilities, which can
therefore omit one complete answer token even when the scoring path is valid.

This wrapper preserves the benchmark and model-residency behavior unchanged,
but requests a wider grammar-filtered probability window and then performs the
Qwen-recommended binary normalization over the complete ``yes`` and ``no``
tokens only.
"""
from __future__ import annotations

import math
import time
from typing import Any

import httpx

import semantic_reranker_benchmark as benchmark


PROBABILITY_WINDOW = 32


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
                "token": item.get("token") or item.get("tok_str"),
                "prob": item.get("prob"),
                "logprob": item.get("logprob"),
            }
            for item in options
        ]
        raise RuntimeError(
            "Qwen reranker scoring requires complete yes/no token probabilities; "
            f"missing={sorted(missing)} from grammar-filtered top-{PROBABILITY_WINDOW}: {compact}"
        )

    # Qwen3-Reranker defines relevance as softmax over the logits of the
    # single-token answers yes and no.  llama.cpp has already softmaxed the
    # grammar-valid logits; renormalizing just these two probabilities preserves
    # their exact pairwise ratio while ignoring prefix tokens such as y/n.
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
            "post_sampling_probs": True,
            "grammar": 'root ::= "yes" | "no"',
            "cache_prompt": False,
        },
    )
    return _yes_probability(body), time.perf_counter() - started


benchmark._yes_probability = _yes_probability
benchmark.rerank_score = rerank_score


if __name__ == "__main__":
    benchmark.main()
