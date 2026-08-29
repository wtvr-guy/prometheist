"""MEM-ADAPT-002: semantic adversarial comparison of memory-attention strategies.

This benchmark deliberately evaluates *evidence retrieval*, not final-answer LLM
reasoning. A retrieval strategy succeeds when it exposes the complete canonical
evidence set required for a stateless downstream worker, or correctly returns no
historical evidence in an abstention case.

The frozen v0.7 profiles and adaptive controller share the same canonical ledger,
current percept, leakage boundary, evidence floor, automatic aperture, and focus
anchors. The live interaction path is not modified by this benchmark.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import runpy
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://jit_agent_app@localhost:5432/jit_agent_test",
)

from jit_agent import db, jit_memory
from jit_agent.adaptive_memory_attention import MemoryUncertainty, RetrievalTelemetry


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "benchmarks" / "results"
BASELINE = runpy.run_path(
    str(ROOT / "benchmarks" / "compare_memory_attention_architectures.py"),
    run_name="mem_adapt_002_baseline",
)

_reset_database = BASELINE["_reset_database"]
_prepare_database = BASELINE["_prepare_database"]
_new_conversation = BASELINE["_new_conversation"]
_record = BASELINE["_record"]
_finalize_corpus = BASELINE["_finalize_corpus"]
_insert_association = BASELINE["_insert_association"]
_run_aperture = BASELINE["_run_aperture"]
_run_frozen = BASELINE["_run_frozen"]
_run_adaptive = BASELINE["_run_adaptive"]
_head_to_head = BASELINE["_head_to_head"]


def _as_observations(*items) -> list[dict[str, object]]:
    return [asdict(item) for item in items if item is not None]


def _case(
    *,
    scenario_id: str,
    purpose: str,
    observations: list[dict[str, object]],
    aperture_success: bool,
    evaluation: str = "required_evidence_complete",
    notes: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "scenario_id": scenario_id,
        "purpose": purpose,
        "evaluation": evaluation,
        "aperture_already_sufficient": aperture_success,
        "observations": observations,
    }
    if notes:
        result["notes"] = notes
    return result


def _correction_pair_case(conn) -> dict[str, object]:
    """A later correction must not erase the older claim needed to interpret it."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    original = _record(
        conn,
        conversation_id,
        "Atlas launch date was recorded as Tuesday; status ORIGINAL-CLAIM",
    )
    correction = _record(
        conn,
        conversation_id,
        "Atlas launch date was corrected from Tuesday to Thursday; status CORRECTION",
    )
    for index in range(8):
        _record(conn, conversation_id, f"Atlas launch date planning distractor-{index}")
    anchor = _record(conn, conversation_id, "active Atlas planning anchor")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="Atlas launch date",
        anchors=(anchor.event_id,),
        required=(original.event_id, correction.event_id),
    )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.POSSIBLE_CONTRADICTION,
        telemetry=RetrievalTelemetry(candidate_scores=(0.52, 0.48)),
    )
    return _case(
        scenario_id="correction_pair_complete_evidence",
        purpose="Retrieve both an older claim and its later correction so downstream cognition can reason about supersession instead of seeing only the newest statement.",
        observations=_as_observations(aperture, deeper, focused, adaptive),
        aperture_success=aperture.success,
        notes="Success means evidence completeness only; the benchmark does not ask retrieval to decide which claim is authoritative.",
    )


def _zero_overlap_bridge_case(conn) -> dict[str, object]:
    """The target has no lexical overlap with the percept and requires an anchor route."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(conn, conversation_id, "opaque decision token ZETA-ORCHID-41")
    anchor = _record(conn, conversation_id, "deployment rollback discussion anchor")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="why did the deployment strategy change",
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    _insert_association(
        conn,
        association_id="bridge-anchor-to-opaque-target",
        source_kind="EVENT",
        source=str(anchor.event_id),
        target_kind="EVENT",
        target=str(target.event_id),
        provenance_event_ids=(str(anchor.event_id), str(target.event_id)),
    )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
        telemetry=RetrievalTelemetry(candidate_scores=(0.92, 0.08)),
    )
    return _case(
        scenario_id="zero_overlap_anchor_bridge",
        purpose="Recover canonical evidence with zero lexical overlap by following a selected contextual anchor while preserving the current percept as the semantic cue.",
        observations=_as_observations(aperture, deeper, focused, adaptive),
        aperture_success=aperture.success,
    )


def _false_short_true_long_case(conn) -> dict[str, object]:
    """A plausible short association must not prevent exposure of deeper counterevidence."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchor = _record(conn, conversation_id, "incident cause investigation anchor")
    false_claim = _record(
        conn,
        conversation_id,
        "early investigation blamed network congestion; FALSE-SHORT-CLAIM",
    )
    intermediates = [
        _record(conn, conversation_id, f"opaque causal bridge-{index}") for index in range(4)
    ]
    true_target = _record(
        conn,
        conversation_id,
        "later forensic evidence identified clock skew; TRUE-DEEP-EVIDENCE",
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="what caused the incident",
        anchors=(anchor.event_id,),
        required=(false_claim.event_id, true_target.event_id),
    )
    _insert_association(
        conn,
        association_id="false-short",
        source_kind="EVENT",
        source=str(anchor.event_id),
        target_kind="EVENT",
        target=str(false_claim.event_id),
        provenance_event_ids=(str(anchor.event_id), str(false_claim.event_id)),
    )
    chain = [anchor, *intermediates, true_target]
    for index, (source, target) in enumerate(zip(chain, chain[1:])):
        _insert_association(
            conn,
            association_id=f"true-long-{index}",
            source_kind="EVENT",
            source=str(source.event_id),
            target_kind="EVENT",
            target=str(target.event_id),
            provenance_event_ids=(str(source.event_id), str(target.event_id)),
        )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.POSSIBLE_CONTRADICTION,
        telemetry=RetrievalTelemetry(candidate_scores=(0.86, 0.14)),
    )
    return _case(
        scenario_id="false_short_path_true_deep_counterevidence",
        purpose="Expose both an attractive one-hop claim and deeper counterevidence rather than allowing the shorter associative route to monopolize the evidence packet.",
        observations=_as_observations(aperture, deeper, focused, adaptive),
        aperture_success=aperture.success,
    )


def _multi_anchor_deep_case(conn) -> dict[str, object]:
    """Relational evidence requires multiple anchors and five association hops."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    anchors = (
        _record(conn, conversation_id, "Alice architecture discussion anchor"),
        _record(conn, conversation_id, "Bob deployment discussion anchor"),
    )
    paths: list[list[object]] = []
    for branch in range(2):
        intermediates = [
            _record(conn, conversation_id, f"opaque branch-{branch}-bridge-{index}")
            for index in range(4)
        ]
        paths.append([anchors[branch], *intermediates])
    target = _record(
        conn,
        conversation_id,
        "shared hidden design constraint RELATIONAL-FIVE-HOP-TARGET",
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="what hidden constraint connected the architecture and deployment discussions",
        anchors=tuple(item.event_id for item in anchors),
        required=(target.event_id,),
    )
    for branch, path in enumerate(paths):
        chain = [*path, target]
        for index, (source, destination) in enumerate(zip(chain, chain[1:])):
            _insert_association(
                conn,
                association_id=f"multi-deep-{branch}-{index}",
                source_kind="EVENT",
                source=str(source.event_id),
                target_kind="EVENT",
                target=str(destination.event_id),
                provenance_event_ids=(str(source.event_id), str(destination.event_id)),
            )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    cross = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.CROSS_REFERENCE)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
        telemetry=RetrievalTelemetry(candidate_scores=(0.51, 0.49)),
    )
    return _case(
        scenario_id="multi_anchor_five_hop_relationship",
        purpose="Test whether anchor cardinality and traversal depth can vary independently when a relationship requires multiple foci and deeper search than frozen cross-reference permits.",
        observations=_as_observations(aperture, deeper, cross, adaptive),
        aperture_success=aperture.success,
    )


def _single_anchor_reorientation_case(conn, hostile_edges: int) -> dict[str, object]:
    """A wrong focus must eventually be abandoned for an unanchored cue-term route."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "escape correction canonical fact REORIENT-CORRECTION-TARGET",
    )
    anchor = _record(conn, conversation_id, "plausible obsolete explanation anchor")
    distractors = [
        _record(conn, conversation_id, f"obsolete explanation reinforcement-{index}")
        for index in range(hostile_edges)
    ]
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="escape correction",
        anchors=(anchor.event_id,),
        required=(target.event_id,),
    )
    for index, distractor in enumerate(distractors):
        _insert_association(
            conn,
            association_id=f"trap-{index:05d}",
            source_kind="EVENT",
            source=str(anchor.event_id),
            target_kind="EVENT",
            target=str(distractor.event_id),
            provenance_event_ids=(str(anchor.event_id), str(distractor.event_id)),
        )
    _insert_association(
        conn,
        association_id="z-correction-route",
        source_kind="TERM",
        source="escape",
        target_kind="EVENT",
        target=str(target.event_id),
        provenance_event_ids=(str(target.event_id),),
    )
    aperture = _run_aperture(conn, corpus)
    focused = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.FOCUSED_RECALL)
    rounds = []
    for round_index in range(3):
        rounds.append(
            _run_adaptive(
                conn,
                corpus,
                uncertainty=MemoryUncertainty.MISSING_RELATIONSHIP,
                telemetry=RetrievalTelemetry(
                    candidate_scores=(0.90, 0.10),
                    anchored_rounds=round_index,
                    support_gain=0.0 if round_index else None,
                ),
                method_suffix=f":round-{round_index + 1}",
            )
        )
    return _case(
        scenario_id="obsolete_single_anchor_requires_reorientation",
        purpose="Test whether repeated non-improving focus on a plausible obsolete explanation is abandoned so a correction reachable from the original cue can enter evidence.",
        observations=_as_observations(aperture, focused, *rounds),
        aperture_success=aperture.success,
    )


def _multi_anchor_reorientation_case(conn, hostile_edges: int) -> dict[str, object]:
    """A mutually reinforcing wrong cluster must not permanently own attention."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    target = _record(
        conn,
        conversation_id,
        "escape cluster correction canonical fact MULTI-REORIENT-TARGET",
    )
    anchors = (
        _record(conn, conversation_id, "obsolete cluster explanation alpha"),
        _record(conn, conversation_id, "obsolete cluster explanation beta"),
    )
    distractors = [
        _record(conn, conversation_id, f"mutually reinforcing obsolete clue-{index}")
        for index in range(hostile_edges)
    ]
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="escape cluster correction",
        anchors=tuple(item.event_id for item in anchors),
        required=(target.event_id,),
    )
    for index, distractor in enumerate(distractors):
        source = anchors[index % len(anchors)]
        _insert_association(
            conn,
            association_id=f"cluster-trap-{index:05d}",
            source_kind="EVENT",
            source=str(source.event_id),
            target_kind="EVENT",
            target=str(distractor.event_id),
            provenance_event_ids=(str(source.event_id), str(distractor.event_id)),
        )
    _insert_association(
        conn,
        association_id="z-cluster-correction-route",
        source_kind="TERM",
        source="escape",
        target_kind="EVENT",
        target=str(target.event_id),
        provenance_event_ids=(str(target.event_id),),
    )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    cross = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.CROSS_REFERENCE)
    rounds = []
    for round_index in range(3):
        rounds.append(
            _run_adaptive(
                conn,
                corpus,
                uncertainty=MemoryUncertainty.POSSIBLE_CONTRADICTION,
                telemetry=RetrievalTelemetry(
                    candidate_scores=(0.51, 0.49),
                    anchored_rounds=round_index,
                    support_gain=0.0 if round_index else None,
                ),
                method_suffix=f":round-{round_index + 1}",
            )
        )
    return _case(
        scenario_id="mutually_reinforcing_anchor_cluster_requires_reorientation",
        purpose="Test whether a bad multi-anchor cluster can be escaped after bounded non-improving exploitation instead of becoming a self-reinforcing attentional attractor.",
        observations=_as_observations(aperture, deeper, cross, *rounds),
        aperture_success=aperture.success,
    )


def _abstention_case(conn) -> dict[str, object]:
    """No ledger evidence supports the cue; successful retrieval should return none."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    for index in range(12):
        _record(conn, conversation_id, f"ordinary unrelated cooking note-{index}")
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="xylophone nebula insurance quaternion",
        anchors=(),
        required=(),
    )
    standard = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.STANDARD)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.MISSING_CONTEXT,
        telemetry=RetrievalTelemetry(candidate_scores=()),
    )
    observations = _as_observations(standard, adaptive)
    for item in observations:
        item["success"] = len(item["returned_event_ids"]) == 0
    return _case(
        scenario_id="unsupported_query_abstention",
        purpose="Verify that widening or reorienting attention does not manufacture historical support when the canonical ledger contains no evidence for the cue.",
        observations=observations,
        aperture_success=False,
        evaluation="no_historical_evidence_returned",
        notes="This case compares unanchored deliberate retrieval directly because an automatic aperture with active WorkingState would intentionally surface that active state even when no historical match exists.",
    )


def _packet_pressure_weak_clues_case(conn, distractors: int) -> dict[str, object]:
    """Several partial clues jointly matter while exact-looking distractors compete."""
    _reset_database(conn)
    conversation_id = _new_conversation(conn)
    clue_a = _record(conn, conversation_id, "RAVEN clue alpha mentioned the scheduler")
    clue_b = _record(conn, conversation_id, "RAVEN clue beta mentioned memory pressure")
    clue_c = _record(conn, conversation_id, "RAVEN clue gamma mentioned rollback")
    for index in range(distractors):
        _record(
            conn,
            conversation_id,
            f"RAVEN scheduler memory pressure rollback plausible distractor-{index}",
        )
    anchors = (
        _record(conn, conversation_id, "RAVEN scheduler discussion anchor"),
        _record(conn, conversation_id, "RAVEN rollback discussion anchor"),
    )
    corpus = _finalize_corpus(
        conn,
        conversation_id=conversation_id,
        query_text="RAVEN scheduler memory pressure rollback",
        anchors=tuple(item.event_id for item in anchors),
        required=(clue_a.event_id, clue_b.event_id, clue_c.event_id),
    )
    aperture = _run_aperture(conn, corpus)
    deeper = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.DEEPER_RESEARCH)
    cross = _run_frozen(conn, corpus, jit_memory.MemoryRecallProfile.CROSS_REFERENCE)
    adaptive = _run_adaptive(
        conn,
        corpus,
        uncertainty=MemoryUncertainty.AMBIGUOUS_CANDIDATES,
        telemetry=RetrievalTelemetry(candidate_scores=(0.26, 0.25, 0.25, 0.24)),
    )
    return _case(
        scenario_id="multiple_weak_clues_under_packet_pressure",
        purpose="Require several individually weaker memories while exact-looking distractors compete, exposing whether top-k ranking discards distributed evidence needed for synthesis.",
        observations=_as_observations(aperture, deeper, cross, adaptive),
        aperture_success=aperture.success,
        notes=f"Hostile exact-looking distractors: {distractors}",
    )


def run_comparison(*, stress: bool) -> dict[str, object]:
    conn = db.get_connection()
    try:
        database_name = _prepare_database(conn)
        hostile_edges = 1300 if stress else 1200
        weak_distractors = 18 if stress else 12
        cases = [
            _correction_pair_case(conn),
            _zero_overlap_bridge_case(conn),
            _false_short_true_long_case(conn),
            _multi_anchor_deep_case(conn),
            _single_anchor_reorientation_case(conn, hostile_edges),
            _multi_anchor_reorientation_case(conn, hostile_edges),
            _packet_pressure_weak_clues_case(conn, weak_distractors),
            _abstention_case(conn),
        ]
        return {
            "schema_version": 1,
            "benchmark_id": "MEM-ADAPT-002",
            "mode": "stress" if stress else "quick",
            "database": database_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_boundary": (
                "This benchmark evaluates whether the complete canonical evidence needed by "
                "a downstream stateless worker is surfaced. It does not award retrieval credit "
                "for interpreting corrections, causality, truth, or contradiction."
            ),
            "head_to_head": _head_to_head(cases),
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
        output = RESULTS_DIR / f"MEM-ADAPT-002_{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"benchmark_id": result["benchmark_id"], "mode": result["mode"], "head_to_head": result["head_to_head"], "output": str(output)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
