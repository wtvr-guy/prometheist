from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from benchmarks import run_person_fidelity_baseline as native_runner
from jit_agent.person_fidelity_benchmark import (
    REQUIRED_BASELINE_DIMENSIONS,
    canonical_seed_payload,
    chronological_life_events,
    deterministic_fixture_uuid,
    evaluate_structural_probe,
    fixture_digest,
    load_person_fidelity_corpus,
    successful_response_realization,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "benchmarks" / "person_fidelity_public_v1.json"


def _corpus():
    return load_person_fidelity_corpus(CORPUS_PATH)


def _event_ids(corpus):
    return {
        event.event_id: deterministic_fixture_uuid(corpus, "event", event.event_id)
        for event in corpus.life_events
    }


def test_frozen_person_fidelity_fixture_is_complete_and_digest_verified():
    corpus = _corpus()

    assert corpus.subject.fictional is True
    assert {probe.dimension for probe in corpus.probes} == REQUIRED_BASELINE_DIMENSIONS
    assert any(probe.expect_no_seeded_evidence for probe in corpus.probes)
    assert any(len(probe.required_event_ids) >= 3 for probe in corpus.probes)
    ordered = chronological_life_events(corpus)
    assert [event.occurred_at for event in ordered] == sorted(
        event.occurred_at for event in corpus.life_events
    )


def test_fixture_digest_fails_closed_on_unversioned_oracle_or_stimulus_change():
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    tampered = deepcopy(document)
    tampered["probes"][0]["human_oracle"]["reference_outcome"] += " Tampered."

    assert fixture_digest(document) == document["fixture_sha256"]
    assert fixture_digest(tampered) != document["fixture_sha256"]


def test_canonical_seed_payload_cannot_leak_probe_or_human_oracle():
    corpus = _corpus()
    for event in corpus.life_events:
        payload = canonical_seed_payload(corpus, event)
        serialized = json.dumps(payload, sort_keys=True)

        assert payload["text"] == event.text
        assert payload["benchmark_fixture"]["fixture_event_id"] == event.event_id
        assert "human_oracle" not in serialized
        assert "reference_outcome" not in serialized
        assert "faithful_elements" not in serialized
        assert all(probe.prompt not in serialized for probe in corpus.probes)


def test_structural_pass_proves_evidence_delivery_not_semantic_fidelity():
    corpus = _corpus()
    probe = corpus.probes[0]
    event_ids = _event_ids(corpus)
    admitted = [f"event:{event_ids[event_id]}" for event_id in probe.required_event_ids]

    result = evaluate_structural_probe(
        corpus,
        probe,
        event_ids_by_fixture=event_ids,
        response_text="This answer can be semantically wrong and still have a valid receipt.",
        artifact_chain_valid=True,
        artifact_chain_complete=True,
        admitted_evidence_refs=admitted,
    )

    assert result.passed is True
    assert result.missing_required_refs == ()


def test_structural_evaluation_rejects_missing_and_unknown_case_evidence():
    corpus = _corpus()
    event_ids = _event_ids(corpus)
    answerable = corpus.probes[0]
    unknown = next(probe for probe in corpus.probes if probe.expect_no_seeded_evidence)

    missing = evaluate_structural_probe(
        corpus,
        answerable,
        event_ids_by_fixture=event_ids,
        response_text="Non-empty",
        artifact_chain_valid=True,
        artifact_chain_complete=True,
        admitted_evidence_refs=[],
    )
    unexpected = evaluate_structural_probe(
        corpus,
        unknown,
        event_ids_by_fixture=event_ids,
        response_text="I do not know.",
        artifact_chain_valid=True,
        artifact_chain_complete=True,
        admitted_evidence_refs=[f"event:{next(iter(event_ids.values()))}"],
    )

    assert missing.passed is False
    assert missing.missing_required_refs
    assert unexpected.passed is False
    assert unexpected.unexpected_seeded_refs


def test_response_realization_selects_only_last_successful_response_artifact():
    artifacts = [
        {
            "artifact_id": "wrong-stage",
            "artifact_type": "LLM_INVOCATION",
            "stage": "V2_COMPOSE_MEMORY",
            "payload": {"kind": "FINAL_RESPONSE_V2", "output": "ignored"},
        },
        {
            "artifact_id": "failed",
            "artifact_type": "LLM_INVOCATION",
            "stage": "V2_RESPOND",
            "payload": {
                "kind": "FINAL_RESPONSE_V2",
                "output": None,
                "error_type": "RuntimeError",
            },
        },
        {
            "artifact_id": "selected",
            "artifact_type": "LLM_INVOCATION",
            "stage": "V2_RESPOND",
            "payload": {
                "kind": "FINAL_RESPONSE_V2",
                "output": "response",
                "error_type": None,
            },
        },
    ]

    assert successful_response_realization(artifacts)["artifact_id"] == "selected"


def test_loader_rejects_a_changed_fixture_without_an_explicit_new_digest(tmp_path):
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    document["life_events"][0]["text"] += " Changed without versioning."
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="fixture digest mismatch"):
        load_person_fidelity_corpus(path)


def test_native_result_writer_never_overwrites_prior_evidence(tmp_path):
    path = tmp_path / "result.json"
    native_runner._write_result(path, {"result": "baseline"})

    with pytest.raises(FileExistsError):
        native_runner._write_result(path, {"result": "replacement"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"result": "baseline"}
