"""Compatibility wrapper for the Qwen3 reranker benchmark.

Qwen3-Reranker defines relevance from the pairwise logits of the complete
single-token answers ``yes`` and ``no``. llama.cpp's ``n_probs`` response only
returns top-N probabilities, and grammar-constrained sampling can expose token
prefixes/variants while omitting one complete target token.

This wrapper resolves the model's exact token IDs for ``yes`` and ``no`` via
llama.cpp's /tokenize endpoint, applies the same large positive logit bias to
both IDs, requests post-sampling probabilities, and then renormalizes only the
two target-token probabilities. Equal additive bias preserves their pairwise
softmax ratio exactly while forcing both tokens into the returned window.
"""
from __future__ import annotations

import math
import time
from typing import Any

import httpx

import semantic_reranker_benchmark as benchmark


PROBABILITY_WINDOW = 8
TARGET_LOGIT_BIAS = 80.0
_TARGET_IDS: dict[str, int] | None = None


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


benchmark.rerank_score = rerank_score


if __name__ == "__main__":
    benchmark.main()
