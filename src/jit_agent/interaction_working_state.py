"""Minimal durable active-situation state for stateless interaction continuity.

Working state is deliberately simple: it records which canonical events are
currently active. It does not parse natural language into an ever-growing set
of phrase-specific referents, labels, entities, or conclusions. Fresh workers
rehydrate those canonical events through JIT Memory, and semantic interpretation
remains a stateless inference concern rather than hard-coded application logic.
"""
from __future__ import annotations

from uuid import UUID, uuid5

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from jit_agent import event_store
from jit_agent.models import EventType, MemoryPacket
from jit_agent.response_policy import ResponsePolicy, filter_memory_packet_for_scope


WORKING_STATE_VERSION = "v0.7-working-state-v2"
SOURCE = "interaction_working_state"
MAX_ACTIVE_EVENT_IDS = 12


class InteractionWorkingState(BaseModel):
    """Bounded system-owned activation record for the current situation."""

    version: str = WORKING_STATE_VERSION
    state_id: UUID
    revision: int = Field(ge=1)
    conversation_ids: list[UUID] = Field(default_factory=list, max_length=16)
    active_event_ids: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_ACTIVE_EVENT_IDS,
    )


def deterministic_working_state_id(conversation_id: UUID) -> UUID:
    return uuid5(conversation_id, "interaction-working-state")


def deterministic_working_state_event_id(interaction_id: UUID, activation_key: str) -> UUID:
    return uuid5(interaction_id, f"working-state-event:{activation_key}")


def load_working_state(
    conn: psycopg.Connection,
    conversation_id: UUID,
) -> InteractionWorkingState | None:
    """Load the latest active state bound to the current interaction stream."""

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT payload
            FROM events
            WHERE event_type = %s
              AND (
                    conversation_id = %s
                    OR payload -> 'state' -> 'conversation_ids' ? %s
              )
            ORDER BY global_seq DESC
            LIMIT 1
            """,
            (
                EventType.INTERACTION_WORKING_STATE.value,
                conversation_id,
                str(conversation_id),
            ),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return InteractionWorkingState.model_validate(row["payload"]["state"])


def _linked_response_evidence_event_ids(
    conn: psycopg.Connection,
    event_id: UUID,
) -> list[UUID]:
    """Recover policy-admitted canonical evidence behind one persisted response.

    A generated response is canonical evidence of what Prometheist said, but it
    is not a substitute for the user/tool/system evidence that supported those
    words. Current finalized responses point to their terminal workpiece
    snapshot, which preserves both FINAL_EVIDENCE and FINAL_RESPONSE_DIRECTIVE.
    Re-activating those admitted source events keeps bounded WorkingState tied to
    the underlying authority instead of allowing accurate-or-inaccurate model
    restatements to become self-supporting memory.

    Historical/legacy response events without a workpiece link remain valid and
    simply contribute no additional anchors.
    """

    event = event_store.get_event_by_id(conn, event_id)
    if event is None or event.event_type is not EventType.INTERACTION_RESPONSE:
        return []

    raw_workpiece_event_id = event.payload.get("workpiece_event_id")
    if raw_workpiece_event_id is None:
        return []
    try:
        workpiece_event_id = UUID(str(raw_workpiece_event_id))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("response references an invalid workpiece event id") from exc

    workpiece_event = event_store.get_event_by_id(conn, workpiece_event_id)
    if workpiece_event is None:
        raise RuntimeError("response references a missing workpiece snapshot")
    if (
        workpiece_event.event_type is not EventType.SYSTEM_EVENT
        or workpiece_event.payload.get("kind") != "INTERACTION_WORKPIECE_SNAPSHOT"
    ):
        raise RuntimeError("response workpiece reference does not target a terminal snapshot")

    raw_workpiece = workpiece_event.payload.get("workpiece")
    if not isinstance(raw_workpiece, dict):
        raise RuntimeError("response workpiece snapshot has no workpiece payload")
    components = raw_workpiece.get("components")
    if not isinstance(components, list):
        raise RuntimeError("response workpiece snapshot has invalid components")

    final_evidence_components = [
        component
        for component in components
        if isinstance(component, dict)
        and component.get("component_type") == "FINAL_EVIDENCE"
    ]
    directive_components = [
        component
        for component in components
        if isinstance(component, dict)
        and component.get("component_type") == "FINAL_RESPONSE_DIRECTIVE"
    ]
    if len(final_evidence_components) != 1 or len(directive_components) != 1:
        raise RuntimeError("response workpiece snapshot has invalid final response components")

    final_packet = MemoryPacket.model_validate(
        final_evidence_components[0].get("memory_packet")
    )
    raw_directive = directive_components[0].get("directive")
    if not isinstance(raw_directive, dict):
        raise RuntimeError("response workpiece snapshot has invalid final directive")
    policy = ResponsePolicy.model_validate(raw_directive.get("response_policy"))
    admitted_packet = filter_memory_packet_for_scope(
        final_packet,
        policy.evidence_scope,
    )
    if admitted_packet is None:
        return []
    return [item.source_event_id for item in admitted_packet.items]


def _expand_activation_event_ids(
    conn: psycopg.Connection,
    event_ids: list[UUID],
) -> list[UUID]:
    """Keep each explicit activation adjacent to its canonical response anchors."""

    expanded: list[UUID] = []
    for event_id in event_ids:
        expanded.append(event_id)
        expanded.extend(_linked_response_evidence_event_ids(conn, event_id))
    return expanded


def activate_working_state(
    conn: psycopg.Connection,
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    activated_event_ids: list[UUID],
    activation_key: str = "response",
) -> InteractionWorkingState:
    """Promote canonical events into bounded active state.

    Each activation phase has a deterministic event ID. A retry of the same
    phase therefore returns the already-persisted revision instead of advancing
    state again. Distinct phases (for example `memory` and `response`) remain
    append-only revisions within the same interaction.

    When a finalized response is activated, its policy-admitted source events
    are deterministically re-activated beside it. This preserves source
    authority across natural conversational compression without storing a free-
    form summary or making model output authoritative.
    """

    event_id = deterministic_working_state_event_id(interaction_id, activation_key)
    existing = event_store.get_event_by_id(conn, event_id)
    if existing is not None:
        if existing.event_type is not EventType.INTERACTION_WORKING_STATE:
            raise RuntimeError("working-state activation id collides with another event type")
        return InteractionWorkingState.model_validate(existing.payload["state"])

    previous = load_working_state(conn, conversation_id)
    state_id = (
        previous.state_id
        if previous is not None
        else deterministic_working_state_id(conversation_id)
    )
    revision = 1 if previous is None else previous.revision + 1
    conversation_ids = _merge_uuid_lists(
        [conversation_id],
        previous.conversation_ids if previous is not None else [],
        16,
    )
    active_event_ids = _merge_uuid_lists(
        _expand_activation_event_ids(conn, activated_event_ids),
        previous.active_event_ids if previous is not None else [],
        MAX_ACTIVE_EVENT_IDS,
    )

    state = InteractionWorkingState(
        state_id=state_id,
        revision=revision,
        conversation_ids=conversation_ids,
        active_event_ids=active_event_ids,
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.INTERACTION_WORKING_STATE,
        source=SOURCE,
        payload={"activation_key": activation_key, "state": state.model_dump(mode="json")},
        event_id=event_id,
    )
    return state


def _merge_uuid_lists(first: list[UUID], second: list[UUID], limit: int) -> list[UUID]:
    merged: list[UUID] = []
    seen: set[UUID] = set()
    for value in [*first, *second]:
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)
        if len(merged) == limit:
            break
    return merged
