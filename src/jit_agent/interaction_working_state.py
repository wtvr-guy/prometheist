"""Minimal durable active-situation state for stateless interaction continuity.

This is not long-term memory and it is not a free-form model summary.  It is a
small system-owned activation record that says which canonical events,
referents, options, entities, and recent conclusions are currently relevant to
an interaction situation.  Canonical event content remains authoritative and is
rehydrated through JIT Memory when a fresh worker needs it.
"""
from __future__ import annotations

import re
from uuid import UUID, uuid5

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from jit_agent import event_store
from jit_agent.models import EventType, MemoryPacket


WORKING_STATE_VERSION = "v0.7-working-state-v1"
SOURCE = "interaction_working_state"
_MAX_ACTIVE_EVENT_IDS = 12
_MAX_ENTITIES = 8
_MAX_OPTIONS = 6
_MAX_CONCLUSIONS = 6

_PROJECT_RE = re.compile(r"\bProject\s+([A-Z][A-Za-z0-9_-]+)\b")
_PLAN_NICKNAME_RE = re.compile(
    r"\bcall\s+the\s+plan\s+([A-Za-z][A-Za-z0-9_-]{2,})\b",
    re.IGNORECASE,
)
_BETWEEN_RE = re.compile(
    r"\b(?:choosing|choose|deciding|decide)\s+between\s+(.{1,120}?)\s+and\s+(.{1,120}?)(?:[.,;!?]|$)",
    re.IGNORECASE,
)
_RULED_OUT_RE = re.compile(
    r"\b(?:conflicts?|violates?|prohibit(?:ed|s)?|rules?\s+out|ruled\s+out|never\s+use)\b",
    re.IGNORECASE,
)


class WorkingConclusion(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    supporting_event_ids: list[UUID] = Field(default_factory=list, max_length=12)


class InteractionWorkingState(BaseModel):
    """Bounded active situation representation owned by Prometheist itself."""

    version: str = WORKING_STATE_VERSION
    state_id: UUID
    revision: int = Field(ge=1)
    conversation_ids: list[UUID] = Field(default_factory=list, max_length=16)
    active_entities: list[str] = Field(default_factory=list, max_length=_MAX_ENTITIES)
    active_options: list[str] = Field(default_factory=list, max_length=_MAX_OPTIONS)
    referents: dict[str, str] = Field(default_factory=dict)
    recent_conclusions: list[WorkingConclusion] = Field(
        default_factory=list,
        max_length=_MAX_CONCLUSIONS,
    )
    active_event_ids: list[UUID] = Field(default_factory=list, max_length=_MAX_ACTIVE_EVENT_IDS)


def deterministic_working_state_id(conversation_id: UUID) -> UUID:
    """Create the initial situation identity without assigning identity to a worker."""

    return uuid5(conversation_id, "interaction-working-state")


def deterministic_working_state_event_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "working-state-event")


def load_working_state(
    conn: psycopg.Connection,
    conversation_id: UUID,
) -> InteractionWorkingState | None:
    """Load the latest active situation bound to this interaction stream.

    Conversation identity is used only as a durable binding to the currently
    active situation.  The state itself carries a list of conversation IDs so a
    later situation-assembly milestone can rebind the same state across streams
    without changing this contract.
    """

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


def working_state_memory_cue(state: InteractionWorkingState | None) -> str | None:
    """Return a compact deterministic lexical cue for fallback routing only."""

    if state is None:
        return None
    parts: list[str] = []
    nickname = state.referents.get("plan_nickname")
    if nickname:
        parts.append(nickname)
    parts.extend(state.active_entities)
    parts.extend(state.active_options)
    if state.recent_conclusions:
        parts.append(state.recent_conclusions[-1].subject)
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = " ".join(part.split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            deduped.append(normalized)
    return " ".join(deduped) or None


def update_working_state(
    conn: psycopg.Connection,
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    user_prompt_event_id: UUID,
    response_event_id: UUID,
    user_text: str,
    response_text: str,
    memory_packet: MemoryPacket | None,
) -> InteractionWorkingState:
    """Persist one deterministic revision after an interaction completes."""

    previous = load_working_state(conn, conversation_id)
    if previous is None:
        state_id = deterministic_working_state_id(conversation_id)
        revision = 1
        conversation_ids = [conversation_id]
        active_entities: list[str] = []
        active_options: list[str] = []
        referents: dict[str, str] = {}
        conclusions: list[WorkingConclusion] = []
        previous_event_ids: list[UUID] = []
    else:
        state_id = previous.state_id
        revision = previous.revision + 1
        conversation_ids = _merge_uuid_lists(previous.conversation_ids, [conversation_id], 16)
        active_entities = list(previous.active_entities)
        active_options = list(previous.active_options)
        referents = dict(previous.referents)
        conclusions = list(previous.recent_conclusions)
        previous_event_ids = list(previous.active_event_ids)

    project_matches = [match.group(1) for match in _PROJECT_RE.finditer(user_text)]
    active_entities = _merge_text_lists(project_matches, active_entities, _MAX_ENTITIES)

    nickname_match = _PLAN_NICKNAME_RE.search(user_text)
    if nickname_match:
        referents["plan_nickname"] = nickname_match.group(1)

    between_match = _BETWEEN_RE.search(user_text)
    if between_match:
        options = [_clean_option(between_match.group(1)), _clean_option(between_match.group(2))]
        active_options = _merge_text_lists(options, active_options, _MAX_OPTIONS)

    memory_event_ids = (
        [item.source_event_id for item in memory_packet.items]
        if memory_packet is not None
        else []
    )
    current_support = _merge_uuid_lists(
        memory_event_ids,
        [user_prompt_event_id, response_event_id],
        _MAX_ACTIVE_EVENT_IDS,
    )
    active_event_ids = _merge_uuid_lists(
        current_support,
        previous_event_ids,
        _MAX_ACTIVE_EVENT_IDS,
    )

    if _RULED_OUT_RE.search(response_text):
        for option in active_options:
            if option.casefold() in response_text.casefold() or (
                option.casefold().startswith("docker")
                and "docker" in response_text.casefold()
            ):
                conclusion = WorkingConclusion(
                    subject=option,
                    predicate="RULED_OUT",
                    supporting_event_ids=_merge_uuid_lists(
                        [response_event_id],
                        memory_event_ids,
                        _MAX_ACTIVE_EVENT_IDS,
                    ),
                )
                conclusions = [
                    existing
                    for existing in conclusions
                    if not (
                        existing.subject.casefold() == option.casefold()
                        and existing.predicate == "RULED_OUT"
                    )
                ]
                conclusions.append(conclusion)
                conclusions = conclusions[-_MAX_CONCLUSIONS:]
                referents["recent_ruled_out_option"] = option
                break

    state = InteractionWorkingState(
        state_id=state_id,
        revision=revision,
        conversation_ids=conversation_ids,
        active_entities=active_entities,
        active_options=active_options,
        referents=referents,
        recent_conclusions=conclusions,
        active_event_ids=active_event_ids,
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.INTERACTION_WORKING_STATE,
        source=SOURCE,
        payload={"state": state.model_dump(mode="json")},
        event_id=deterministic_working_state_event_id(interaction_id),
    )
    return state


def _clean_option(value: str) -> str:
    return " ".join(value.strip().split())


def _merge_text_lists(
    first: list[str],
    second: list[str],
    limit: int,
) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*first, *second]:
        normalized = " ".join(value.split())
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
        if len(merged) == limit:
            break
    return merged


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
