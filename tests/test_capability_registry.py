import uuid

import pytest

from jit_agent import capability_registry, db, event_store, llm
from jit_agent.models import CapabilityDescriptor, CapabilityKind, CapabilityNeed, EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


@pytest.mark.parametrize(
    "query,expected,kind",
    [
        (
            "Create a deployment plan and recommend the next steps.",
            "planning_specialist",
            CapabilityKind.AGENT,
        ),
        (
            "Compare the Project Atlas schedule and explain what changed.",
            "analysis_specialist",
            CapabilityKind.AGENT,
        ),
        (
            "Recall the original Project Oriole codename from prior history.",
            "internal_memory",
            CapabilityKind.SERVICE,
        ),
    ],
)
def test_registry_routes_heterogeneous_capabilities_without_llm_selection(query, expected, kind):
    need = CapabilityNeed(query_text=query, limit=1)

    first = capability_registry.DEFAULT_REGISTRY.discover(need)
    second = capability_registry.DEFAULT_REGISTRY.discover(need)

    assert first
    assert first[0].descriptor.capability_id == expected
    assert first[0].descriptor.kind == kind
    assert second == first


@pytest.mark.parametrize(
    "query",
    [
        "persisted internal history access",
        "retrieve stored deployment information",
        "look up saved Project Atlas data",
        "access prior context about the deployment requirement",
    ],
)
def test_internal_memory_discovery_accepts_natural_information_access_phrasing(query):
    need = CapabilityNeed(query_text=query, limit=1)

    matches = capability_registry.DEFAULT_REGISTRY.discover(need)

    assert matches
    assert matches[0].descriptor.capability_id == "internal_memory"


def test_registry_returns_no_match_instead_of_inventing_capability():
    need = CapabilityNeed(
        query_text="Render a textured 3D mesh from a point cloud.",
        limit=3,
    )

    assert capability_registry.DEFAULT_REGISTRY.discover(need) == []


def test_registry_respects_capability_kind_filter():
    need = CapabilityNeed(
        query_text="Recall prior history.",
        kinds=[CapabilityKind.AGENT],
        limit=3,
    )

    assert capability_registry.DEFAULT_REGISTRY.discover(need) == []


def test_registry_can_add_and_remove_capability_without_primary_changes():
    registry = capability_registry.CapabilityRegistry()
    registration = capability_registry.RegisteredCapability(
        descriptor=CapabilityDescriptor(
            capability_id="document_specialist",
            kind=CapabilityKind.AGENT,
            description="Inspect and synthesize document evidence.",
        ),
        routing_terms=("document", "pdf", "contract"),
        executor="stateless_specialist",
        instruction="Analyze supplied document evidence.",
    )

    registry.register(registration)
    need = CapabilityNeed(query_text="Analyze this contract document.", limit=1)
    assert registry.discover(need)[0].descriptor.capability_id == "document_specialist"

    removed = registry.unregister("document_specialist")
    assert removed == registration
    assert registry.discover(need) == []


def test_primary_system_prompt_does_not_embed_capability_catalog():
    prompt = llm._CLASSIFY_SYSTEM_PROMPT

    for descriptor in capability_registry.DEFAULT_REGISTRY.descriptors():
        assert descriptor.capability_id not in prompt


def test_registry_uses_supplemental_capability_query_only_after_canonical_miss():
    need = CapabilityNeed(
        query_text="Please handle this for me.",
        supplemental_query_texts=["access persisted internal history"],
        limit=1,
    )

    matches, role, selected_query = capability_registry.DEFAULT_REGISTRY.discover_with_trace(need)

    assert matches[0].descriptor.capability_id == "internal_memory"
    assert role == "supplemental"
    assert selected_query == "access persisted internal history"


def test_canonical_capability_match_wins_over_lossy_supplemental_query():
    need = CapabilityNeed(
        query_text="Compare how the Project Atlas schedule changed.",
        supplemental_query_texts=["access persisted internal history"],
        limit=1,
    )

    matches, role, selected_query = capability_registry.DEFAULT_REGISTRY.discover_with_trace(need)

    assert matches[0].descriptor.capability_id == "analysis_specialist"
    assert role == "canonical"
    assert selected_query == need.query_text


def test_request_capability_persists_bounded_request_and_packet(conn):
    conversation_id = event_store.start_conversation(conn)
    correlation_id = uuid.uuid4()
    need = CapabilityNeed(
        query_text="Compare how the Project Atlas schedule changed.",
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
    assert packet.selected_query_role == "canonical"

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
