from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from jit_agent.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from jit_agent.response_policy import (
    ExactSourceComposition,
    ExactSourceSelection,
    HistoricalEvidenceScope,
    ResponsePolicy,
    ResponseSurfaceMode,
    allowed_event_types,
    filter_memory_packet_for_scope,
    scope_requires_historical_support,
    validate_current_literal,
    validate_exact_source_composition,
    validate_exact_source_selection,
)


def _evidence(event_type: EventType, content: str, seq: int) -> MemoryEvidence:
    return MemoryEvidence(
        source_event_id=uuid.uuid4(),
        event_type=event_type,
        source="response-policy-test",
        created_at=datetime.now(timezone.utc),
        conversation_id=uuid.uuid4(),
        conversation_seq=seq,
        global_seq=seq,
        content=content,
    )


def _packet(*items: MemoryEvidence) -> MemoryPacket:
    return MemoryPacket(
        memory_request_id=uuid.uuid4(),
        need=MemoryNeed(query_text="historical question"),
        supported=bool(items),
        items=list(items),
    )


def test_user_authored_scope_physically_removes_model_output():
    user = _evidence(EventType.USER_PROMPT, "My favorite color is green.", 1)
    assistant = _evidence(
        EventType.INTERACTION_RESPONSE,
        "The user's favorite color is Cerulean-POISON.",
        2,
    )

    filtered = filter_memory_packet_for_scope(
        _packet(user, assistant),
        HistoricalEvidenceScope.USER_AUTHORED,
    )

    assert filtered is not None
    assert [item.source_event_id for item in filtered.items] == [user.source_event_id]
    assert filtered.supported is True


def test_user_authored_scope_fails_closed_when_only_model_output_exists():
    assistant = _evidence(
        EventType.INTERACTION_RESPONSE,
        "The user's favorite color is Cerulean-POISON.",
        1,
    )

    filtered = filter_memory_packet_for_scope(
        _packet(assistant),
        HistoricalEvidenceScope.USER_AUTHORED,
    )

    assert filtered is not None
    assert filtered.items == []
    assert filtered.supported is False
    assert scope_requires_historical_support(HistoricalEvidenceScope.USER_AUTHORED)


def test_model_output_scope_preserves_assistant_history_for_assistant_history_questions():
    user = _evidence(EventType.USER_PROMPT, "Tell me a color.", 1)
    assistant = _evidence(EventType.INTERACTION_RESPONSE, "I said blue.", 2)

    filtered = filter_memory_packet_for_scope(
        _packet(user, assistant),
        HistoricalEvidenceScope.MODEL_OUTPUT,
    )

    assert filtered is not None
    assert [item.source_event_id for item in filtered.items] == [assistant.source_event_id]


def test_scope_mapping_is_application_owned_and_closed():
    assert allowed_event_types(HistoricalEvidenceScope.USER_AUTHORED) == frozenset(
        {EventType.USER_PROMPT}
    )
    assert EventType.INTERACTION_RESPONSE in (
        allowed_event_types(HistoricalEvidenceScope.MODEL_OUTPUT) or frozenset()
    )
    assert allowed_event_types(HistoricalEvidenceScope.GENERAL_OR_CURRENT) is None


def test_insufficient_literal_must_be_verbatim_current_prompt_text():
    prompt = "Favorite color? USER_PROMPT only; otherwise INSUFFICIENT."
    assert validate_current_literal(prompt, "INSUFFICIENT") == "INSUFFICIENT"
    with pytest.raises(ValueError, match="exact substring"):
        validate_current_literal(prompt, "UNKNOWN")


def test_exact_source_selection_returns_source_bytes_not_generated_wrapper():
    item = _evidence(
        EventType.USER_PROMPT,
        "The launch key for Project Aster is ASTER-1234ABCD.",
        1,
    )
    packet = _packet(item)
    selection = ExactSourceSelection(
        source_index=0,
        verbatim_value="ASTER-1234ABCD",
    )

    assert validate_exact_source_selection(packet, selection) == "ASTER-1234ABCD"

    with pytest.raises(ValueError, match="verbatim substring"):
        validate_exact_source_selection(
            packet,
            ExactSourceSelection(source_index=0, verbatim_value="The key is ASTER-1234ABCD"),
        )


def test_exact_source_composition_uses_only_source_values_and_current_formatting():
    prompt = "Return exactly '<approach> | <profile>' and nothing else."
    source_texts = (
        "I am choosing between Docker Compose and PostgreSQL directly on Windows.",
        "I track that constraint under profile VX-1234ABCD.",
    )
    composition = ExactSourceComposition(
        selections=[
            ExactSourceSelection(source_index=0, verbatim_value="Docker Compose"),
            ExactSourceSelection(source_index=1, verbatim_value="VX-1234ABCD"),
        ],
        separator=" | ",
    )

    assert (
        validate_exact_source_composition(prompt, source_texts, composition)
        == "Docker Compose | VX-1234ABCD"
    )


def test_exact_source_composition_rejects_answer_bearing_current_text_as_separator():
    with pytest.raises(ValueError, match="formatting-only"):
        ExactSourceComposition(
            selections=[ExactSourceSelection(source_index=0, verbatim_value="Docker Compose")],
            separator="approach",
        )


def test_exact_source_composition_rejects_separator_not_present_in_current_prompt():
    prompt = "Return exactly '<approach> | <profile>' and nothing else."
    source_texts = ("Docker Compose", "VX-1234ABCD")
    composition = ExactSourceComposition(
        selections=[
            ExactSourceSelection(source_index=0, verbatim_value="Docker Compose"),
            ExactSourceSelection(source_index=1, verbatim_value="VX-1234ABCD"),
        ],
        separator=" / ",
    )

    with pytest.raises(ValueError, match="current-prompt"):
        validate_exact_source_composition(prompt, source_texts, composition)


def test_response_policy_schema_keeps_epistemic_and_surface_contract_separate():
    policy = ResponsePolicy(
        evidence_scope=HistoricalEvidenceScope.USER_AUTHORED,
        surface_mode=ResponseSurfaceMode.EXACT_SOURCE_SUBSTRING,
        insufficient_literal=None,
    )

    assert policy.evidence_scope is HistoricalEvidenceScope.USER_AUTHORED
    assert policy.surface_mode is ResponseSurfaceMode.EXACT_SOURCE_SUBSTRING

    composition_policy = policy.model_copy(
        update={"surface_mode": ResponseSurfaceMode.EXACT_SOURCE_COMPOSITION}
    )
    assert composition_policy.surface_mode is ResponseSurfaceMode.EXACT_SOURCE_COMPOSITION
