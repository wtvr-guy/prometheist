"""MEM-ADAPT-004: adversarial red-team of coverage-aware evidence composition.

This benchmark freezes ``compose_coverage_aware`` exactly as implemented and attacks
its inductive bias directly. It does not involve PostgreSQL retrieval: every case
constructs an explicit retrieval-shaped candidate pool so failures can be attributed
to composition rather than upstream candidate generation, admission, or graph work.

The baseline and experimental composer receive the same ordered candidates and the
same final packet limit. Some cases are intentionally designed so ordinary top-k
*should* be the better policy. A top-k-only success is evidence against the current
composer, not a benchmark defect.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from jit_agent.evidence_composer import CompositionResult, compose_coverage_aware
from jit_agent.models import EventType, MemoryEvidence


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "benchmarks" / "results"
PACKET_LIMIT = 6
_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event_id(index: int) -> uuid.UUID:
    return uuid.UUID(int=index + 1)


def _conversation_id(index: int = 0) -> uuid.UUID:
    return uuid.UUID(int=10_000 + index)


def _evidence(
    index: int,
    content: str,
    *,
    score: float,
    source: str = "memory",
    conversation_index: int = 0,
    event_type: EventType = EventType.USER_PROMPT,
    retrieval_reasons: tuple[str, ...] = ("LEXICAL",),
) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=_event_id(index),
        event_type=event_type,
        source=source,
        created_at=_BASE_TIME,
        conversation_id=_conversation_id(conversation_index),
        conversation_seq=index + 1,
        global_seq=index + 1,
        content=content,
        score=score,
        retrieval_reasons=list(retrieval_reasons),
        provenance_event_ids=[],
    )


def _serialize_composition(result: CompositionResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for decision in result.decisions:
        row = asdict(decision)
        row["source_event_id"] = str(decision.source_event_id)
        row["token_novelty"] = str(decision.token_novelty)
        rows.append(row)
    return rows


def _ids(items) -> tuple[uuid.UUID, ...]:
    return tuple(item.source_event_id for item in items)


def _success(items, required: tuple[uuid.UUID, ...]) -> bool:
    surfaced = set(_ids(items))
    return all(event_id in surfaced for event_id in required)


def _evaluate(
    *,
    scenario_id: str,
    purpose: str,
    candidates: list[MemoryEvidence],
    required: tuple[uuid.UUID, ...],
    retained: tuple[MemoryEvidence, ...] = (),
    designed_to_favor: str,
) -> dict[str, object]:
    current = candidates[:PACKET_LIMIT]
    composed = compose_coverage_aware(candidates, retained=retained, limit=PACKET_LIMIT)
    required_ranks = {
        str(event_id): next(
            (
                index
                for index, item in enumerate(candidates, start=1)
                if item.source_event_id == event_id
            ),
            None,
        )
        for event_id in required
    }
    return {
        "scenario_id": scenario_id,
        "purpose": purpose,
        "designed_to_favor": designed_to_favor,
        "candidate_pool_size": len(candidates),
        "retained_count": len(retained),
        "required_candidate_ranks": required_ranks,
        "top_k": {
            "success": _success(current, required),
            "event_ids": [str(value) for value in _ids(current)],
        },
        "coverage_aware": {
            "success": _success(composed.items, required),
            "event_ids": [str(value) for value in _ids(composed.items)],
            "decisions": _serialize_composition(composed),
        },
    }


def _numeric_fact_blindness(*, bait_count: int) -> dict[str, object]:
    # Numeric-only distinctions are intentionally ignored by the composer's lexical
    # signature. Here those distinctions are the actual payload.
    required_items = [
        _evidence(
            index,
            f"calibration threshold value {10 * (index + 1)}",
            score=1.0 - index * 0.01,
        )
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            (
                "calibration threshold commentary "
                f"zephyr{index} quartz{index} nebula{index} irrelevant{index}"
            ),
            score=0.80 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="numeric_fact_blindness",
        purpose=(
            "Six high-relevance facts differ only in numeric payload; lower-ranked verbose "
            "novelty must not displace those facts merely because numeric-only tokens are ignored."
        ),
        candidates=[*required_items, *bait],
        required=tuple(item.source_event_id for item in required_items),
        designed_to_favor="top_k",
    )


def _corroboration_is_repetition(*, bait_count: int) -> dict[str, object]:
    required_items = [
        _evidence(
            index,
            "independent check confirms reactor seal remained intact",
            score=1.0 - index * 0.01,
        )
        for index in range(4)
    ]
    filler = [
        _evidence(20 + index, "reactor seal routine check", score=0.94 - index * 0.01)
        for index in range(2)
    ]
    bait = [
        _evidence(
            100 + index,
            f"reactor seal peripheral anecdote comet{index} orchard{index} velvet{index}",
            score=0.80 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="corroboration_is_repetition",
        purpose=(
            "Several highly ranked near-identical observations jointly matter because repetition "
            "is corroboration; novelty-heavy lower-ranked evidence should not erase that frequency signal."
        ),
        candidates=[*required_items, *filler, *bait],
        required=tuple(item.source_event_id for item in required_items),
        designed_to_favor="top_k",
    )


def _random_token_novelty_attack(*, bait_count: int) -> dict[str, object]:
    required_items = [
        _evidence(
            index,
            f"deployment approval gate phase {index + 1}",
            score=1.0 - index * 0.01,
        )
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            (
                "deployment approval unrelated payload "
                f"xqzeta{index} prionyx{index} kaldrim{index} vospera{index}"
            ),
            score=0.79 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="random_token_novelty_attack",
        purpose=(
            "Irrelevant lower-ranked memories contain unique token salad intended to game lexical novelty."
        ),
        candidates=[*required_items, *bait],
        required=tuple(item.source_event_id for item in required_items),
        designed_to_favor="top_k",
    )


def _diversity_metadata_attack(*, bait_count: int) -> dict[str, object]:
    required_items = [
        _evidence(
            index,
            f"trusted audit confirms control state {index + 1}",
            score=1.0 - index * 0.01,
            source="trusted-audit",
            conversation_index=0,
        )
        for index in range(PACKET_LIMIT)
    ]
    event_types = (
        EventType.TOOL_RESULT,
        EventType.SYSTEM_EVENT,
        EventType.CAPABILITY_RESULT,
        EventType.AGENT_RESULT,
        EventType.INTERACTION_RESPONSE,
        EventType.ERROR,
    )
    bait = [
        _evidence(
            100 + index,
            "trusted audit unrelated control note",
            score=0.78 - index * 0.001,
            source=f"untrusted-source-{index}",
            conversation_index=index + 1,
            event_type=event_types[index % len(event_types)],
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="diversity_metadata_attack",
        purpose=(
            "Lower-ranked irrelevant evidence is artificially diverse in source, conversation, and event type; "
            "metadata diversity must not outrank six stronger same-source facts."
        ),
        candidates=[*required_items, *bait],
        required=tuple(item.source_event_id for item in required_items),
        designed_to_favor="top_k",
    )


def _stale_retention_poisoning(*, bait_count: int) -> dict[str, object]:
    required_items = [
        _evidence(
            index,
            f"current verified state component alpha item{index}",
            score=1.0 - index * 0.01,
        )
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            f"current verified state low rank filler{index}",
            score=0.60 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    retained = (
        _evidence(
            900,
            "obsolete superseded hypothesis from prior attention round",
            score=0.01,
            source="stale-memory",
        ),
    )
    return _evaluate(
        scenario_id="stale_retention_poisoning",
        purpose=(
            "A stale retained item has very low current relevance. Retention should be a tie preference, "
            "not an unconditional first-slot reservation that forces out one of six current required facts."
        ),
        candidates=[*required_items, *bait],
        required=tuple(item.source_event_id for item in required_items),
        retained=retained,
        designed_to_favor="top_k",
    )


def _verbose_irrelevance_over_concise_truth(*, bait_count: int) -> dict[str, object]:
    required_items = [
        _evidence(
            index,
            f"safety verdict pass {index + 1}",
            score=1.0 - index * 0.01,
        )
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            (
                "safety verdict peripheral narrative "
                f"lavender{index} turbine{index} mosaic{index} peninsula{index} harmonic{index}"
            ),
            score=0.77 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="verbose_irrelevance_over_concise_truth",
        purpose=(
            "Concise high-relevance truths compete against verbose lower-ranked material with more lexical novelty."
        ),
        candidates=[*required_items, *bait],
        required=tuple(item.source_event_id for item in required_items),
        designed_to_favor="top_k",
    )


def _composer_positive_control(*, bait_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(
            index,
            "orbit cedar amber repetitive update",
            score=1.0 - index * 0.01,
        )
        for index in range(PACKET_LIMIT)
    ]
    target = _evidence(
        50,
        "orbit cedar amber decisive exception cobalt",
        score=0.80,
    )
    tail = [
        _evidence(
            100 + index,
            "orbit cedar amber repetitive update",
            score=0.70 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="composer_positive_control",
        purpose=(
            "Control case from the failure family MEM-ADAPT-003 was built to solve: a uniquely informative "
            "lower-ranked memory should beat repetitive top-k crowd-out."
        ),
        candidates=[*repetitive, target, *tail],
        required=(target.source_event_id,),
        designed_to_favor="coverage_aware",
    )


def _shared_success_control() -> dict[str, object]:
    required_items = [
        _evidence(
            index,
            f"distinct required fact token{index}",
            score=1.0 - index * 0.01,
        )
        for index in range(3)
    ]
    tail = [
        _evidence(
            20 + index,
            "distinct required fact routine filler",
            score=0.50 - index * 0.01,
        )
        for index in range(3)
    ]
    return _evaluate(
        scenario_id="shared_success_control",
        purpose="Both policies should retain a small set of highly ranked, lexically distinct required facts.",
        candidates=[*required_items, *tail],
        required=tuple(item.source_event_id for item in required_items),
        designed_to_favor="neither",
    )


def _head_to_head(cases: list[dict[str, object]]) -> dict[str, int]:
    counts = {
        "coverage_aware_only": 0,
        "top_k_only": 0,
        "both": 0,
        "neither": 0,
    }
    for case in cases:
        coverage = bool(case["coverage_aware"]["success"])
        top_k = bool(case["top_k"]["success"])
        if coverage and top_k:
            counts["both"] += 1
        elif coverage:
            counts["coverage_aware_only"] += 1
        elif top_k:
            counts["top_k_only"] += 1
        else:
            counts["neither"] += 1
    return counts


def run_benchmark(*, stress: bool) -> dict[str, object]:
    bait_count = 48 if stress else 12
    cases = [
        _numeric_fact_blindness(bait_count=bait_count),
        _corroboration_is_repetition(bait_count=bait_count),
        _random_token_novelty_attack(bait_count=bait_count),
        _diversity_metadata_attack(bait_count=bait_count),
        _stale_retention_poisoning(bait_count=bait_count),
        _verbose_irrelevance_over_concise_truth(bait_count=bait_count),
        _composer_positive_control(bait_count=bait_count),
        _shared_success_control(),
    ]
    return {
        "schema_version": 1,
        "benchmark_id": "MEM-ADAPT-004",
        "mode": "stress" if stress else "quick",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_packet_limit": PACKET_LIMIT,
        "evaluation_boundary": (
            "Coverage-aware composition is frozen. Both policies receive the identical explicit ordered "
            "candidate pool and final packet budget; no retrieval or model behavior is under test."
        ),
        "red_team_rule": (
            "Cases intentionally designed for top-k are valid attacks. Do not tune the composer until the "
            "unmodified implementation has been measured against the complete red-team corpus."
        ),
        "head_to_head": _head_to_head(cases),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark(stress=args.stress)
    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"MEM-ADAPT-004_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "head_to_head": result["head_to_head"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
