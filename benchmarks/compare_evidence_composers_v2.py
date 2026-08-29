"""MEM-ADAPT-005: combined adversarial comparison for Evidence Composer v2.

This benchmark holds retrieval out of scope and gives all policies the same explicit
ordered candidate pools and six-item packet budget. It combines the two failure
regimes discovered by MEM-ADAPT-003 and MEM-ADAPT-004:

- top-k crowd-out of older/distributed evidence;
- v1 novelty/diversity displacement of stronger evidence.

The v2 policy is not a weighted blend. It preserves nonredundant top-k evidence and
spends only demonstrably redundant core slots on coverage/support augmentation.
One diagnostic case intentionally withholds provenance that would be required to
distinguish corroboration from duplication; that case is reported but excluded from
the observable-evidence acceptance summary.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from jit_agent.evidence_composer import (
    CompositionResult,
    RelevanceCoverageResult,
    compose_coverage_aware,
    compose_relevance_coverage,
)
from jit_agent.models import EventType, MemoryEvidence


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "benchmarks" / "results"
PACKET_LIMIT = 6
_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event_id(index: int) -> uuid.UUID:
    return uuid.UUID(int=index + 1)


def _conversation_id(index: int = 0) -> uuid.UUID:
    return uuid.UUID(int=20_000 + index)


def _evidence(
    index: int,
    content: str,
    *,
    score: float,
    source: str = "memory",
    conversation_index: int = 0,
    event_type: EventType = EventType.USER_PROMPT,
    provenance: tuple[uuid.UUID, ...] = (),
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
        retrieval_reasons=["LEXICAL"],
        provenance_event_ids=list(provenance),
    )


def _ids(items) -> tuple[uuid.UUID, ...]:
    return tuple(item.source_event_id for item in items)


def _success(items, required: tuple[uuid.UUID, ...]) -> bool:
    surfaced = set(_ids(items))
    return all(event_id in surfaced for event_id in required)


def _serialize_v1(result: CompositionResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for decision in result.decisions:
        row = asdict(decision)
        row["source_event_id"] = str(decision.source_event_id)
        row["token_novelty"] = str(decision.token_novelty)
        rows.append(row)
    return rows


def _serialize_v2(result: RelevanceCoverageResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for decision in result.decisions:
        row = asdict(decision)
        row["source_event_id"] = str(decision.source_event_id)
        row["token_novelty"] = str(decision.token_novelty)
        rows.append(row)
    return rows


def _evaluate(
    *,
    scenario_id: str,
    purpose: str,
    candidates: list[MemoryEvidence],
    required: tuple[uuid.UUID, ...],
    retained: tuple[MemoryEvidence, ...] = (),
    observable: bool = True,
) -> dict[str, object]:
    top_k = candidates[:PACKET_LIMIT]
    v1 = compose_coverage_aware(candidates, retained=retained, limit=PACKET_LIMIT)
    v2 = compose_relevance_coverage(candidates, retained=retained, limit=PACKET_LIMIT)
    ranks = {
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
        "observable": observable,
        "required_candidate_ranks": ranks,
        "retained_count": len(retained),
        "top_k": {
            "success": _success(top_k, required),
            "event_ids": [str(value) for value in _ids(top_k)],
        },
        "coverage_v1": {
            "success": _success(v1.items, required),
            "event_ids": [str(value) for value in _ids(v1.items)],
            "decisions": _serialize_v1(v1),
        },
        "relevance_coverage_v2": {
            "success": _success(v2.items, required),
            "event_ids": [str(value) for value in _ids(v2.items)],
            "decisions": _serialize_v2(v2),
        },
    }


def _duplicate_pressure_target(*, duplicate_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(index, f"orbit cedar amber repetitive update-{index}", score=0.81)
        for index in range(duplicate_count)
    ]
    target = _evidence(
        500,
        "orbit cedar amber exact phrase identifies decisive cobalt exception",
        score=0.81,
    )
    return _evaluate(
        scenario_id="duplicate_pressure_old_target",
        purpose="A uniquely informative older tied memory must survive repetitive top-k crowd-out.",
        candidates=[*repetitive, target],
        required=(target.source_event_id,),
    )


def _correction_pair_pressure(*, duplicate_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(index, f"Atlas launch planning update-{index}", score=0.9)
        for index in range(duplicate_count)
    ]
    original = _evidence(500, "Atlas launch date recorded Tuesday original claim", score=0.7)
    correction = _evidence(501, "Atlas launch date corrected Thursday supersedes Tuesday", score=0.69)
    return _evaluate(
        scenario_id="correction_pair_under_duplicate_pressure",
        purpose="Both an older claim and its correction must coexist despite repetitive current updates.",
        candidates=[*repetitive, original, correction],
        required=(original.source_event_id, correction.source_event_id),
    )


def _distributed_weak_clues(*, duplicate_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(index, f"project decision repetitive update-{index}", score=0.95)
        for index in range(duplicate_count)
    ]
    clues = [
        _evidence(500, "project decision clue thermal ceiling", score=0.4),
        _evidence(501, "project decision clue memory pressure", score=0.39),
        _evidence(502, "project decision clue scheduler headroom", score=0.38),
    ]
    return _evaluate(
        scenario_id="distributed_weak_clues",
        purpose="Several lower-ranked complementary clues must survive a repetitive high-score cluster.",
        candidates=[*repetitive, *clues],
        required=tuple(item.source_event_id for item in clues),
    )


def _temporal_distribution(*, duplicate_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(index, f"Atlas design routine revision-{index}", score=0.9)
        for index in range(duplicate_count)
    ]
    required = [
        _evidence(500, "Atlas design inception append only ledger", score=0.7),
        _evidence(501, "Atlas design midcourse working state", score=0.69),
        _evidence(502, "Atlas design final stateless workers", score=0.68),
    ]
    return _evaluate(
        scenario_id="temporally_distributed_evidence",
        purpose="Distinct early, middle, and late facts must fit beside repetitive current history.",
        candidates=[*repetitive, *required],
        required=tuple(item.source_event_id for item in required),
    )


def _retained_target(*, duplicate_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(index, f"obsolete explanation reinforcement-{index}", score=0.9)
        for index in range(duplicate_count)
    ]
    retained = _evidence(900, "escape correction canonical fact retained target", score=0.7)
    return _evaluate(
        scenario_id="retained_target_across_attention_shift",
        purpose="Unique retained evidence may occupy a slot only when the current relevance core is redundant.",
        candidates=repetitive,
        retained=(retained,),
        required=(retained.source_event_id,),
    )


def _numeric_payload_attack(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(index, f"calibration threshold value {10 * (index + 1)}", score=1.0 - index * 0.01)
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            f"calibration threshold commentary zephyr{index} quartz{index} nebula{index}",
            score=0.8 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="numeric_payload_attack",
        purpose="Standalone numeric facts in the relevance core must not be mistaken for duplicate evidence.",
        candidates=[*required, *bait],
        required=tuple(item.source_event_id for item in required),
    )


def _random_token_attack(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(index, f"deployment approval gate phase {index + 1}", score=1.0 - index * 0.01)
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            f"deployment unrelated xqzeta{index} prionyx{index} kaldrim{index} vospera{index}",
            score=0.79 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="random_token_novelty_attack",
        purpose="Novel token salad must not displace six nonredundant higher-ranked facts.",
        candidates=[*required, *bait],
        required=tuple(item.source_event_id for item in required),
    )


def _metadata_diversity_attack(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(
            index,
            f"trusted audit confirms control state {index + 1}",
            score=1.0 - index * 0.01,
            source="trusted-audit",
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
            source=f"untrusted-{index}",
            conversation_index=index + 1,
            event_type=event_types[index % len(event_types)],
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="metadata_diversity_attack",
        purpose="Source/type/conversation diversity must not evict a nonredundant stronger relevance core.",
        candidates=[*required, *bait],
        required=tuple(item.source_event_id for item in required),
    )


def _verbose_bait_attack(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(index, f"safety verdict pass {index + 1}", score=1.0 - index * 0.01)
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(
            100 + index,
            f"safety peripheral lavender{index} turbine{index} mosaic{index} peninsula{index} harmonic{index}",
            score=0.77 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="verbose_irrelevance_attack",
        purpose="Verbose low-ranked novelty must not displace concise nonredundant high-ranked truths.",
        candidates=[*required, *bait],
        required=tuple(item.source_event_id for item in required),
    )


def _stale_retained_attack(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(index, f"current verified state component item{index}", score=1.0 - index * 0.01)
        for index in range(PACKET_LIMIT)
    ]
    bait = [
        _evidence(100 + index, f"current state filler-{index}", score=0.6 - index * 0.001)
        for index in range(bait_count)
    ]
    retained = _evidence(
        900,
        "obsolete superseded hypothesis from prior attention round",
        score=0.01,
        source="stale-memory",
    )
    return _evaluate(
        scenario_id="stale_retained_attack",
        purpose="Retained history must not evict any of six nonredundant current relevance-core facts.",
        candidates=[*required, *bait],
        retained=(retained,),
        required=tuple(item.source_event_id for item in required),
    )


def _independent_corroboration(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(
            index,
            "reactor seal remained intact",
            score=1.0 - index * 0.01,
            provenance=(uuid.uuid5(uuid.NAMESPACE_OID, f"witness:{index}"),),
        )
        for index in range(4)
    ]
    filler = [
        _evidence(20 + index, f"reactor seal routine filler-{index}", score=0.94 - index * 0.01)
        for index in range(2)
    ]
    bait = [
        _evidence(
            100 + index,
            f"reactor peripheral comet{index} orchard{index} velvet{index}",
            score=0.8 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="independent_corroboration",
        purpose="Repeated content with distinct canonical provenance is support, not disposable duplication.",
        candidates=[*required, *filler, *bait],
        required=tuple(item.source_event_id for item in required),
    )


def _unobservable_corroboration(*, bait_count: int) -> dict[str, object]:
    required = [
        _evidence(index, "reactor seal remained intact", score=1.0 - index * 0.01)
        for index in range(4)
    ]
    filler = [
        _evidence(20 + index, f"reactor seal routine filler-{index}", score=0.94 - index * 0.01)
        for index in range(2)
    ]
    bait = [
        _evidence(
            100 + index,
            f"reactor peripheral comet{index} orchard{index} velvet{index}",
            score=0.8 - index * 0.001,
        )
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="unobservable_corroboration_diagnostic",
        purpose=(
            "Diagnostic: identical rows claim independent corroboration but expose no distinct provenance, "
            "source, or conversation signal. A deterministic composer cannot infer hidden independence."
        ),
        candidates=[*required, *filler, *bait],
        required=tuple(item.source_event_id for item in required),
        observable=False,
    )


def _positive_control(*, bait_count: int) -> dict[str, object]:
    repetitive = [
        _evidence(index, "orbit cedar amber repetitive update", score=1.0 - index * 0.01)
        for index in range(PACKET_LIMIT)
    ]
    target = _evidence(50, "orbit cedar amber decisive exception cobalt", score=0.8)
    tail = [
        _evidence(100 + index, "orbit cedar amber repetitive update", score=0.7 - index * 0.001)
        for index in range(bait_count)
    ]
    return _evaluate(
        scenario_id="coverage_positive_control",
        purpose="Coverage must still rescue a uniquely informative lower-ranked target from redundant top-k evidence.",
        candidates=[*repetitive, target, *tail],
        required=(target.source_event_id,),
    )


def _shared_success() -> dict[str, object]:
    required = [
        _evidence(index, f"distinct required fact token{index}", score=1.0 - index * 0.01)
        for index in range(3)
    ]
    tail = [
        _evidence(20 + index, "routine filler", score=0.5 - index * 0.01)
        for index in range(3)
    ]
    return _evaluate(
        scenario_id="shared_success_control",
        purpose="All policies should preserve a small nonredundant relevance core.",
        candidates=[*required, *tail],
        required=tuple(item.source_event_id for item in required),
    )


def _pairwise(cases: list[dict[str, object]], left: str, right: str) -> dict[str, int]:
    counts = {"left_only": 0, "right_only": 0, "both": 0, "neither": 0}
    for case in cases:
        left_ok = bool(case[left]["success"])
        right_ok = bool(case[right]["success"])
        if left_ok and right_ok:
            counts["both"] += 1
        elif left_ok:
            counts["left_only"] += 1
        elif right_ok:
            counts["right_only"] += 1
        else:
            counts["neither"] += 1
    return counts


def _summary(cases: list[dict[str, object]]) -> dict[str, object]:
    observable = [case for case in cases if case["observable"]]
    return {
        "success_counts": {
            "top_k": sum(bool(case["top_k"]["success"]) for case in observable),
            "coverage_v1": sum(bool(case["coverage_v1"]["success"]) for case in observable),
            "relevance_coverage_v2": sum(
                bool(case["relevance_coverage_v2"]["success"]) for case in observable
            ),
        },
        "v2_vs_top_k": _pairwise(observable, "relevance_coverage_v2", "top_k"),
        "v2_vs_v1": _pairwise(observable, "relevance_coverage_v2", "coverage_v1"),
        "diagnostic_case_count": len(cases) - len(observable),
    }


def run_benchmark(*, stress: bool) -> dict[str, object]:
    duplicate_count = 40 if stress else 12
    bait_count = 48 if stress else 12
    cases = [
        _duplicate_pressure_target(duplicate_count=duplicate_count),
        _correction_pair_pressure(duplicate_count=duplicate_count),
        _distributed_weak_clues(duplicate_count=duplicate_count),
        _temporal_distribution(duplicate_count=duplicate_count),
        _retained_target(duplicate_count=duplicate_count),
        _numeric_payload_attack(bait_count=bait_count),
        _random_token_attack(bait_count=bait_count),
        _metadata_diversity_attack(bait_count=bait_count),
        _verbose_bait_attack(bait_count=bait_count),
        _stale_retained_attack(bait_count=bait_count),
        _independent_corroboration(bait_count=bait_count),
        _unobservable_corroboration(bait_count=bait_count),
        _positive_control(bait_count=bait_count),
        _shared_success(),
    ]
    return {
        "schema_version": 1,
        "benchmark_id": "MEM-ADAPT-005",
        "mode": "stress" if stress else "quick",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "final_packet_limit": PACKET_LIMIT,
        "evaluation_boundary": (
            "Top-k, frozen coverage v1, and relevance-constrained coverage v2 receive identical explicit "
            "candidate pools and packet budgets; retrieval and model behavior are out of scope."
        ),
        "summary": _summary(cases),
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
        output = RESULTS_DIR / f"MEM-ADAPT-005_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "summary": result["summary"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
