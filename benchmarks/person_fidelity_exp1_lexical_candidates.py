"""Reproducible rejected scorers from person-fidelity Experiment 1.

These scorers are experimental evidence, not production retrieval code.  The
module intentionally owns the complete candidate definitions and emits a
machine-readable comparison so a negative result does not depend on prose alone.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks import replay_person_fidelity_retrieval as replay  # noqa: E402
from prometheist.jit_memory import MINIMUM_SCORE  # noqa: E402
from prometheist.memory_kernel import LEXICAL_WEIGHT, MemoryEvent, tokenize  # noqa: E402
from prometheist.person_fidelity_benchmark import (  # noqa: E402
    FidelityProbe,
    PersonFidelityCorpus,
)


RESULT_PATH = (
    ROOT
    / "benchmarks"
    / "results"
    / "PERSON-FIDELITY-EXP1-LEXICAL-RELEVANCE.json"
)
EXPERIMENT_VERSION = "person-fidelity-exp1-lexical-candidates-v1"


ScoreFunction = Callable[[str, MemoryEvent, tuple[MemoryEvent, ...]], float]


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    description: str
    formula: str
    score: ScoreFunction


def _query_terms(query: str) -> set[str]:
    return set(tokenize(query))


def _event_terms(event: MemoryEvent) -> set[str]:
    return set(tokenize(event.text))


def _document_frequencies(events: tuple[MemoryEvent, ...]) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for event in events:
        frequencies.update(_event_terms(event))
    return frequencies


def _smooth_idf(term: str, events: tuple[MemoryEvent, ...]) -> float:
    """Frozen Robertson-style positive IDF used by the experiment."""

    frequencies = _document_frequencies(events)
    document_count = len(events)
    frequency = frequencies.get(term, 0)
    return math.log(1.0 + (document_count - frequency + 0.5) / (frequency + 0.5))


def _uniform_coverage(
    query: str,
    event: MemoryEvent,
    _events: tuple[MemoryEvent, ...],
) -> float:
    query_terms = _query_terms(query)
    if not query_terms:
        return 0.0
    return len(query_terms & _event_terms(event)) / len(query_terms)


def _idf_coverage(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    query_terms = _query_terms(query)
    if not query_terms:
        return 0.0
    weights = {term: _smooth_idf(term, events) for term in query_terms}
    denominator = sum(weights.values())
    matched = query_terms & _event_terms(event)
    return sum(weights[term] for term in matched) / denominator if denominator else 0.0


def _idf_cosine(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    query_terms = _query_terms(query)
    event_terms = _event_terms(event)
    if not query_terms or not event_terms:
        return 0.0
    vocabulary = query_terms | event_terms
    weights = {term: _smooth_idf(term, events) for term in vocabulary}
    numerator = sum(weights[term] ** 2 for term in query_terms & event_terms)
    query_norm = math.sqrt(sum(weights[term] ** 2 for term in query_terms))
    event_norm = math.sqrt(sum(weights[term] ** 2 for term in event_terms))
    return numerator / (query_norm * event_norm) if query_norm and event_norm else 0.0


def _saturated_matched_mass(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    matched = _query_terms(query) & _event_terms(event)
    mass = sum(_smooth_idf(term, events) for term in matched)
    return 1.0 - math.exp(-mass)


def _bm25(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    """BM25 followed by a bounded monotone saturation for the 0..1 kernel."""

    query_terms = _query_terms(query)
    event_tokens = tokenize(event.text)
    if not query_terms or not event_tokens:
        return 0.0
    frequencies = Counter(event_tokens)
    average_length = sum(len(tokenize(item.text)) for item in events) / len(events)
    k1 = 1.2
    b = 0.75
    raw = 0.0
    for term in query_terms:
        frequency = frequencies.get(term, 0)
        if not frequency:
            continue
        denominator = frequency + k1 * (
            1.0 - b + b * len(event_tokens) / average_length
        )
        raw += _smooth_idf(term, events) * frequency * (k1 + 1.0) / denominator
    return raw / (1.0 + raw)


_LOW_SALIENCY_TERMS = frozenset(
    {
        "about",
        "after",
        "all",
        "already",
        "am",
        "any",
        "because",
        "before",
        "could",
        "get",
        "give",
        "how",
        "if",
        "into",
        "like",
        "make",
        "most",
        "now",
        "probably",
        "really",
        "say",
        "than",
        "then",
        "think",
        "used",
        "would",
    }
)


def _damped_query_mass(
    query: str,
    event: MemoryEvent,
    _events: tuple[MemoryEvent, ...],
    *,
    exponent: float,
    low_saliency_weight: float = 1.0,
) -> float:
    query_terms = _query_terms(query)
    if not query_terms:
        return 0.0
    weights = {
        term: low_saliency_weight if term in _LOW_SALIENCY_TERMS else 1.0
        for term in query_terms
    }
    matched_mass = sum(
        weights[term] for term in query_terms & _event_terms(event)
    )
    query_mass = sum(weights.values())
    return min(1.0, matched_mass / (query_mass**exponent))


def _saliency_damped(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    return _damped_query_mass(
        query,
        event,
        events,
        exponent=0.5,
        low_saliency_weight=0.2,
    )


def _damped_p05(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    return _damped_query_mass(query, event, events, exponent=0.5)


def _damped_p07(
    query: str,
    event: MemoryEvent,
    events: tuple[MemoryEvent, ...],
) -> float:
    return _damped_query_mass(query, event, events, exponent=0.7)


CANDIDATES = (
    Candidate(
        "uniform_query_coverage",
        "Current uniform unique-query-token coverage.",
        "|Q ∩ D| / |Q|",
        _uniform_coverage,
    ),
    Candidate(
        "ledger_idf_coverage",
        "Positive ledger-IDF weighted query-token coverage.",
        "Σ IDF(Q ∩ D) / Σ IDF(Q)",
        _idf_coverage,
    ),
    Candidate(
        "idf_cosine",
        "Binary TF-IDF cosine with query and event normalization.",
        "Σ IDF(t)^2 / (||Q|| × ||D||)",
        _idf_cosine,
    ),
    Candidate(
        "saturated_matched_mass",
        "Absolute matched-IDF mass with monotone saturation.",
        "1 - exp(-Σ IDF(Q ∩ D))",
        _saturated_matched_mass,
    ),
    Candidate(
        "bm25",
        "Robertson-IDF BM25 with pivoted event-length normalization.",
        "BM25(k1=1.2,b=0.75) / (1 + BM25)",
        _bm25,
    ),
    Candidate(
        "general_saliency_damped_p05",
        "Frozen general-English low-saliency tier plus damped query mass.",
        "matched weighted mass / query weighted mass^0.5; low tier=0.2",
        _saliency_damped,
    ),
    Candidate(
        "damped_query_mass_p05",
        "Uniform matched-token mass with damped query-length normalization.",
        "|Q ∩ D| / |Q|^0.5",
        _damped_p05,
    ),
)


def _ranked_event_ids(
    probe: FidelityProbe,
    events: tuple[MemoryEvent, ...],
    candidate: Candidate,
    *,
    cutoff: float,
    limit: int = 6,
) -> list[str]:
    scored = [
        (event, LEXICAL_WEIGHT * candidate.score(probe.prompt, event, events))
        for event in events
    ]
    admitted = [(event, score) for event, score in scored if score >= cutoff]
    admitted.sort(key=lambda item: (-item[1], item[0].event_id))

    ranked: list[MemoryEvent] = []
    index = 0
    while index < len(admitted):
        score = admitted[index][1]
        tied: deque[MemoryEvent] = deque()
        while index < len(admitted) and admitted[index][1] == score:
            tied.append(admitted[index][0])
            index += 1
        tied = deque(sorted(tied, key=lambda item: (item.global_seq, item.event_id)))
        take_newest = True
        while tied:
            ranked.append(tied.pop() if take_newest else tied.popleft())
            take_newest = not take_newest
    return [event.event_id for event in ranked[:limit]]


def evaluate_candidate(
    corpus: PersonFidelityCorpus,
    candidate: Candidate,
    *,
    cutoff: float = MINIMUM_SCORE,
) -> dict[str, object]:
    events, fixture_by_event_id = replay.kernel_events(corpus)
    probes = []
    for probe in corpus.probes:
        delivered_event_ids = _ranked_event_ids(
            probe,
            events,
            candidate,
            cutoff=cutoff,
        )
        delivered = [fixture_by_event_id[event_id] for event_id in delivered_event_ids]
        delivered_set = set(delivered)
        required = set(probe.required_event_ids)
        missing = sorted(required - delivered_set)
        noise = sorted(delivered_set - required)
        met = not missing and not (delivered if probe.expect_no_seeded_evidence else [])
        probes.append(
            {
                "probe_id": probe.probe_id,
                "delivered_fixture_ids": delivered,
                "missing_required": missing,
                "noise_fixture_ids": noise,
                "retrieval_contract_met": met,
            }
        )
    return {
        "candidate_id": candidate.candidate_id,
        "description": candidate.description,
        "formula": candidate.formula,
        "cutoff": cutoff,
        "retrieval_contract_met_count": sum(
            bool(probe["retrieval_contract_met"]) for probe in probes
        ),
        "noise_admitted": sum(len(probe["noise_fixture_ids"]) for probe in probes),
        "total_admitted": sum(len(probe["delivered_fixture_ids"]) for probe in probes),
        "unknown_probe_clean": not probes[-1]["delivered_fixture_ids"],
        "probes": probes,
    }


def build_report() -> dict[str, object]:
    baseline = replay.load_person_fidelity_corpus(replay.DEFAULT_CORPUS)
    holdout = replay.load_person_fidelity_corpus(replay.HOLDOUT_CORPUS)
    candidate_results = [
        evaluate_candidate(baseline, candidate) for candidate in CANDIDATES
    ]
    cutoff_controls = [
        evaluate_candidate(baseline, CANDIDATES[0], cutoff=cutoff)
        for cutoff in (0.15, 0.07, 0.03, 0.02)
    ]
    damped_controls = [
        evaluate_candidate(
            baseline,
            Candidate(
                f"damped_query_mass_p{str(exponent).replace('.', '')}",
                "Uniform damped query mass control.",
                f"|Q ∩ D| / |Q|^{exponent}",
                score,
            ),
        )
        for exponent, score in ((0.7, _damped_p07), (0.5, _damped_p05))
    ]
    report: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": "PERSON-FIDELITY-EXP1-LEXICAL-RELEVANCE",
        "experiment_version": EXPERIMENT_VERSION,
        "status": "REJECTED_INSUFFICIENT_DISCRIMINATION",
        "production_changed": False,
        "reconstruction_recorded_on": "2026-09-21",
        "fixtures": {
            baseline.benchmark_id: baseline.fixture_sha256,
            holdout.benchmark_id: holdout.fixture_sha256,
        },
        "fixed_policy": {
            "lexical_weight": LEXICAL_WEIGHT,
            "minimum_score": MINIMUM_SCORE,
            "packet_limit": 6,
        },
        "baseline_candidates": candidate_results,
        "cutoff_controls": cutoff_controls,
        "damped_controls": damped_controls,
        "holdout_null": evaluate_candidate(holdout, CANDIDATES[0]),
        "conclusions": [
            "Pure lexical overlap cannot retrieve required zero-overlap evidence.",
            "Higher admission volume does not by itself establish better discrimination.",
            "No tested candidate satisfies the frozen promotion rule.",
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


def write_report(path: Path = RESULT_PATH) -> dict[str, object]:
    report = build_report()
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _summary(report: dict[str, object]) -> Iterable[str]:
    yield str(report["experiment_id"])
    for result in report["baseline_candidates"]:  # type: ignore[union-attr]
        yield (
            f"  {result['candidate_id']}: "
            f"{result['retrieval_contract_met_count']}/10; "
            f"noise={result['noise_admitted']}; admitted={result['total_admitted']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the frozen JSON result")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    report = write_report() if args.write else build_report()
    if args.summary:
        print("\n".join(_summary(report)))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
