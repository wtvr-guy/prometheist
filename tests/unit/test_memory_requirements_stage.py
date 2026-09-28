import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from prometheist import percept_response_runtime as runtime
from prometheist import percept_response_worker as worker
from prometheist.capability_registry import DEFAULT_REGISTRY
from prometheist.composer_coverage import MemoryRequirements
from prometheist.interaction_contracts import DurableInteraction
from prometheist.models import MemoryNeed, MemoryPacket
from prometheist.percept_response_runtime import ComposerValidationError, PerceptLLM, PerceptStage
from prometheist.response_policy import RESPONSE_POLICY_VERSION, ResponsePolicy, source_types_for_scope
from prometheist.self_memory import SelfContextPacket


def plan():
    return MemoryRequirements.model_validate({"requirements": [
        {"need": "communication style"}, {"need": "comparable past project messages"},
    ]})


def policy_output(scope="SELF_MODEL"):
    policy = ResponsePolicy(evidence_scope=scope, surface_mode="NATURAL_LANGUAGE")
    return {"response_policy_version": RESPONSE_POLICY_VERSION,
            "response_policy": policy.model_dump(mode="json"),
            "response_source_types": [x.value for x in source_types_for_scope(policy.evidence_scope)]}


def envelope(stage):
    return SimpleNamespace(step=SimpleNamespace(step_key=stage.value))


@pytest.mark.parametrize("llm_type", [PerceptLLM, worker.UserPromptLLM])
def test_requirement_specialist_sees_only_current_request_and_retries_invalid_plan(monkeypatch, llm_type):
    llm = llm_type()
    calls = []
    refs = []
    monkeypatch.setattr(llm, "_set_artifact_evidence_refs", refs.append)
    def structured(kind, system, current, evidence, schema, max_tokens):
        calls.append(max_tokens)
        assert kind == "V2_MEMORY_REQUIREMENTS"
        assert current == "Draft the update I would send."
        assert evidence == worker._quarantined_evidence()
        assert set(schema["properties"]) == {"requirements"}
        return '{"requirements":[]}' if len(calls) == 1 else plan().model_dump_json()
    monkeypatch.setattr(llm, "_structured_with_evidence", structured)
    assert llm.plan_memory_requirements("Draft the update I would send.") == plan()
    assert calls == [256, 384]
    assert refs == [()]


def test_invalid_requirements_never_become_a_plan(monkeypatch):
    llm = worker.UserPromptLLM()
    monkeypatch.setattr(llm, "_structured_with_evidence", lambda *args: '{"requirements":[]}')
    with pytest.raises(ComposerValidationError):
        llm.plan_memory_requirements("Draft the update I would send.")


@pytest.mark.parametrize("stage,forbidden", [
    (PerceptStage.MEMORY_REQUIREMENTS, "V2_MEMORY_SUFFICIENCY_USER_PROMPT"),
    (PerceptStage.MEMORY_REQUIREMENTS, "FINAL_RESPONSE_V2"),
    (PerceptStage.COMPOSE_MEMORY, "V2_MEMORY_REQUIREMENTS"),
    (PerceptStage.PRECOGNITIVE, "V2_MEMORY_REQUIREMENTS"),
])
def test_planning_and_evidence_matching_have_separate_guarded_workers(stage, forbidden):
    llm = worker.UserPromptLLM(stage=stage)
    with pytest.raises(RuntimeError, match="cannot invoke LLM role"):
        llm._require_stage_specialization(forbidden)


def test_requirement_stage_loads_only_policy_and_commits_typed_plan(monkeypatch):
    reads = []
    def stage_result(conn, interaction, stage, scheduler_key):
        reads.append(stage)
        assert stage is PerceptStage.EVIDENCE_POLICY
        return policy_output()
    monkeypatch.setattr(runtime, "_stage_result", stage_result)
    llm = SimpleNamespace(plan_memory_requirements=lambda prompt: plan())
    output, refs = runtime._execute_stage(
        None, llm, envelope(PerceptStage.MEMORY_REQUIREMENTS),
        SimpleNamespace(user_text="Draft the update I would send."),
        scheduler_key="test", registry=DEFAULT_REGISTRY,
    )
    assert reads == [PerceptStage.EVIDENCE_POLICY]
    assert output == {"skipped": False, "requirements": plan().model_dump(mode="json")}
    assert refs == []


def test_non_self_model_requests_skip_planning_without_a_model_call(monkeypatch):
    monkeypatch.setattr(runtime, "_stage_result", lambda *args: policy_output("USER_AUTHORED"))
    output, refs = runtime._execute_stage(
        None, object(), envelope(PerceptStage.MEMORY_REQUIREMENTS),
        SimpleNamespace(user_text="What was my teacher's name?"),
        scheduler_key="test", registry=DEFAULT_REGISTRY,
    )
    assert output == {"skipped": True, "requirements": None}
    assert refs == []


def test_compose_stage_rehydrates_the_exact_plan_without_replanning(monkeypatch):
    memory = MemoryPacket(memory_request_id=uuid4(), need=MemoryNeed(), supported=False, items=[])
    saved_plan = json.loads(plan().model_dump_json())
    results = {
        PerceptStage.EVIDENCE_POLICY: policy_output(),
        PerceptStage.MEMORY_REQUIREMENTS: {"skipped": False, "requirements": saved_plan},
        PerceptStage.PRECOGNITIVE: {
            "disposition": {"response_required": True, "capability_indices": []},
            "aperture_packet": memory.model_dump(mode="json"),
            "self_context": SelfContextPacket(admission="PRIMARY_DERIVED_CONTEXT").model_dump(mode="json"),
        },
    }
    monkeypatch.setattr(runtime, "_stage_result", lambda conn, interaction, stage, key: results[stage])
    def compose(*args, **kwargs):
        assert kwargs["requirements"] == plan()
        return runtime.ResponseMemoryPackage(
            memory_packet=memory, sufficient=False, composer_rounds=1, adaptive_recall_rounds=0,
            unresolved_memory_deficit="communication style", requirements=kwargs["requirements"],
        )
    monkeypatch.setattr(runtime, "_compose_memory_package", compose)
    output, _ = runtime._execute_stage(
        None, object(), envelope(PerceptStage.COMPOSE_MEMORY),
        SimpleNamespace(user_text="Draft the update I would send."),
        scheduler_key="test", registry=DEFAULT_REGISTRY,
    )
    assert output["memory_package"]["requirements"] == saved_plan


def test_published_requirement_stage_recovers_after_database_completion_failure(monkeypatch):
    interaction = DurableInteraction(
        interaction_id=uuid4(), conversation_id=uuid4(), correlation_id=uuid4(),
        user_prompt_event_id=uuid4(), task_id=uuid4(), assignment_id=uuid4(),
        before_global_seq=1, user_text="Draft the update I would send.",
    )
    claimed = envelope(PerceptStage.MEMORY_REQUIREMENTS)
    claimed.step.task_id = interaction.task_id
    monkeypatch.setattr(worker, "load_worker_claim_envelope", lambda *args, **kwargs: claimed)
    monkeypatch.setattr(worker, "load_interaction_by_task", lambda *args, **kwargs: interaction)
    monkeypatch.setattr(worker, "_ensure_percept_artifact", lambda *args: None)
    output = {"skipped": False, "requirements": plan().model_dump(mode="json")}
    worker.artifact_journal.write_stage_result_artifact(
        interaction_id=interaction.interaction_id, conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id, task_id=interaction.task_id,
        assignment_id=interaction.assignment_id, stage=PerceptStage.MEMORY_REQUIREMENTS.value,
        output=output, output_refs=[],
    )
    monkeypatch.setattr(worker, "_execute_stage", lambda *args, **kwargs: pytest.fail("must recover, not replan"))
    completed = []
    monkeypatch.setattr(worker, "complete_worker_claim", lambda *args, **kwargs: completed.append(kwargs))
    worker._execute_claimed_user_prompt_step(None, object(), claim_id=uuid4(), worker_id="fresh", scheduler_key="test")
    assert completed[0]["output"] == output
