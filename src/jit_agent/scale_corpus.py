"""Deterministic large synthetic histories for Memory Kernel scale testing.

The small persona benchmarks remain the oracle-bearing source corpora. This
module expands one of those corpora with realistic but non-authoritative
synthetic distractors while preserving every oracle question and remapping all
IDs to stable UUIDs so the result can be loaded into PostgreSQL unchanged.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta
import json
from pathlib import Path
import random
import uuid
from typing import Any

_SCALE_NAMESPACE = uuid.UUID("485b7648-c53a-4d7f-af1b-3dfd35fb71f2")
DEFAULT_SEED = 20260820
DEFAULT_EVENT_COUNTS = (1_000, 10_000, 50_000)
DEFAULT_BASE_CORPORA = (
    "jordan_vale_v1.json",
    "avery_chen_v1.json",
    "morgan_reyes_v05_robustness.json",
)

_MUNDANE_TEMPLATES = (
    "Kitchen inventory note {i}: shelf {n} contains clean containers, towels, labels, and foil.",
    "Calendar reminder {i}: routine building maintenance is scheduled for room {n} next week.",
    "Receipt archive {i}: rice, soap, batteries, paper towels, and storage bags were listed for batch {n}.",
    "Weather log {i}: the afternoon temperature reading for station {n} was recorded during a routine check.",
    "Office note {i}: printer paper, pens, folders, and charger cables were counted in cabinet {n}.",
    "Household checklist {i}: laundry, dishes, recycling, and floor cleaning were recorded for cycle {n}.",
)

# These intentionally share vocabulary with benchmark questions without
# asserting the persona-specific fact being tested. They are sparse enough to
# model long-lived lexical interference without turning every query into a
# deliberately impossible nearest-neighbor problem.
_CONFUSABLE_TEMPLATES = (
    (
        "beverage",
        "Office supply note {i}: espresso cups, coffee filters, cappuccino stirrers, and green tea bags are stocked in cabinet {n}.",
        ("coffee supplies", "cabinet"),
    ),
    (
        "vehicle",
        "Parking log {i}: a Toyota Corolla, Ford Escape, Honda Civic, and delivery vehicle were noted near bay {n}.",
        ("parking log", "vehicle"),
    ),
    (
        "deposit",
        "Accounting exercise {i}: security deposit and pet deposit are example ledger labels for training case {n}.",
        ("accounting exercise", "deposit"),
    ),
    (
        "work",
        "Conference index {i}: Acme Design, Northstar Labs, Atlas, and Orion appear as sample organization or project labels in dataset {n}.",
        ("conference index", "project labels"),
    ),
    (
        "people",
        "Directory exercise {i}: Sarah Patel, Sarah Kimball, Priya Shah, and Morgan Lee are placeholder names assigned to room {n}.",
        ("directory exercise", "placeholder names"),
    ),
    (
        "location",
        "Travel catalog {i}: Portland, Spokane, Seattle, and Tacoma appear in route example {n}.",
        ("travel catalog", "route example"),
    ),
    (
        "appointment",
        "Calendar template {i}: dentist appointment and delivery reminder are example fields for schedule slot {n}.",
        ("calendar template", "schedule slot"),
    ),
    (
        "objects",
        "Inventory training note {i}: blue notebook, office shelf, and laptop charger are sample object labels for bin {n}.",
        ("inventory training", "object labels"),
    ),
)


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(_SCALE_NAMESPACE, value))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def load_document(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_scaled_document(
    base_document: dict[str, Any],
    *,
    target_event_count: int,
    seed: int = DEFAULT_SEED,
    confusable_every: int = 12,
) -> dict[str, Any]:
    """Return a deterministic UUID-safe scale corpus derived from one persona.

    Base events are preserved semantically and remain first in append order.
    Later distractor events simulate years of unrelated accumulated history,
    including sparse lexically confusable records. Oracle question references
    are remapped to the UUID IDs of the preserved base events.
    """
    if target_event_count < 1:
        raise ValueError("target_event_count must be >= 1")
    if confusable_every < 2:
        raise ValueError("confusable_every must be >= 2")

    document = deepcopy(base_document)
    base_events = document.get("events", [])
    if target_event_count < len(base_events):
        raise ValueError(
            f"target_event_count {target_event_count} is smaller than base event count {len(base_events)}"
        )

    persona_name = document["persona"]["name"]
    persona_key = persona_name.casefold().replace(" ", "-")
    rng = random.Random(seed)

    event_id_map: dict[str, str] = {}
    conversation_id_map: dict[str, str] = {}
    scaled_events: list[dict[str, Any]] = []

    for seq, raw in enumerate(base_events, start=1):
        original_event_id = str(raw["event_id"])
        original_conversation_id = str(raw["conversation_id"])
        event_id = _stable_uuid(f"{persona_key}:base-event:{original_event_id}")
        conversation_id = conversation_id_map.setdefault(
            original_conversation_id,
            _stable_uuid(f"{persona_key}:base-conversation:{original_conversation_id}"),
        )
        event_id_map[original_event_id] = event_id

        event = deepcopy(raw)
        event["event_id"] = event_id
        event["conversation_id"] = conversation_id
        event["global_seq"] = seq
        event["benchmark_origin_event_id"] = original_event_id
        scaled_events.append(event)

    if scaled_events:
        latest_time = max(_parse_time(event["created_at"]) for event in scaled_events)
    else:
        latest_time = datetime.fromisoformat("2026-01-01T00:00:00+00:00")

    noise_count = target_event_count - len(scaled_events)
    for noise_index in range(1, noise_count + 1):
        global_seq = len(base_events) + noise_index
        is_confusable = noise_index % confusable_every == 0
        bucket = rng.randint(1, 9_999)

        if is_confusable:
            category, template, entities = _CONFUSABLE_TEMPLATES[
                (noise_index // confusable_every - 1) % len(_CONFUSABLE_TEMPLATES)
            ]
            text = template.format(i=noise_index, n=bucket)
            payload_entities = list(entities)
            source = f"synthetic_{category}"
            event_type = "SYSTEM_EVENT"
        else:
            template = _MUNDANE_TEMPLATES[(noise_index - 1) % len(_MUNDANE_TEMPLATES)]
            text = template.format(i=noise_index, n=bucket)
            payload_entities = ["synthetic distractor"]
            source = "synthetic_background"
            event_type = "SYSTEM_EVENT"

        conversation_group = (noise_index - 1) // 10
        conversation_seq = (noise_index - 1) % 10 + 1
        conversation_id = _stable_uuid(
            f"{persona_key}:noise-conversation:{conversation_group}"
        )
        event_id = _stable_uuid(f"{persona_key}:noise-event:{noise_index}")
        created_at = latest_time + timedelta(minutes=noise_index)

        scaled_events.append(
            {
                "event_id": event_id,
                "global_seq": global_seq,
                "conversation_id": conversation_id,
                "conversation_seq": conversation_seq,
                "event_type": event_type,
                "source": source,
                "created_at": created_at.isoformat(),
                "text": text,
                "payload": {
                    "entities": payload_entities,
                    "synthetic_scale_distractor": True,
                    "distractor_kind": "confusable" if is_confusable else "background",
                },
            }
        )

    scaled_questions: list[dict[str, Any]] = []
    for raw_question in document.get("questions", []):
        question = deepcopy(raw_question)
        question["relevant_event_ids"] = [
            event_id_map[event_id]
            for event_id in raw_question.get("relevant_event_ids", [])
        ]
        question["required_event_ids"] = [
            event_id_map[event_id]
            for event_id in raw_question.get("required_event_ids", [])
        ]
        scaled_questions.append(question)

    document["benchmark_version"] = (
        f"{base_document.get('benchmark_version', 'synthetic-life')}-scale-v1"
    )
    document["events"] = scaled_events
    document["questions"] = scaled_questions
    document["scale"] = {
        "seed": seed,
        "target_event_count": target_event_count,
        "base_event_count": len(base_events),
        "distractor_event_count": noise_count,
        "confusable_every": confusable_every,
        "confusable_distractor_count": noise_count // confusable_every,
        "id_scheme": "uuid5",
    }
    return document


def write_scaled_document(
    base_path: str | Path,
    output_path: str | Path,
    *,
    target_event_count: int,
    seed: int = DEFAULT_SEED,
    confusable_every: int = 12,
) -> Path:
    document = build_scaled_document(
        load_document(base_path),
        target_event_count=target_event_count,
        seed=seed,
        confusable_every=confusable_every,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic large persona corpora for Memory Kernel scale testing."
    )
    parser.add_argument(
        "--events",
        type=int,
        nargs="+",
        default=list(DEFAULT_EVENT_COUNTS),
        help="Target event counts per persona (default: 1000 10000 50000).",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--confusable-every", type=int, default=12)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "benchmarks" / "generated",
    )
    parser.add_argument(
        "--base",
        nargs="*",
        default=list(DEFAULT_BASE_CORPORA),
        help="Base benchmark filenames under benchmarks/.",
    )
    args = parser.parse_args()

    benchmark_dir = Path(__file__).resolve().parents[2] / "benchmarks"
    for base_name in args.base:
        base_path = benchmark_dir / base_name
        for count in args.events:
            destination = args.output_dir / f"{base_path.stem}_scale_{count}.json"
            write_scaled_document(
                base_path,
                destination,
                target_event_count=count,
                seed=args.seed,
                confusable_every=args.confusable_every,
            )
            print(destination)


if __name__ == "__main__":
    main()
