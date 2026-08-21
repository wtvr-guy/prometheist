import uuid
from pathlib import Path

import pytest

from jit_agent.scale_corpus import build_scaled_document, load_document


ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS = ROOT / "benchmarks"


@pytest.mark.parametrize(
    "filename",
    [
        "jordan_vale_v1.json",
        "avery_chen_v1.json",
        "morgan_reyes_v05_robustness.json",
    ],
)
def test_scaled_corpus_is_uuid_safe_and_preserves_oracle_references(filename):
    base = load_document(BENCHMARKS / filename)
    scaled = build_scaled_document(base, target_event_count=250)

    assert len(scaled["events"]) == 250
    event_ids = {event["event_id"] for event in scaled["events"]}
    conversation_ids = {event["conversation_id"] for event in scaled["events"]}

    assert len(event_ids) == 250
    assert all(str(uuid.UUID(event_id)) == event_id for event_id in event_ids)
    assert all(str(uuid.UUID(conversation_id)) == conversation_id for conversation_id in conversation_ids)

    for question in scaled["questions"]:
        assert set(question.get("required_event_ids", ())).issubset(event_ids)
        assert set(question.get("relevant_event_ids", ())).issubset(event_ids)

    base_text_by_id = {event["event_id"]: event["text"] for event in base["events"]}
    preserved = {
        event["benchmark_origin_event_id"]: event["text"]
        for event in scaled["events"]
        if "benchmark_origin_event_id" in event
    }
    assert preserved == base_text_by_id


def test_scaled_corpus_is_deterministic_and_prefix_stable():
    base = load_document(BENCHMARKS / "morgan_reyes_v05_robustness.json")

    first = build_scaled_document(base, target_event_count=300, seed=1234)
    second = build_scaled_document(base, target_event_count=300, seed=1234)
    larger = build_scaled_document(base, target_event_count=500, seed=1234)

    assert first == second
    assert first["events"] == larger["events"][:300]
    assert first["questions"] == larger["questions"]


def test_scaled_corpus_records_noise_profile():
    base = load_document(BENCHMARKS / "avery_chen_v1.json")
    scaled = build_scaled_document(
        base,
        target_event_count=130,
        seed=99,
        confusable_every=12,
    )

    noise_count = 130 - len(base["events"])
    assert scaled["scale"]["distractor_event_count"] == noise_count
    assert scaled["scale"]["confusable_distractor_count"] == noise_count // 12
    assert scaled["scale"]["id_scheme"] == "uuid5"
