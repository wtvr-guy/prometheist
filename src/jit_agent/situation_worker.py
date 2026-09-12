"""One claimed situation stage per fresh process, with exact artifact handoffs."""
from __future__ import annotations

import json
import os
from uuid import UUID, uuid5

from jit_agent import artifact_journal, db, event_store, jit_memory
from jit_agent.action_outcomes import issue_action, observe_action_outcome
from jit_agent.cognitive_store import get_record, put_record
from jit_agent.consolidation import consolidate_page
from jit_agent.epistemic_authority import format_authority_bound_memory_packet
from jit_agent.llm import _quarantined_evidence
from jit_agent.model_evidence_budget import configured_model_evidence_budget, validate_rendered_evidence
from jit_agent.models import MemoryPacket
from jit_agent.percept_response_runtime import ResponseMemoryPackage, _compose_memory_package
from jit_agent.percept_response_worker import UserPromptLLM
from jit_agent.percept_triage import TriageDecision, TaskClass, deterministic_triage, semantic_triage
from jit_agent.response_policy import HistoricalEvidenceScope, ResponsePolicy, ResponseSurfaceMode, source_types_for_scope
from jit_agent.situation_runtime import SITUATION_PROTOCOL, SituationStage, SituationTask
from jit_agent.worker_protocol import deterministic_worker_step_id
from jit_agent.worker_store import complete_worker_claim, load_worker_claim_envelope, load_worker_result, release_worker_claim

TRIAGE_MAX_TOKENS = 512
SITUATION_MODEL_ITEMS = 8
_ALLOWED_LLM_KINDS = {
    SituationStage.MEMORY: frozenset(),
    SituationStage.TRIAGE: frozenset({"PERCEPT_TRIAGE"}),
    SituationStage.EXECUTE: frozenset(),
    SituationStage.COMPOSE: frozenset({"V2_MEMORY_SUFFICIENCY_USER_PROMPT"}),
    SituationStage.RESPOND: frozenset({"FINAL_RESPONSE_V2"}),
    SituationStage.PERSIST: frozenset(),
}


class SituationLLM(UserPromptLLM):
    def _require_stage_specialization(self, kind: str) -> None:
        if self._artifact_stage not in _ALLOWED_LLM_KINDS or kind not in _ALLOWED_LLM_KINDS[self._artifact_stage]:
            raise RuntimeError(f"{self._artifact_stage} cannot invoke LLM role {kind}")

    def triage(self, policy, evidence: str) -> TriageDecision:
        return semantic_triage(policy, evidence, lambda system, data, schema: self._structured_with_evidence(
            "PERCEPT_TRIAGE", system, "Classify the operational need under the application policy.",
            _quarantined_evidence(data), schema, TRIAGE_MAX_TOKENS,
        ))


def _output(conn, task: SituationTask, stage: SituationStage, scheduler_key: str) -> dict:
    result = load_worker_result(conn, deterministic_worker_step_id(task.assignment_id, stage.value), scheduler_key=scheduler_key)
    if result is None:
        raise RuntimeError(f"missing durable prerequisite: {stage.value}")
    return result.output


def _source_types(domains) -> list:
    return sorted({event_type for domain in domains for event_type in source_types_for_scope(domain)}, key=lambda item: item.value)


def _situation_view(task: SituationTask) -> dict:
    situation = task.situation
    return {"epistemic_status": "DERIVED", "snapshot_id": str(situation.snapshot_id),
            "prediction_error": situation.prediction_error, "retention_hint": situation.retention_hint,
            "observed_state": [value.model_dump(mode="json") for value in situation.observed_state[-SITUATION_MODEL_ITEMS:]],
            "prediction_errors": [value.model_dump(mode="json") for value in situation.prediction_errors[-SITUATION_MODEL_ITEMS:]],
            "percept_excerpt": list(task.percept.input_buffer.segments),
            "excerpt_incomplete": task.percept.input_buffer.truncated,
            "state_incomplete": len(situation.observed_state) > SITUATION_MODEL_ITEMS,
            "provenance": [str(value) for value in situation.provenance[-SITUATION_MODEL_ITEMS:]]}


def execute_situation_stage(conn, task: SituationTask, stage: SituationStage, *, llm=None, scheduler_key: str) -> dict:
    if stage is SituationStage.MEMORY:
        packet = jit_memory.request_attention_activation(
            conn, conversation_id=task.conversation_id, correlation_id=task.correlation_id,
            requesting_component=f"situation-aperture:{task.task_id}",
            need=jit_memory.build_memory_need(
                "\n".join(task.percept.input_buffer.segments), include_persisted_history=True,
                conversation_id=None, source_types=_source_types(task.policy.evidence_domains),
            ), before_global_seq=task.before_global_seq, memory_request_id=uuid5(task.task_id, "memory-aperture"),
        )
        return {"memory_packet": packet.model_dump(mode="json"), "source_policy": task.policy.model_dump(mode="json")}
    if stage is SituationStage.TRIAGE:
        memory = _output(conn, task, SituationStage.MEMORY, scheduler_key)
        decision = deterministic_triage(task.percept, task.situation, task.policy)
        if decision is not None:
            return {"decision": decision.model_dump(mode="json"), "inference_used": False}
        if llm is None:
            raise RuntimeError("opaque non-user semantics require a guarded triage specialist")
        packet = MemoryPacket.model_validate(memory["memory_packet"])
        evidence = json.dumps(_situation_view(task), ensure_ascii=False) + "\n" + format_authority_bound_memory_packet(packet)
        validate_rendered_evidence((evidence,), budget=configured_model_evidence_budget())
        llm._set_artifact_evidence_refs(tuple(f"event:{item.source_event_id}" for item in packet.items) +
                                      (f"situation:{task.situation.snapshot_id}",))
        decision = llm.triage(task.policy, evidence)
        return {"decision": decision.model_dump(mode="json"), "inference_used": True}
    if stage is SituationStage.EXECUTE:
        decision = TriageDecision.model_validate(_output(conn, task, SituationStage.TRIAGE, scheduler_key)["decision"])
        if not decision.task_required:
            return {"work_results": [], "task_required": False}
        action_id = uuid5(task.task_id, "registered-action")
        issue_action(conn, action_id=action_id, task_id=task.task_id, at=task.created_at,
                     entity_refs=task.situation.entity_refs[:16])
        saved = get_record(conn, "action_execution", str(action_id))
        if saved is None:
            if decision.candidate_task_class is TaskClass.CONSOLIDATE:
                cursor = json.loads(task.percept.normalized_text).get("after_key", "")
                projection = get_record(conn, "consolidation", str(action_id)) or consolidate_page(conn, action_id=action_id, after_key=cursor)
                result_data = {"consolidation_id": str(action_id), "projection_count": len(projection["projections"]),
                               "next_cursor": projection["next_cursor"], "canonical_records_modified": False}
            else:
                result_data = _situation_view(task)
                result_data["operation"] = decision.candidate_task_class.value
                result_data["meaning"] = "Observed discrepancies recorded for reconciliation; external state was not changed."
            saved = {"work_results": [{"capability_id": f"situation.{decision.candidate_task_class.value.casefold()}",
                                        "executor": "application", "result_data": result_data}], "task_required": True, "observed_status": "SUCCEEDED"}
        receipt_id = put_record(conn, "action_execution", str(action_id), saved, revision="1")
        receipt = event_store.get_event_by_id(conn, receipt_id)
        # Read-after-write confirms our registered local operation. It makes no
        # claim that an external command has completed or a physical fault healed.
        if receipt is None or get_record(conn, "action_execution", str(action_id)) != saved:
            raise RuntimeError("action completion could not be observed")
        observe_action_outcome(conn, action_id=action_id, receipt_event_id=receipt_id,
                               status="SUCCEEDED", observed_at=receipt.created_at)
        return saved
    if stage is SituationStage.COMPOSE:
        packet = MemoryPacket.model_validate(_output(conn, task, SituationStage.MEMORY, scheduler_key)["memory_packet"])
        if not task.policy.response_required or not task.policy.natural_language_response:
            return {"skipped": True}
        if llm is None:
            raise RuntimeError("natural response requires a separate memory specialist")
        # Composer receives persistent memory alone; work results bypass it.
        package = _compose_memory_package(conn, llm, task, packet, _source_types(task.policy.evidence_domains))
        return {"memory_package": package.model_dump(mode="json")}
    if stage is SituationStage.RESPOND:
        execution = _output(conn, task, SituationStage.EXECUTE, scheduler_key)
        if not task.policy.response_required:
            return {"response_required": False, "response_text": None}
        if task.policy.natural_language_response:
            if llm is None:
                raise RuntimeError("natural response requires a separate final responder")
            package = ResponseMemoryPackage.model_validate(_output(conn, task, SituationStage.COMPOSE, scheduler_key)["memory_package"])
            text = llm.generate_final_response(
                task.user_text, package, tuple(execution["work_results"]) or
                ({"capability_id": "situation.observation", "result_data": _situation_view(task)},),
                response_policy=ResponsePolicy(evidence_scope=HistoricalEvidenceScope.DERIVED_INTERNAL,
                                               surface_mode=ResponseSurfaceMode.NATURAL_LANGUAGE),
            )
        else:
            text = json.dumps({"situation": _situation_view(task), "work": execution}, ensure_ascii=False, sort_keys=True)
        return {"response_required": True, "response_text": text}
    if stage is SituationStage.PERSIST:
        response = _output(conn, task, SituationStage.RESPOND, scheduler_key)
        put_record(conn, "situation_completion", str(task.task_id), response, revision="1")
        return response
    raise ValueError("unsupported situation stage")


def execute_claimed_situation_step(conn, *, claim_id: UUID, worker_id: str, scheduler_key: str, llm_factory=SituationLLM) -> dict:
    envelope = load_worker_claim_envelope(conn, claim_id, worker_id=worker_id, scheduler_key=scheduler_key)
    task = SituationTask.model_validate(get_record(conn, "situation_task", str(envelope.step.task_id)))
    if task.protocol_version != SITUATION_PROTOCOL or task.assignment_id != envelope.step.assignment_id:
        raise ValueError("situation task protocol or assignment mismatch")
    stage = SituationStage(envelope.step.step_key)
    artifact_journal.write_percept_artifact(
        interaction_id=task.task_id, conversation_id=task.conversation_id, correlation_id=task.correlation_id,
        task_id=task.task_id, user_text=task.user_text, user_prompt_event_id=task.user_prompt_event_id,
        percept=task.percept, salience_assessment=task.situation.salience,
    )
    try:
        recovered = artifact_journal.load_stage_result_artifact(task.task_id, stage.value)
        if recovered:
            output = recovered["output"]
        else:
            uses_model = (stage is SituationStage.TRIAGE and deterministic_triage(task.percept, task.situation, task.policy) is None) or (
                stage in {SituationStage.COMPOSE, SituationStage.RESPOND} and task.policy.response_required and task.policy.natural_language_response)
            llm = llm_factory(interaction=task, stage=stage, claim_id=claim_id) if uses_model else None
            output = execute_situation_stage(conn, task, stage, llm=llm, scheduler_key=scheduler_key)
            artifact_journal.write_stage_result_artifact(
                interaction_id=task.task_id, conversation_id=task.conversation_id, correlation_id=task.correlation_id,
                task_id=task.task_id, assignment_id=task.assignment_id, stage=stage.value,
                output=output, output_refs=[f"situation:{task.situation.snapshot_id}"],
            )
        complete_worker_claim(conn, claim_id=claim_id, worker_id=worker_id, output=output,
                              output_refs=[f"situation:{task.situation.snapshot_id}"], scheduler_key=scheduler_key)
        return output
    except Exception as exc:
        artifact_journal.write_stage_error_artifact(
            interaction_id=task.task_id, conversation_id=task.conversation_id, correlation_id=task.correlation_id,
            task_id=task.task_id, assignment_id=task.assignment_id, stage=stage.value, claim_id=claim_id,
            error_type=type(exc).__name__, message=str(exc),
        )
        release_worker_claim(conn, claim_id=claim_id, worker_id=worker_id, scheduler_key=scheduler_key)
        raise


def main() -> None:
    with db.get_connection() as conn:
        execute_claimed_situation_step(conn, claim_id=UUID(os.environ["PROMETHEIST_WORKER_CLAIM_ID"]),
                                       worker_id=os.environ["PROMETHEIST_WORKER_ID"],
                                       scheduler_key=os.environ["PROMETHEIST_WORKER_SCHEDULER_KEY"])


if __name__ == "__main__":
    main()
