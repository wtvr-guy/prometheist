from datetime import datetime, timezone
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from prometheist.composer_coverage import (
    EvidenceCoverage, MemoryRequirements, coverage_catalog, coverage_schema,
)
from prometheist.models import EventType, MemoryEvidence, MemoryNeed, MemoryPacket
from prometheist.percept_response_runtime import ComposerValidationError, PerceptLLM, _compose_memory_package
from prometheist.percept_response_worker import UserPromptLLM
from prometheist.self_memory import SelfContextItem, SelfContextPacket, SelfEvidenceMetrics


def requirements(*needs):
    return MemoryRequirements.model_validate({"requirements": [{"need": need} for need in needs]})


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


def coverage(*indices):
    return EvidenceCoverage.model_validate({"coverage": [
        {"requirement_index": i, "evidence_indices": sources} for i, sources in enumerate(indices)
    ]})


def test_missing_fixed_requirement_cannot_be_dropped_or_overridden():
    plan = requirements("work location", "financial priorities", "career values")
    assert coverage([0], [], []).decision_fields(plan, 1) == {
        "sufficient": False, "memory_deficit": "financial priorities",
    }
    with pytest.raises(ValueError, match="every fixed requirement"):
        coverage([0]).decision_fields(plan, 1)
    assert coverage([0], [1], [2]).decision_fields(plan, 3) == {
        "sufficient": True, "memory_deficit": None,
    }


def test_multiple_memories_can_cover_one_requirement_without_changing_it():
    plan = requirements("experience explaining changed work preference")
    assert coverage([0, 1, 2]).decision_fields(plan, 3)["sufficient"]
    assert MemoryRequirements.model_validate_json(plan.model_dump_json()) == plan
    with pytest.raises(ValueError):
        plan.requirements[0].need = "a different remembered answer"


@pytest.mark.parametrize("needs", [(), (" ",), ("x" * 81,), ("location", " Location ")])
def test_invalid_requirement_plans_fail_closed(needs):
    with pytest.raises(ValueError):
        requirements(*needs)


@pytest.mark.parametrize("payload", [
    {"coverage": []},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [-1]}]},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [False]}]},
    {"coverage": [{"requirement_index": False, "evidence_indices": [0]}]},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [1]}]},
    {"coverage": [{"requirement_index": 1, "evidence_indices": [0]}]},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [0, 0]}]},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [0]}], "sufficient": True},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [0], "need": "replacement"}]},
    {"coverage": [{"requirement_index": 0, "evidence_indices": [0]},
                  {"requirement_index": 0, "evidence_indices": [0]}]},
    {"requirements": [{"need": "location", "evidence_index": 0}]},
])
def test_invalid_or_fabricated_coverage_fails_closed(payload):
    with pytest.raises(ValueError):
        EvidenceCoverage.model_validate(payload).decision_fields(requirements("location"), 1)


@pytest.mark.parametrize("llm_type", [PerceptLLM, UserPromptLLM])
def test_both_composer_paths_derive_verdict_and_retry_invalid_source_selection(monkeypatch, llm_type):
    llm = llm_type()
    calls = []
    plan = requirements("financial priorities")

    def structured(kind, system, user, evidence, schema, max_tokens):
        calls.append(max_tokens)
        assert "source_index=0" in evidence
        assert "I prefer an office near home." in evidence
        assert "sufficient" not in schema["properties"]
        assert plan.render() in user
        return json.dumps({"coverage": [{
            "requirement_index": 0, "evidence_indices": [99] if len(calls) == 1 else [],
        }]})

    monkeypatch.setattr(llm, "_structured_with_evidence", structured)
    decision = llm.assess_memory_sufficiency(
        "What are my financial priorities?", packet(), person_history_required=True,
        requirements=plan,
    )
    assert calls == [256, 384]
    assert decision.sufficient is False
    assert decision.memory_deficit == "financial priorities"


@pytest.mark.parametrize("llm_type", [PerceptLLM, UserPromptLLM])
def test_composer_cannot_plan_requirements_as_a_fallback(monkeypatch, llm_type):
    llm = llm_type()
    def forbidden(*args):
        pytest.fail("missing committed requirements must not invoke another model role")
    monkeypatch.setattr(llm, "_structured_with_evidence", forbidden)
    with pytest.raises(ComposerValidationError, match="committed requirements"):
        llm.assess_memory_sufficiency("What do I prefer?", packet(), person_history_required=True)


def test_repeated_invalid_source_selections_cannot_authorize_response(monkeypatch):
    llm = UserPromptLLM()
    monkeypatch.setattr(llm, "_structured_with_evidence", lambda *args:
        '{"coverage":[{"requirement_index":0,"evidence_indices":[99]}]}')
    with pytest.raises(ComposerValidationError):
        llm.assess_memory_sufficiency("What do I prefer?", packet(), person_history_required=True,
                                     requirements=requirements("preferences"))


def test_catalog_and_schema_share_bounds_and_empty_catalog_requires_empty_support():
    memory = packet()
    plan = requirements("location")
    rendered, refs = coverage_catalog(memory, None)
    assert refs == (f"event:{memory.items[0].source_event_id}",)
    assert "source_index=0" in rendered
    assert "DIRECT_USER_TESTIMONY" in rendered
    schema = coverage_schema(plan, 1)
    props = schema["$defs"]["RequirementSupport"]["properties"]
    assert props["evidence_indices"]["items"]["maximum"] == 0
    assert props["requirement_index"]["maximum"] == 0
    assert schema["properties"]["coverage"]["minItems"] == 1
    assert schema["properties"]["coverage"]["maxItems"] == 1
    empty = coverage_schema(plan, 0)["$defs"]["RequirementSupport"]["properties"]["evidence_indices"]
    assert empty["maxItems"] == 0
    assert coverage([]).decision_fields(plan, 0)["sufficient"] is False
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


def test_fixed_missing_requirement_drives_recall_without_replanning(monkeypatch):
    initial = packet()
    plan = requirements("work location", "financial priorities")
    llm = UserPromptLLM()
    calls = []

    def structured(*args):
        calls.append(args)
        assert args[0] == "V2_MEMORY_SUFFICIENCY_USER_PROMPT"
        assert plan.render() in args[2]
        return coverage([0], [] if len(calls) == 1 else [1]).model_dump_json()

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
        person_history_required=True, requirements=plan,
    )
    assert package.sufficient is True
    assert package.requirements == plan
    assert package.adaptive_recall_rounds == 1
    assert package.composer_rounds == 2
    assert "predictable income" in calls[1][3]
