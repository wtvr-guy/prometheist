"""Scheduled derivation over repeated observations; never rewrite canonical history."""
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
from jit_agent.semantic_memory import record_semantic_evidence
from jit_agent.situations import Situation

DERIVATION_METHOD = "consolidation/v2"


def _record_page_semantic_evidence(
    conn: psycopg.Connection,
    by_percept: dict,
    *,
    asserted_at: datetime,
) -> list[dict]:
    """Persist each unique observation as evidence, independent of page shape.

    A storage page is only a bounded execution unit. It must never decide
    whether evidence is semantically admissible. Stable evidence identities
    deduplicate overlapping situation snapshots and repeated consolidation
    passes, while the semantic resolver compares observation time rather than
    page order.
    """

    updates: list[dict] = []
    for state in sorted(
        by_percept.values(),
        key=lambda item: (
            item.observation.subject,
            item.observation.property,
            item.observed_at,
            str(item.percept_id),
        ),
    ):
        observation = state.observation
        result = record_semantic_evidence(
            conn,
            subject=observation.subject,
            property=observation.property,
            value=observation.value,
            unit=observation.unit,
            confidence=observation.confidence,
            source_percept_id=state.percept_id,
            observed_at=state.observed_at,
            asserted_at=asserted_at,
            derivation_method=DERIVATION_METHOD,
        )
        updates.append(
            {
                "subject": observation.subject,
                "property": observation.property,
                "assertion_id": str(result.assertion.assertion_id),
                "evidence_id": str(result.evidence.evidence_id),
                "assertion_created": result.assertion_created,
                "evidence_created": result.evidence_created,
                "resolution_id": str(result.resolution.resolution_id),
                "resolution_status": result.resolution.status.value,
                "selected_assertion_id": (
                    str(result.resolution.selected_assertion_id)
                    if result.resolution.selected_assertion_id
                    else None
                ),
                "resolution_created": result.resolution_created,
            }
        )
    return updates


def consolidate_page(
    conn: psycopg.Connection,
    *,
    action_id: UUID,
    asserted_at: datetime,
    after_key: str = "",
) -> dict:
    """Process one bounded storage page without making the page epistemic."""

    aware(asserted_at)
    snapshots = list_records(conn, "situation_ingest", after_key=after_key)
    groups = defaultdict(dict)
    unique_states = {}

    for _key, data in snapshots:
        situation = Situation.model_validate(data)
        for state in situation.observed_state:
            observation = state.observation
            grouping_key = (observation.property, observation.unit)
            groups[grouping_key][state.percept_id] = state
            unique_states[
                (state.percept_id, observation.subject, observation.property)
            ] = state

    projections = []
    for (property_name, unit), by_percept in sorted(
        groups.items(), key=lambda item: str(item[0])
    ):
        values = defaultdict(list)
        for state in by_percept.values():
            values[json.dumps(state.observation.value, sort_keys=True)].append(
                str(state.percept_id)
            )
        projections.append(
            {
                "property": property_name,
                "unit": unit,
                "observed_values": [
                    {
                        "value": json.loads(value),
                        "support_percept_ids": refs,
                    }
                    for value, refs in sorted(values.items())
                ],
                "epistemic_status": "DERIVED",
                "scope": "BOUNDED_SITUATION_PAGE",
                "variation_present": len(values) > 1,
                "universal_claim": False,
                "subject_refs": sorted(
                    {
                        state.observation.subject
                        for state in by_percept.values()
                    }
                ),
            }
        )

    semantic_updates = _record_page_semantic_evidence(
        conn,
        {index: state for index, state in enumerate(unique_states.values())},
        asserted_at=asserted_at,
    )
    result = {
        "projections": projections,
        "source_snapshot_ids": [
            data["snapshot_id"] for _, data in snapshots
        ],
        "next_cursor": snapshots[-1][0] if snapshots else None,
        "canonical_records_modified": False,
        "semantic_updates": semantic_updates,
    }
    put_record(conn, "consolidation", str(action_id), result, revision="2")
    return result


class ConsolidationSchedule(FrozenRecord):
    schedule_id: UUID
    due_at: datetime
    after_key: str = ""


def schedule_consolidation(
    conn: psycopg.Connection, schedule: ConsolidationSchedule
) -> None:
    aware(schedule.due_at)
    put_record(
        conn,
        "consolidation_schedule",
        str(schedule.schedule_id),
        schedule.model_dump(mode="json"),
        revision="1",
    )


def emit_due_consolidations(
    conn: psycopg.Connection,
    *,
    now: datetime,
    after_key: str = "",
) -> str | None:
    """One scheduler poll page, safe to replay across process restarts."""

    aware(now)
    source_id = "scheduler:consolidation"
    install_source_policy(
        conn,
        SourcePolicy(
            source_id=source_id,
            kind=PerceptKind.SCHEDULED_EVENT,
            modalities=(PerceptModality.STRUCTURED,),
            deterministic_task=TaskClass.CONSOLIDATE,
            allowed_task_classes=(TaskClass.CONSOLIDATE,),
        ),
    )
    rows = list_records(conn, "consolidation_schedule", after_key=after_key)
    for key, data in rows:
        schedule = ConsolidationSchedule.model_validate(data)
        if schedule.due_at > now or get_record(conn, "schedule_delivery", key):
            continue
        percept = ingest_percept(
            conn,
            source=PerceptSource(
                source_id=source_id,
                kind=PerceptKind.SCHEDULED_EVENT,
                modality=PerceptModality.STRUCTURED,
                interface="scheduler",
            ),
            observation={
                "schedule_id": key,
                "after_key": schedule.after_key,
            },
            observed_at=schedule.due_at,
            delivery_id=key,
            correlation_id=schedule.schedule_id,
        )
        put_record(
            conn,
            "schedule_delivery",
            key,
            {"percept_id": str(percept.percept_id)},
            revision="1",
        )
    return rows[-1][0] if rows else None
