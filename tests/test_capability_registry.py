import uuid

import pytest

from jit_agent import capability_registry, db, event_store, llm
from jit_agent.models import CapabilityKind, CapabilityNeed, EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


@pytest.mark.parametrize(
    "query,expected",
    [
        (
            "Create a deployment plan and recommend the next steps.",
            "planning_specialist",
        ),
        (
            "Compare the Project Atlas schedule and explain what changed.",
            "analysis_specialist",
        ),
        (
            "Recall the original Project Oriole codename from prior history.",
            "memory_specialist",
        ),
    ],
)
def test_registry_routes_tasks_without_llm_selection(query, expected):
    need = CapabilityNeed(query_text=query, kinds=[CapabilityKind.AGENT], limit=1)

    first = capability_registry.DEFAULT_REGISTRY.discover(need)
    second = capability_registry.DEFAULT_REGISTRY.discover(need)

    assert first
    assert first[0].descriptor.capability_id == expected
    assert second == first


def test_registry_returns_no_match_instead_of_inventing_capability():
    need = CapabilityNeed(
        query_text="Render a textured 3D mesh from a point cloud.",
        kinds=[CapabilityKind.AGENT],
        limit=3,
    )

    assert capability_registry.DEFAULT_REGISTRY.discover(need) == []


def test_registry_respects_capability_kind_filter():
    need = CapabilityNeed(
        query_text="Create a deployment plan.",
        kinds=[CapabilityKind.TOOL],
        limit=3,
    )

    assert capability_registry.DEFAULT_REGISTRY.discover(need) == []


def test_primary_system_prompt_does_not_embed_capability_catalog():
    prompt = llm._CLASSIFY_SYSTEM_PROMPT

    for descriptor in capability_registry.DEFAULT_REGISTRY.descriptors():
        assert descriptor.capability_id not in prompt


def test_request_capability_persists_bounded_request_and_packet(conn):
    conversation_id = event_store.start_conversation(conn)
    correlation_id = uuid.uuid4()
    need = CapabilityNeed(
        query_text="Compare how the Project Atlas schedule changed.",
        kinds=[CapabilityKind.AGENT],
        limit=1,
    )

    packet = capability_registry.request_capability(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        requesting_agent="test_agent",
        need=need,
    )

    assert len(packet.matches) == 1
    assert packet.matches[0].descriptor.capability_id == "analysis_specialist"

    events = event_store.get_events_by_conversation(conn, conversation_id)
    assert [event.event_type for event in events] == [
        EventType.CAPABILITY_REQUEST,
        EventType.CAPABILITY_PACKET,
    ]
    request_event, packet_event = events
    assert request_event.source == "test_agent"
    assert packet_event.source == capability_registry.SOURCE
    assert request_event.payload["capability_request_id"] == str(packet.capability_request_id)
    assert packet_event.payload["packet"]["capability_request_id"] == str(
        packet.capability_request_id
    )
    assert len(packet_event.payload["packet"]["matches"]) == 1

    public_descriptor = packet_event.payload["packet"]["matches"][0]["descriptor"]
    assert set(public_descriptor) == {"capability_id", "kind", "description"}
