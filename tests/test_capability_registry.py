from __future__ import annotations

import json
import uuid

import pytest

from jit_agent import db, event_store
from jit_agent.capability_registry import (
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityNeed,
    CapabilityRegistry,
    RegisteredCapability,
    deterministic_capability_request_id,
    request_capability,
)
from jit_agent.models import EventType


def _registration(
    capability_id: str,
    kind: CapabilityKind,
    *terms: str,
    executor: str = "test.executor",
) -> RegisteredCapability:
    return RegisteredCapability(
        descriptor=CapabilityDescriptor(
            capability_id=capability_id,
            kind=kind,
            description=f"Public description for {capability_id}.",
        ),
        routing_terms=terms,
        executor=executor,
    )


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def test_discovery_is_bounded_deterministic_and_canonical_first():
    registry = CapabilityRegistry(
        (
            _registration("weather_lookup", CapabilityKind.TOOL, "weather", "forecast"),
            _registration(
                "compare_records",
                CapabilityKind.WORKFLOW,
                "compare records",
                "reconcile records",
            ),
        )
    )
    need = CapabilityNeed(
        query_text="Please compare records from the two systems.",
        supplemental_query_texts=["weather forecast"],
        limit=1,
    )

    first = registry.discover_with_trace(need)
    second = registry.discover_with_trace(need)

    assert first == second
    matches, role, selected_text = first
    assert [item.descriptor.capability_id for item in matches] == ["compare_records"]
    assert role == "canonical"
    assert selected_text == need.query_text


def test_supplemental_query_runs_only_after_canonical_abstention():
    registry = CapabilityRegistry(
        (_registration("weather_lookup", CapabilityKind.TOOL, "weather forecast"),)
    )

    matches, role, selected_text = registry.discover_with_trace(
        CapabilityNeed(
            query_text="This canonical task has no installed match.",
            supplemental_query_texts=["weather forecast"],
        )
    )

    assert [item.descriptor.capability_id for item in matches] == ["weather_lookup"]
    assert role == "supplemental"
    assert selected_text == "weather forecast"


def test_discovery_abstains_and_honors_kind_and_exclusion_filters():
    registry = CapabilityRegistry(
        (
            _registration("weather_model", CapabilityKind.MODEL, "weather"),
            _registration("weather_tool", CapabilityKind.TOOL, "weather"),
        )
    )
    need = CapabilityNeed(
        query_text="weather",
        kinds=[CapabilityKind.TOOL],
        exclude_capability_ids=["weather_tool"],
    )

    assert registry.discover(need) == []


def test_registry_rejects_duplicate_ids_and_exposes_only_public_descriptors():
    private = _registration(
        "internal_memory",
        CapabilityKind.SERVICE,
        "secret routing phrase",
        executor="private.executor",
    )
    registry = CapabilityRegistry((private,))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(private)

    rendered = json.dumps(
        registry.discover(CapabilityNeed(query_text="secret routing phrase"))[0].model_dump(
            mode="json"
        )
    )
    assert "secret routing phrase" not in rendered
    assert "private.executor" not in rendered
    assert set(CapabilityKind) == {
        CapabilityKind.SERVICE,
        CapabilityKind.TOOL,
        CapabilityKind.MODEL,
        CapabilityKind.WORKFLOW,
    }


def test_persisted_capability_lookup_is_idempotent_and_task_neutral(conn):
    conversation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    event_store.start_conversation(conn, conversation_id)
    registry = CapabilityRegistry(
        (_registration("weather_lookup", CapabilityKind.TOOL, "weather"),)
    )
    need = CapabilityNeed(query_text="weather")

    first = request_capability(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        need=need,
        registry=registry,
    )
    repeated = request_capability(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requester_task_id=task_id,
        requester_step_id=step_id,
        need=need,
        registry=registry,
    )

    assert repeated == first
    assert first.capability_request_id == deterministic_capability_request_id(step_id)
    assert "agent" not in first.model_dump_json().casefold()
    events = event_store.get_events_by_conversation(conn, conversation_id)
    assert [event.event_type for event in events] == [
        EventType.CAPABILITY_REQUEST,
        EventType.CAPABILITY_PACKET,
    ]
