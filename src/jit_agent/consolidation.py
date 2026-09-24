"""Scheduled derivation of repeated observations; never rewrite canonical history."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from uuid import UUID

import psycopg

from jit_agent.cognitive_store import get_record, list_records, put_record
from jit_agent.percept_context import FrozenRecord, aware
from jit_agent.percept_intake import ingest_percept, install_source_policy
from jit_agent.perception import PerceptKind, PerceptModality, PerceptSource
from jit_agent.percept_triage import SourcePolicy, TaskClass
from jit_agent.semantic_memory import derive_semantic_fact
from jit_agent.situations import Situation

DERIVATION_METHOD = "consolidation/v1"


def _derive_page_semantic_facts(conn: psycopg.Connection, by_percept: dict) -> list[dict]:
    """Durable, per-subject beliefs for one (property, unit) group in this page.

    The projection this page also builds intentionally aggregates every
    subject sharing a property/unit within the bounded page (see the
    ``subject_refs`` field below); a durable belief must never blur two
    different subjects' evidence together, so this re-partitions by exact
    subject before deriving anything.
    """
    by_subject = defaultdict(list)
    for state in by_percept.values():
        by_subject[state.observation.subject].append(state)
    facts = []
    for subject, states in sorted(by_subject.items()):
        distinct_values = {json.dumps(state.observation.value, sort_keys=True) for state in states}
        if len(distinct_values) != 1:
            continue  # Ambiguous within this page; leave resolution to a later page or reflection.
        ordered = sorted(states, key=lambda state: (state.observed_at, str(state.percept_id)))
        latest = ordered[-1]
        result = derive_semantic_fact(
            conn, subject=subject, property=latest.observation.property, value=latest.observation.value,
            unit=latest.observation.unit, confidence=min(state.observation.confidence for state in states),
            # Every state here came from this one bounded, HEAD_PAGE_SIZE-limited
            # page, so this is always within SemanticFact.derived_from's bound.
            derived_from=tuple(state.percept_id for state in ordered),
            observed_at=latest.observed_at, asserted_at=latest.observed_at,
            derivation_method=DERIVATION_METHOD,
        )
        if result.created:
            facts.append({
                "subject": subject, "property": latest.observation.property,
                "fact_id": str(result.fact.fact_id), "relation": result.fact.relation.value,
            })
    return facts


def consolidate_page(conn: psycopg.Connection, *, action_id: UUID, after_key: str = "") -> dict:
    """One bounded page. The next cursor is durably scheduled by the caller."""
    snapshots = list_records(conn, "situation_ingest", after_key=after_key)
    groups = defaultdict(dict)
    for _key, data in snapshots:
        situation = Situation.model_validate(data)
        for state in situation.observed_state:
            observation = state.observation
            key = (observation.property, observation.unit)
            # Overlapping situations cannot count the same percept twice.
            groups[key][state.percept_id] = state
    projections = []
    semantic_facts = []
    for (property_name, unit), by_percept in sorted(groups.items(), key=lambda item: str(item[0])):
        values = defaultdict(list)
        for state in by_percept.values():
            values[json.dumps(state.observation.value, sort_keys=True)].append(str(state.percept_id))
        projections.append({"property": property_name, "unit": unit,
                            "observed_values": [{"value": json.loads(value), "support_percept_ids": refs}
                                                for value, refs in sorted(values.items())],
                            "epistemic_status": "DERIVED", "scope": "BOUNDED_SITUATION_PAGE",
                            "variation_present": len(values) > 1, "universal_claim": False,
                            "subject_refs": sorted({state.observation.subject for state in by_percept.values()})})
        semantic_facts.extend(_derive_page_semantic_facts(conn, by_percept))
    result = {"projections": projections, "source_snapshot_ids": [data["snapshot_id"] for _, data in snapshots],
              "next_cursor": snapshots[-1][0] if snapshots else None,
              "canonical_records_modified": False, "semantic_facts": semantic_facts}
    put_record(conn, "consolidation", str(action_id), result, revision="1")
    return result


class ConsolidationSchedule(FrozenRecord):
    schedule_id: UUID
    due_at: datetime
    after_key: str = ""


def schedule_consolidation(conn: psycopg.Connection, schedule: ConsolidationSchedule) -> None:
    aware(schedule.due_at)
    put_record(conn, "consolidation_schedule", str(schedule.schedule_id), schedule.model_dump(mode="json"), revision="1")


def emit_due_consolidations(conn: psycopg.Connection, *, now: datetime, after_key: str = "") -> str | None:
    """One scheduler poll page, safe to replay across process restarts."""
    aware(now)
    source_id = "scheduler:consolidation"
    install_source_policy(conn, SourcePolicy(
        source_id=source_id, kind=PerceptKind.SCHEDULED_EVENT, modalities=(PerceptModality.STRUCTURED,),
        deterministic_task=TaskClass.CONSOLIDATE, allowed_task_classes=(TaskClass.CONSOLIDATE,),
    ))
    rows = list_records(conn, "consolidation_schedule", after_key=after_key)
    for key, data in rows:
        schedule = ConsolidationSchedule.model_validate(data)
        if schedule.due_at > now or get_record(conn, "schedule_delivery", key):
            continue
        percept = ingest_percept(
            conn, source=PerceptSource(source_id=source_id, kind=PerceptKind.SCHEDULED_EVENT,
                                       modality=PerceptModality.STRUCTURED, interface="scheduler"),
            observation={"schedule_id": key, "after_key": schedule.after_key}, observed_at=schedule.due_at,
            delivery_id=key, correlation_id=schedule.schedule_id,
        )
        put_record(conn, "schedule_delivery", key, {"percept_id": str(percept.percept_id)}, revision="1")
    return rows[-1][0] if rows else None
