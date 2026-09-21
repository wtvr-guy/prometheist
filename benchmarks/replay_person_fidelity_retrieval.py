"""Deterministic offline replay of person-fidelity evidence selection.

The native benchmark measures retrieval, Composer judgment, source policy, and
generation together. This replay isolates the first of those: given a frozen
fixture, which canonical life events does the deterministic kernel actually
deliver to the attention aperture for each probe?

It requires neither PostgreSQL nor Ollama, so a retrieval mechanism can be
characterized and regression-checked without spending a native run, and a
recorded native result can be checked for reproduction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from jit_agent.attention_aperture import DEFAULT_ATTENTION_APERTURE_LIMIT
from jit_agent.jit_memory import DEFAULT_EVIDENCE_TYPES, MINIMUM_SCORE
from jit_agent.memory_kernel import (
    POLICY_VERSION,
    CueState,
    MemoryEvent,
    recall,
    score_event,
)
from jit_agent.person_fidelity_benchmark import (
    FidelityProbe,
    PersonFidelityCorpus,
    chronological_life_events,
    deterministic_fixture_uuid,
    load_person_fidelity_corpus,
)
from jit_agent.response_policy import HistoricalEvidenceScope, source_types_for_scope


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks" / "person_fidelity_public_v1.json"
HOLDOUT_CORPUS = ROOT / "benchmarks" / "person_fidelity_holdout_v1.json"


def kernel_events(corpus: PersonFidelityCorpus) -> tuple[
    tuple[MemoryEvent, ...], dict[str, str]
]:
    """Rebuild the seeded ledger exactly as the native runner orders it."""

    events: list[MemoryEvent] = []
    fixture_by_event_id: dict[str, str] = {}
    for sequence, fixture in enumerate(chronological_life_events(corpus), start=1):
        event_id = str(deterministic_fixture_uuid(corpus, "event", fixture.event_id))
        conversation_id = str(
            deterministic_fixture_uuid(corpus, "conversation", fixture.conversation_id)
        )
        fixture_by_event_id[event_id] = fixture.event_id
        events.append(
            MemoryEvent(
                event_id=event_id,
                global_seq=sequence,
                conversation_id=conversation_id,
                conversation_seq=sequence,
                event_type=fixture.event_type.value,
                source=fixture.source,
                created_at=fixture.occurred_at,
                text=fixture.text,
                payload={**fixture.payload, "text": fixture.text},
            )
        )
    return tuple(events), fixture_by_event_id


def _aperture_cue(probe: FidelityProbe, source_types: tuple[str, ...]) -> CueState:
    """Mirror the aperture cue: current percept text only, no model-written query."""

    return CueState(
        query_text=probe.prompt,
        entities=(),
        reference_time=None,
        conversation_id=None,
        source_types=source_types,
        limit=DEFAULT_ATTENTION_APERTURE_LIMIT,
        minimum_score=MINIMUM_SCORE,
    )


def replay_probe(
    corpus: PersonFidelityCorpus,
    probe: FidelityProbe,
    *,
    scope: HistoricalEvidenceScope | None = None,
) -> dict[str, Any]:
    """Return the aperture packet and the complete score table for one probe."""

    events, fixture_by_event_id = kernel_events(corpus)
    allowed = (
        tuple(item.value for item in source_types_for_scope(scope))
        if scope is not None
        else tuple(item.value for item in DEFAULT_EVIDENCE_TYPES)
    )
    cue = _aperture_cue(probe, allowed)
    packet = recall(events, cue)
    delivered = [fixture_by_event_id[event.event_id] for event in packet.items]

    scores = []
    for event in events:
        components = score_event(event, cue)
        scores.append(
            {
                "fixture_id": fixture_by_event_id[event.event_id],
                "event_type": event.event_type,
                "source_allowed": event.event_type in set(allowed),
                "score": round(components.total, 6),
                "lexical": round(components.lexical, 6),
            }
        )
    scores.sort(key=lambda item: (-item["score"], item["fixture_id"]))

    required = set(probe.required_event_ids)
    delivered_set = set(delivered)
    unexpected = (
        sorted(delivered_set) if probe.expect_no_seeded_evidence else []
    )
    return {
        "probe_id": probe.probe_id,
        "dimension": probe.dimension.value,
        "evidence_scope": scope.value if scope is not None else "ALL_EVIDENCE_TYPES",
        "cue_token_count": len(set(packet.trace.cue_tokens)),
        "minimum_score": MINIMUM_SCORE,
        "aperture_limit": DEFAULT_ATTENTION_APERTURE_LIMIT,
        "delivered_fixture_ids": delivered,
        "required_fixture_ids": sorted(required),
        "missing_required": sorted(required - delivered_set),
        "unexpected_on_unknown_probe": unexpected,
        "retrieval_contract_met": (
            not (required - delivered_set) and not unexpected
        ),
        "all_event_scores": scores,
    }


def replay_corpus(
    corpus: PersonFidelityCorpus,
    *,
    scope: HistoricalEvidenceScope | None = None,
) -> dict[str, Any]:
    probes = [replay_probe(corpus, probe, scope=scope) for probe in corpus.probes]
    return {
        "benchmark_id": corpus.benchmark_id,
        "benchmark_version": corpus.benchmark_version,
        "fixture_sha256": corpus.fixture_sha256,
        "kernel_policy_version": POLICY_VERSION,
        "evidence_scope": scope.value if scope is not None else "ALL_EVIDENCE_TYPES",
        "retrieval_contract_met_count": sum(
            bool(item["retrieval_contract_met"]) for item in probes
        ),
        "probe_count": len(probes),
        "probes": probes,
    }


def compare_with_native_result(
    corpus: PersonFidelityCorpus,
    result_path: Path,
) -> dict[str, Any]:
    """Check that the offline replay reproduces a recorded native run's packets.

    The native run's own source policy is recovered from its recorded response
    source types, so a mismatch means retrieval is not reproducible offline
    rather than that the policy differed.
    """

    result = json.loads(result_path.read_text(encoding="utf-8"))
    probes_by_id = {probe.probe_id: probe for probe in corpus.probes}
    comparisons = []
    for recorded in result.get("probes", []):
        probe = probes_by_id.get(recorded["probe_id"])
        if probe is None:
            continue
        native = sorted(recorded["memory_retrieval"]["retrieved_fixture_event_ids"])
        best: dict[str, Any] | None = None
        for scope in (None, *HistoricalEvidenceScope):
            replayed = replay_probe(corpus, probe, scope=scope)
            if sorted(replayed["delivered_fixture_ids"]) == native:
                best = replayed
                break
            if best is None:
                best = replayed
        assert best is not None
        comparisons.append(
            {
                "probe_id": probe.probe_id,
                "native_retrieved": native,
                "replay_delivered": sorted(best["delivered_fixture_ids"]),
                "reproduced": sorted(best["delivered_fixture_ids"]) == native,
                "reproducing_scope": best["evidence_scope"],
            }
        )
    return {
        "result_artifact": result_path.as_posix(),
        "source_revision": result.get("revision"),
        "kernel_policy_version": POLICY_VERSION,
        "reproduced_count": sum(bool(item["reproduced"]) for item in comparisons),
        "probe_count": len(comparisons),
        "probes": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument(
        "--scope",
        choices=[scope.value for scope in HistoricalEvidenceScope],
        help="replay under one application source policy instead of all evidence types",
    )
    parser.add_argument(
        "--compare-result",
        type=Path,
        help="verify this replay reproduces a recorded native result's retrieval",
    )
    parser.add_argument("--summary", action="store_true", help="print a compact table")
    args = parser.parse_args()

    corpus_path = (
        HOLDOUT_CORPUS if args.holdout and args.corpus == DEFAULT_CORPUS else args.corpus
    )
    corpus = load_person_fidelity_corpus(corpus_path)

    if args.compare_result is not None:
        report = compare_with_native_result(corpus, args.compare_result)
        print(json.dumps(report, indent=2, sort_keys=True))
        if report["reproduced_count"] != report["probe_count"]:
            sys.exit(1)
        return

    scope = HistoricalEvidenceScope(args.scope) if args.scope else None
    report = replay_corpus(corpus, scope=scope)
    if args.summary:
        print(f"{report['benchmark_id']} scope={report['evidence_scope']}")
        for probe in report["probes"]:
            print(
                f"  {probe['probe_id']} "
                f"{'OK  ' if probe['retrieval_contract_met'] else 'FAIL'} "
                f"tokens={probe['cue_token_count']:>2} "
                f"delivered={probe['delivered_fixture_ids']} "
                f"missing={probe['missing_required']}"
                + (
                    f" unexpected={probe['unexpected_on_unknown_probe']}"
                    if probe["unexpected_on_unknown_probe"]
                    else ""
                )
            )
        print(
            f"  retrieval contract met: "
            f"{report['retrieval_contract_met_count']}/{report['probe_count']}"
        )
        return
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
