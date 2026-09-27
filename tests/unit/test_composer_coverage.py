from datetime import datetime, timezone
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from prometheist.composer_coverage import EvidenceCoverage, coverage_catalog, coverage_schema
from prometheist.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from prometheist.percept_response_runtime import ComposerValidationError, PerceptLLM, _compose_memory_package
from prometheist.percept_response_worker import UserPromptLLM
from prometheist.self_memory import SelfContextItem, SelfContextPacket, SelfEvidenceMetrics


def packet():
    return MemoryPacket(
        memory_request_id=uuid4(), need=MemoryNeed(), supported=True,
        items=[MemoryEvidence(
            source_event_id=uuid4(), event_type=EventType.USER_PROMPT,
            source="user", created_at=datetime.now(timezone.utc),
            conversation_id=uuid4(), conversation_seq=1, global_seq=1,
            content="I prefer an office near home.",
        )],
    )


def test_missing_requirement_cannot_be_overridden_by_supported_partial_context():
    assessment = EvidenceCoverage.model_validate({"requirements": [
        {"need": "work location", "evidence_index": 0},
        {"need": "financial priorities", "evidence_index": None},
        {"need": "career values", "evidence_index": None},
    ]})
    assert assessment.decision_fields(1) == {
        "sufficient": False, "memory_deficit": "financial priorities",
    }
    assert EvidenceCoverage.model_validate({"requirements": [
        {"need": "work location", "evidence_index": 0},
    ]}).decision_fields(1) == {"sufficient": True, "memory_deficit": None}


@pytest.mark.parametrize("payload", [
    {"requirements": []},
    {"requirements": [{"need": " ", "evidence_index": None}]},
    {"requirements": [{"need": "location", "evidence_index": -1}]},
    {"requirements": [{"need": "location", "evidence_index": False}]},
    {"requirements": [{"need": "location", "evidence_index": 1}]},
    {"requirements": [{"need": "location", "evidence_index": 0}], "sufficient": True},
    {"requirements": [{"need": "location", "evidence_index": 0},
                      {"need": " Location ", "evidence_index": 0}]},
])
def test_invalid_or_fabricated_coverage_fails_closed(payload):
    with pytest.raises(ValueError):
        EvidenceCoverage.model_validate(payload).decision_fields(1)


@pytest.mark.parametrize("llm_type", [PerceptLLM, UserPromptLLM])
def test_both_composer_paths_derive_verdict_and_retry_invalid_source_selection(monkeypatch, llm_type):
    llm = llm_type()
    calls = []

    def structured(kind, system, user, evidence, schema, max_tokens):
        calls.append(max_tokens)
        assert "source_index=0" in evidence
        assert "I prefer an office near home." in evidence
        assert "sufficient" not in schema["properties"]
        assert "financial priorities" in user
        return json.dumps({"requirements": [
            {"need": "financial priorities", "evidence_index": 99 if len(calls) == 1 else None},
        ]})

    monkeypatch.setattr(llm, "_structured_with_evidence", structured)
    decision = llm.assess_memory_sufficiency(
        "What are my financial priorities?", packet(), person_history_required=True,
    )
    assert calls == [256, 384]
    assert decision.sufficient is False
    assert decision.memory_deficit == "financial priorities"


def test_repeated_invalid_source_selections_cannot_authorize_response(monkeypatch):
    llm = UserPromptLLM()
    monkeypatch.setattr(llm, "_structured_with_evidence", lambda *args:
        '{"requirements":[{"need":"preferences","evidence_index":99}]}')
    with pytest.raises(ComposerValidationError):
        llm.assess_memory_sufficiency("What do I prefer?", packet(), person_history_required=True)


def test_catalog_and_schema_use_same_source_order_and_zero_sources_require_null():
    memory = packet()
    rendered, refs = coverage_catalog(memory, None)
    assert refs == (f"event:{memory.items[0].source_event_id}",)
    assert "source_index=0" in rendered
    assert "DIRECT_USER_TESTIMONY" in rendered
    field = coverage_schema(1)["$defs"]["EvidenceRequirement"]["properties"]["evidence_index"]
    assert field["anyOf"][0]["maximum"] == 0
    empty = coverage_schema(0)["$defs"]["EvidenceRequirement"]["properties"]["evidence_index"]
    assert empty == {"type": "null"}
    earlier = memory.items[0].model_copy(update={
        "source_event_id": uuid4(), "global_seq": 0, "content": "An earlier preference.",
    })
    memory.items.append(earlier)
    rendered, refs = coverage_catalog(memory, None)
    assert refs[0] == f"event:{earlier.source_event_id}"
    assert rendered.index(earlier.content) < rendered.index(memory.items[0].content)


def test_derived_sources_are_numbered_only_when_admitted_as_evidence():
    memory = packet()
    item = SelfContextItem(
        representation_id=uuid4(), kind="PREFERENCE", perspective="AVOWED",
        statement="I prefer predictable hours.", status="ESTABLISHED",
        identity_centrality="PERIPHERAL", metrics=SelfEvidenceMetrics(
            support_root_count=1, opposition_root_count=0, source_type_count=1,
            source_count=1, context_count=1,
        ),
    )
    context = SelfContextPacket(admission="PRIMARY_DERIVED_CONTEXT", items=(item,))
    rendered, refs = coverage_catalog(memory, context)
    assert refs == (f"event:{memory.items[0].source_event_id}", f"self:{item.representation_id}")
    assert "source_index=1\nsource_kind=DERIVED_SELF" in rendered
    assert item.statement in rendered
    routing = SelfContextPacket(admission="ROUTING_ONLY", items=(item,))
    rendered, refs = coverage_catalog(memory, routing)
    assert len(refs) == 1
    assert item.statement not in rendered


def test_missing_requirement_drives_recall_before_composer_can_approve(monkeypatch):
    initial = packet()
    llm = UserPromptLLM()
    calls = []

    def structured(*args):
        calls.append(args)
        return json.dumps({"requirements": [
            {"need": "work location", "evidence_index": 0},
            {"need": "financial priorities", "evidence_index": None if len(calls) == 1 else 1},
        ]})

    def recall(conn, interaction, current, deficit, **kwargs):
        assert deficit == "financial priorities"
        added = initial.items[0].model_copy(update={
            "source_event_id": uuid4(), "global_seq": 2, "content": "I prefer predictable income.",
        })
        return current.model_copy(update={"items": [*current.items, added]})

    monkeypatch.setattr(llm, "_structured_with_evidence", structured)
    monkeypatch.setattr("prometheist.percept_response_runtime._adaptive_recall", recall)
    package = _compose_memory_package(
        None, llm, SimpleNamespace(user_text="Which offer fits my priorities?"), initial, [],
        person_history_required=True,
    )
    assert package.sufficient is True
    assert package.adaptive_recall_rounds == 1
    assert package.composer_rounds == 2
    assert "predictable income" in calls[1][3]
