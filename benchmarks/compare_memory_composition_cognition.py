"""MEM-ADAPT-006: native cognition comparison over bounded memory composition.

This benchmark crosses the boundary from evidence-set completeness to actual local
model cognition. Each scenario creates one canonical PostgreSQL history and runs one
adaptive memory-attention retrieval pass to obtain a shared candidate population.
Raw top-k, frozen coverage Composer v1, and relevance-constrained Composer v2 then
receive that identical population and the same six-item final packet budget.

Each packet is handed to a fresh stateless ``OllamaClient.respond`` invocation. No
conversation transcript or model context is carried between calls. The benchmark
scores retrieval availability, composition completeness, model answer correctness,
and the layer at which a failure occurred separately.

The script is destructive and refuses any database whose name does not contain
``test`` or ``benchmark``.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
import runpy
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app@localhost:5432/jit_agent_test",
)

import psycopg

from jit_agent import db, jit_memory
from jit_agent.adaptive_memory_attention import MemoryUncertainty, RetrievalTelemetry
from jit_agent.adaptive_memory_retrieval import request_adaptive_memory
from jit_agent.evidence_composer import compose_coverage_aware, compose_relevance_coverage
from jit_agent.llm import OllamaClient
from jit_agent.models import Event, MemoryEvidence, MemoryPacket
from jit_agent.ollama_runtime import configured_ollama_model


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "benchmarks" / "results"
BASELINE = runpy.run_path(
    str(ROOT / "benchmarks" / "compare_memory_attention_architectures.py"),
    run_name="mem_adapt_006_baseline",
)

_reset_database = BASELINE["_reset_database"]
_prepare_database = BASELINE["_prepare_database"]
_new_conversation = BASELINE["_new_conversation"]
_record = BASELINE["_record"]
_finalize_corpus = BASELINE["_finalize_corpus"]
_insert_association = BASELINE["_insert_association"]

PACKET_LIMIT = 6
QUICK_DISTRACTORS = 12
STRESS_DISTRACTORS = 40
QUICK_POOL_LIMIT = 32
STRESS_POOL_LIMIT = 64
POLICIES = ("top_k", "coverage_v1", "relevance_coverage_v2")


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    purpose: str
    question: str
    expected_answer: str
    corpus: object
    retained: tuple[MemoryEvidence, ...] = ()
    uncertainty: MemoryUncertainty = MemoryUncertainty.MISSING_CONTEXT
    telemetry: RetrievalTelemetry = RetrievalTelemetry(candidate_scores=())


def _memory_evidence(
    event: Event,
    content: str,
    *,
    score: float = 0.01,
    retrieval_reasons: tuple[str, ...] = ("RETAINED_EVIDENCE",),
) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=event.event_id,
        event_type=event.event_type,
        source=event.source,
        created_at=event.created_at,
        conversation_id=event.conversation_id,
        conversation_seq=event.conversation_seq,
        global_seq=event.global_seq,
        content=content,
        score=score,
        retrieval_reasons=list(retrieval_reasons),
        provenance_event_ids=[],
    )


def _duplicate_pressure_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "archive recall benchmark vault phrase recorded COPPER-LANTERN-47",
    )
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            f"archive recall benchmark vault phrase recorded routine duplicate-{index}",
        )
    question = (
        "In the archive recall benchmark, what vault phrase was recorded? "
        "Return exactly the phrase and nothing else."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=(target.event_id,),
    )
    return Scenario(
        scenario_id="duplicate_pressure_old_fact",
        purpose=(
            "Test whether a stateless model can answer from a uniquely informative old fact "
            "that remains in the shared retrieval pool below repetitive newer evidence."
        ),
        question=question,
        expected_answer="COPPER-LANTERN-47",
        corpus=corpus,
    )


def _correction_pair_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    original = _record(
        conn,
        conversation_id,
        "Atlas benchmark code earlier original value ORBIT-OLD-17",
    )
    correction = _record(
        conn,
        conversation_id,
        "Atlas benchmark code later corrected value ORBIT-NEW-29",
    )
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            f"Atlas benchmark code earlier original later corrected value review duplicate-{index}",
        )
    question = (
        "For the Atlas benchmark code, what were the earlier original value and the later "
        "corrected value? Return exactly '<original> | <corrected>' and nothing else."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=(original.event_id, correction.event_id),
    )
    return Scenario(
        scenario_id="correction_pair_reasoning",
        purpose=(
            "Require cognition to preserve and distinguish an older claim from its correction, "
            "rather than answering from whichever statement happens to survive composition."
        ),
        question=question,
        expected_answer="ORBIT-OLD-17 | ORBIT-NEW-29",
        corpus=corpus,
        uncertainty=MemoryUncertainty.POSSIBLE_CONTRADICTION,
        telemetry=RetrievalTelemetry(candidate_scores=(0.52, 0.48)),
    )


def _distributed_clues_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    clues = (
        _record(
            conn,
            conversation_id,
            "Orion planning thermal ceiling memory reserve scheduler margin clue thermal ceiling 71",
        ),
        _record(
            conn,
            conversation_id,
            "Orion planning thermal ceiling memory reserve scheduler margin clue memory reserve 2048",
        ),
        _record(
            conn,
            conversation_id,
            "Orion planning thermal ceiling memory reserve scheduler margin clue scheduler margin 18",
        ),
    )
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            (
                "Orion planning thermal ceiling memory reserve scheduler margin routine review "
                f"duplicate-{index}"
            ),
        )
    question = (
        "For Orion planning, what are the thermal ceiling, memory reserve, and scheduler margin? "
        "Return exactly '<thermal> | <memory> | <margin>' using only the recorded numeric values."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=tuple(item.event_id for item in clues),
    )
    return Scenario(
        scenario_id="distributed_clues_reasoning",
        purpose=(
            "Require a six-item context to preserve three complementary lower-ranked facts and "
            "require the model to synthesize them in the requested order."
        ),
        question=question,
        expected_answer="71 | 2048 | 18",
        corpus=corpus,
    )


def _numeric_core_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            (
                "calibration threshold value commentary "
                f"zephyr-{index} quartz-{index} nebula-{index}"
            ),
        )
    required = tuple(
        _record(
            conn,
            conversation_id,
            f"calibration threshold value {10 * (index + 1)}",
        )
        for index in range(PACKET_LIMIT)
    )
    question = (
        "What are the six calibration threshold values in recorded order? "
        "Return exactly '<v1> | <v2> | <v3> | <v4> | <v5> | <v6>'."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=tuple(item.event_id for item in required),
    )
    return Scenario(
        scenario_id="numeric_payload_cognition",
        purpose=(
            "Attack novelty-first composition with six highly relevant facts whose payload is numeric."
        ),
        question=question,
        expected_answer="10 | 20 | 30 | 40 | 50 | 60",
        corpus=corpus,
    )


def _novelty_bait_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            (
                "deployment approval gate phase unrelated payload "
                f"xqzeta-{index} prionyx-{index} kaldrim-{index} vospera-{index}"
            ),
        )
    labels = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta")
    required = tuple(
        _record(
            conn,
            conversation_id,
            f"deployment approval gate phase {label} approved",
        )
        for label in labels
    )
    question = (
        "Which six deployment approval gate phase labels were approved? "
        "Return exactly the six labels in recorded order separated by ' | '."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=tuple(item.event_id for item in required),
    )
    return Scenario(
        scenario_id="random_token_novelty_cognition",
        purpose=(
            "Verify that irrelevant lexical novelty cannot displace six nonredundant high-ranked facts."
        ),
        question=question,
        expected_answer="alpha | beta | gamma | delta | epsilon | zeta",
        corpus=corpus,
    )


def _stale_retained_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    stale_conversation = _new_conversation(conn)
    stale_text = "obsolete prior attention hypothesis STALE-SHADOW-13"
    stale = _record(conn, stale_conversation, stale_text)

    conversation_id = _new_conversation(conn)
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            f"current verified component registry low-rank filler-{index}",
        )
    labels = ("A1", "B2", "C3", "D4", "E5", "F6")
    required = tuple(
        _record(
            conn,
            conversation_id,
            f"current verified component registry item {label}",
        )
        for label in labels
    )
    question = (
        "What are the six current verified component registry items? "
        "Return exactly the six item labels in recorded order separated by ' | '."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=tuple(item.event_id for item in required),
    )
    return Scenario(
        scenario_id="stale_retained_cognition",
        purpose=(
            "Verify that stale retained history cannot consume a slot when all six current "
            "relevance-core facts are independently informative."
        ),
        question=question,
        expected_answer="A1 | B2 | C3 | D4 | E5 | F6",
        corpus=corpus,
        retained=(_memory_evidence(stale, stale_text),),
    )


def _association_bridge_case(conn: psycopg.Connection, distractors: int) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(conn, conversation_id, "opaque evidence token ZETA-ORCHID-41")
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            f"deployment rollback decision token discussion routine duplicate-{index}",
        )
    anchor = _record(conn, conversation_id, "deployment rollback decision anchor")
    question = (
        "What opaque token was associated with the deployment rollback decision? "
        "Return exactly the token and nothing else."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    _insert_association(
        conn,
        association_id="mem-adapt-006-rollback-token",
        source_kind="EVENT",
        source=str(anchor.event_id),
        target_kind="EVENT",
        target=str(target.event_id),
        provenance_event_ids=(str(anchor.event_id), str(target.event_id)),
    )
    return Scenario(
        scenario_id="association_bridge_cognition",
        purpose=(
            "Exercise the complete path: zero-overlap evidence must first reach the shared pool "
            "through adaptive association traversal and then survive bounded composition."
        ),
        question=question,
        expected_answer="ZETA-ORCHID-41",
        corpus=corpus,
        uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
        telemetry=RetrievalTelemetry(candidate_scores=(0.88, 0.12)),
    )


def _abstention_case(conn: psycopg.Connection) -> Scenario:
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    for index in range(8):
        _record(conn, conversation_id, f"unrelated garden ledger note-{index}")
    question = (
        "What is the synthetic Nimbus benchmark marker? If the supplied persisted evidence does "
        "not establish one, return exactly INSUFFICIENT and nothing else."
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text=question,
        anchors=(),
        required=(),
    )
    return Scenario(
        scenario_id="unsupported_query_abstention",
        purpose="Verify that composition improvements do not turn absent evidence into a fabricated answer.",
        question=question,
        expected_answer="INSUFFICIENT",
        corpus=corpus,
    )


def _retrieve_shared_pool(
    conn: psycopg.Connection,
    scenario: Scenario,
    *,
    pool_limit: int,
) -> MemoryPacket:
    corpus = scenario.corpus
    return request_adaptive_memory(
        conn,
        conversation_id=corpus.conversation_id,
        correlation_id=corpus.correlation_id,
        requesting_component="benchmark:mem-adapt-006:shared-pool",
        need=jit_memory.build_memory_need(
            corpus.query_text,
            focus_event_ids=list(corpus.anchor_event_ids),
            limit=pool_limit,
        ),
        uncertainty=scenario.uncertainty,
        telemetry=scenario.telemetry,
        before_global_seq=corpus.before_global_seq,
        memory_request_id=uuid.uuid4(),
    )


def _packet(
    pool: MemoryPacket,
    items: tuple[MemoryEvidence, ...] | list[MemoryEvidence],
    *,
    policy: str,
) -> MemoryPacket:
    bounded = list(items)[:PACKET_LIMIT]
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=pool.need.model_copy(update={"limit": PACKET_LIMIT}),
        supported=bool(bounded),
        items=bounded,
        retrieval_trace={
            "benchmark_id": "MEM-ADAPT-006",
            "composition_policy": policy,
            "shared_pool_memory_request_id": str(pool.memory_request_id),
        },
    )


def _packet_variants(
    pool: MemoryPacket,
    *,
    retained: tuple[MemoryEvidence, ...] = (),
) -> dict[str, MemoryPacket]:
    v1 = compose_coverage_aware(pool.items, retained=retained, limit=PACKET_LIMIT)
    v2 = compose_relevance_coverage(pool.items, retained=retained, limit=PACKET_LIMIT)
    return {
        "top_k": _packet(pool, pool.items[:PACKET_LIMIT], policy="top_k"),
        "coverage_v1": _packet(pool, v1.items, policy="coverage_v1"),
        "relevance_coverage_v2": _packet(
            pool,
            v2.items,
            policy="relevance_coverage_v2",
        ),
    }


def _normalize_answer(value: str) -> str:
    normalized = " ".join(value.strip().split())
    while normalized.endswith((".", "!")):
        normalized = normalized[:-1].rstrip()
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {"'", '"'}
    ):
        normalized = normalized[1:-1].strip()
    return normalized.casefold()


def _failure_layer(
    *,
    available: bool,
    evidence_complete: bool,
    answer_correct: bool,
    model_error: str | None,
) -> str:
    if not available:
        return "retrieval_or_retention"
    if not evidence_complete:
        return "composition"
    if model_error is not None:
        return "model_runtime"
    if not answer_correct:
        return "reasoning"
    return "success"


def _policy_order(case_index: int) -> tuple[str, str, str]:
    offset = case_index % len(POLICIES)
    return POLICIES[offset:] + POLICIES[:offset]


def _required_ranks(pool: MemoryPacket, required_ids: tuple[uuid.UUID, ...]) -> dict[str, int | None]:
    return {
        str(event_id): next(
            (
                index
                for index, item in enumerate(pool.items, start=1)
                if item.source_event_id == event_id
            ),
            None,
        )
        for event_id in required_ids
    }


def _evaluate_scenario(
    client: OllamaClient,
    scenario: Scenario,
    pool: MemoryPacket,
    *,
    case_index: int,
) -> dict[str, object]:
    required_ids = tuple(scenario.corpus.required_event_ids)
    retained_ids = {item.source_event_id for item in scenario.retained}
    pool_ids = {item.source_event_id for item in pool.items}
    available_ids = pool_ids | retained_ids
    available = set(required_ids).issubset(available_ids)
    packets = _packet_variants(pool, retained=scenario.retained)

    policies: dict[str, dict[str, object]] = {}
    for policy in _policy_order(case_index):
        packet = packets[policy]
        surfaced_ids = {item.source_event_id for item in packet.items}
        evidence_complete = set(required_ids).issubset(surfaced_ids)
        started = perf_counter()
        answer = ""
        error: str | None = None
        try:
            answer = client.respond(scenario.question, packet)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
        answer_correct = error is None and (
            _normalize_answer(answer) == _normalize_answer(scenario.expected_answer)
        )
        policies[policy] = {
            "packet_event_ids": [str(item.source_event_id) for item in packet.items],
            "packet_item_count": len(packet.items),
            "evidence_complete": evidence_complete,
            "answer": answer,
            "answer_correct": answer_correct,
            "elapsed_ms": elapsed_ms,
            "error": error,
            "failure_layer": _failure_layer(
                available=available,
                evidence_complete=evidence_complete,
                answer_correct=answer_correct,
                model_error=error,
            ),
        }

    return {
        "scenario_id": scenario.scenario_id,
        "purpose": scenario.purpose,
        "question": scenario.question,
        "expected_answer": scenario.expected_answer,
        "required_event_ids": [str(value) for value in required_ids],
        "required_pool_ranks": _required_ranks(pool, required_ids),
        "retained_event_ids": [str(value) for value in retained_ids],
        "required_available_to_composers": available,
        "shared_pool_item_count": len(pool.items),
        "shared_pool_event_ids": [str(item.source_event_id) for item in pool.items],
        "adaptive_policy": pool.retrieval_trace.get("adaptive_policy"),
        "llm_call_order": list(_policy_order(case_index)),
        "policies": policies,
    }


def _pairwise(cases: list[dict[str, object]], left: str, right: str) -> dict[str, int]:
    counts = {"left_only": 0, "right_only": 0, "both": 0, "neither": 0}
    for case in cases:
        policies = case["policies"]
        left_ok = bool(policies[left]["answer_correct"])
        right_ok = bool(policies[right]["answer_correct"])
        if left_ok and right_ok:
            counts["both"] += 1
        elif left_ok:
            counts["left_only"] += 1
        elif right_ok:
            counts["right_only"] += 1
        else:
            counts["neither"] += 1
    return counts


def _policy_summary(cases: list[dict[str, object]], policy: str) -> dict[str, object]:
    rows = [case["policies"][policy] for case in cases]
    return {
        "cases": len(rows),
        "evidence_complete": sum(bool(row["evidence_complete"]) for row in rows),
        "answer_correct": sum(bool(row["answer_correct"]) for row in rows),
        "composition_failures": sum(row["failure_layer"] == "composition" for row in rows),
        "reasoning_failures": sum(row["failure_layer"] == "reasoning" for row in rows),
        "model_runtime_failures": sum(row["failure_layer"] == "model_runtime" for row in rows),
        "retrieval_or_retention_failures": sum(
            row["failure_layer"] == "retrieval_or_retention" for row in rows
        ),
        "mean_llm_elapsed_ms": round(
            sum(float(row["elapsed_ms"]) for row in rows) / len(rows),
            3,
        ) if rows else 0.0,
    }


def run_comparison(*, stress: bool) -> dict[str, object]:
    conn = db.get_connection()
    try:
        database_name = _prepare_database(conn)
        distractors = STRESS_DISTRACTORS if stress else QUICK_DISTRACTORS
        pool_limit = STRESS_POOL_LIMIT if stress else QUICK_POOL_LIMIT
        builders = (
            _duplicate_pressure_case,
            _correction_pair_case,
            _distributed_clues_case,
            _numeric_core_case,
            _novelty_bait_case,
            _stale_retained_case,
            _association_bridge_case,
        )
        client = OllamaClient()
        cases: list[dict[str, object]] = []
        for case_index, builder in enumerate(builders):
            scenario = builder(conn, distractors)
            pool = _retrieve_shared_pool(conn, scenario, pool_limit=pool_limit)
            cases.append(
                _evaluate_scenario(
                    client,
                    scenario,
                    pool,
                    case_index=case_index,
                )
            )

        abstention = _abstention_case(conn)
        abstention_pool = _retrieve_shared_pool(conn, abstention, pool_limit=pool_limit)
        cases.append(
            _evaluate_scenario(
                client,
                abstention,
                abstention_pool,
                case_index=len(cases),
            )
        )

        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-006",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "model": configured_ollama_model(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "final_packet_limit": PACKET_LIMIT,
            "shared_pool_limit": pool_limit,
            "distractor_count": distractors,
            "stateless_llm_contract": (
                "Every policy answer is a fresh OllamaClient.respond invocation with no inherited "
                "transcript or model context. Calls are sequential; only model residency may persist."
            ),
            "evaluation_boundary": (
                "Adaptive retrieval runs once per scenario. Top-k, Composer v1, and Composer v2 "
                "receive the identical shared candidate population and six-item packet budget. "
                "Retrieval availability, composition completeness, and answer correctness are scored separately."
            ),
            "summary": {
                policy: _policy_summary(cases, policy)
                for policy in POLICIES
            },
            "answer_head_to_head": {
                "v2_vs_top_k": _pairwise(cases, "relevance_coverage_v2", "top_k"),
                "v2_vs_v1": _pairwise(cases, "relevance_coverage_v2", "coverage_v1"),
                "v1_vs_top_k": _pairwise(cases, "coverage_v1", "top_k"),
            },
            "cases": cases,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_comparison(stress=args.stress)
    output = args.output
    if output is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output = RESULTS_DIR / f"MEM-ADAPT-006_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "mode": result["mode"],
                "model": result["model"],
                "summary": result["summary"],
                "answer_head_to_head": result["answer_head_to_head"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
