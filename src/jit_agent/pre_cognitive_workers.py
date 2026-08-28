"""Pre-cognitive transient worker pipeline for production interaction execution.

This module deliberately keeps the durable v0.7 interaction stage keys so that
worker claims, restart recovery, and persisted assignments remain compatible,
while replacing the recurrent capability-router semantics with bounded,
disposable cognition:

1. deterministic reference/working-state inspection;
2. JIT attention aperture + one fresh pre-cognitive assessment;
3. deterministic capability execution, followed only when needed by one fresh
   post-capability assessment and one bounded follow-up tranche;
4. one fresh response worker;
5. deterministic persistence.

No model invocation inherits a previous model context. Durable continuity comes
only from PostgreSQL state, exact source events, MemoryPackets, capability
results, and the closed cognitive-control records persisted here.
"""
from __future__ import annotations

from enum import Enum
import json
from typing import Any, Protocol
from uuid import UUID, uuid5

import psycopg
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from jit_agent import event_store
from jit_agent.attention_aperture import ATTENTION_APERTURE_VERSION, open_attention_aperture
from jit_agent.attention_store import DEFAULT_SCHEDULER_KEY
from jit_agent.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityDescriptor,
    CapabilityExecutionPlan,
    CapabilityRegistry,
    deterministic_selected_capability_step_id,
)
from jit_agent.capability_runtime import CapabilityExecution, execute_registered_capability
from jit_agent.interaction_policy import (
    CapabilityResultSummary,
    DurableInteraction,
    InteractionAction,
    InteractionDecision,
    InteractionStage,
    deterministic_capability_memory_request_id,
)
from jit_agent.interaction_store import load_interaction_by_task
from jit_agent.interaction_working_state import activate_working_state, load_working_state
from jit_agent.models import EventType, MemoryPacket
from jit_agent.worker_protocol import WorkerClaimEnvelope, deterministic_worker_step_id
from jit_agent.worker_store import (
    complete_worker_claim,
    load_worker_claim_envelope,
    load_worker_result,
    release_worker_claim,
)


PRE_COGNITIVE_WORKER_SCHEME_VERSION = "pre-cognitive-transient-workers-v1"
SOURCE = "pre_cognitive_transient_worker"
_MAX_FINAL_MEMORY_ITEMS = 20
_RESEARCH_EVIDENCE_EXECUTORS = {"deeper_research", "cross_reference"}


class CognitivePhase(str, Enum):
    PRE_CAPABILITY = "PRE_CAPABILITY"
    POST_CAPABILITY = "POST_CAPABILITY"


class CognitiveDisposition(str, Enum):
    """Closed control disposition; never a free-form plan."""

    RESPOND = "RESPOND"
    ACQUIRE_CAPABILITIES = "ACQUIRE_CAPABILITIES"
    ABSTAIN = "ABSTAIN"


class IntentMode(str, Enum):
    CONVERSE = "CONVERSE"
    RECALL = "RECALL"
    ANALYZE = "ANALYZE"
    TRANSFORM = "TRANSFORM"
    ACT = "ACT"
    RESEARCH = "RESEARCH"
    OTHER = "OTHER"


class EvidenceState(str, Enum):
    CURRENT_INPUT_SUFFICIENT = "CURRENT_INPUT_SUFFICIENT"
    ACTIVATED_MEMORY_SUFFICIENT = "ACTIVATED_MEMORY_SUFFICIENT"
    MORE_INTERNAL_EVIDENCE_REQUIRED = "MORE_INTERNAL_EVIDENCE_REQUIRED"
    CAPABILITY_RESULT_REQUIRED = "CAPABILITY_RESULT_REQUIRED"
    INSUFFICIENT_AFTER_AVAILABLE_WORK = "INSUFFICIENT_AFTER_AVAILABLE_WORK"


class ClaimScope(str, Enum):
    CURRENT_INPUT = "CURRENT_INPUT"
    USER_HISTORY = "USER_HISTORY"
    SYSTEM_HISTORY = "SYSTEM_HISTORY"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    CAPABILITY_OUTPUT = "CAPABILITY_OUTPUT"


class RequirementFlag(str, Enum):
    EXACT_SOURCE = "EXACT_SOURCE"
    TEMPORAL_RESOLUTION = "TEMPORAL_RESOLUTION"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    DEEPER_RECALL = "DEEPER_RECALL"
    CROSS_REFERENCE = "CROSS_REFERENCE"
    FOCUSED_RECALL = "FOCUSED_RECALL"
    EXTERNAL_CAPABILITY = "EXTERNAL_CAPABILITY"
    ABSTAIN_IF_UNSUPPORTED = "ABSTAIN_IF_UNSUPPORTED"


class PreCognitiveAssessment(BaseModel):
    """Small closed control record emitted by a fresh cognition worker.

    The model may classify intent/evidence/claims/requirements and select indices
    from an application-owned catalog. It may not author capability names,
    retrieval queries, event ids, tool arguments, ordering, or prose plans.
    """

    model_config = ConfigDict(extra="forbid")

    scheme_version: str = PRE_COGNITIVE_WORKER_SCHEME_VERSION
    phase: CognitivePhase
    disposition: CognitiveDisposition
    intent_mode: IntentMode
    evidence_state: EvidenceState
    claim_scopes: list[ClaimScope] = Field(default_factory=list, max_length=5)
    requirement_flags: list[RequirementFlag] = Field(default_factory=list, max_length=8)
    capability_indices: list[int] = Field(default_factory=list, max_length=8)

    @field_validator("claim_scopes", "requirement_flags")
    @classmethod
    def unique_enums(cls, values: list[Any]) -> list[Any]:
        if len(values) != len(set(values)):
            raise ValueError("closed assessment lists must not contain duplicates")
        return values

    @field_validator("capability_indices")
    @classmethod
    def valid_indices(cls, values: list[int]) -> list[int]:
        if any(index < 0 for index in values):
            raise ValueError("capability indices must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("capability indices must not contain duplicates")
        return values

    @model_validator(mode="after")
    def validate_disposition(self) -> "PreCognitiveAssessment":
        if self.scheme_version != PRE_COGNITIVE_WORKER_SCHEME_VERSION:
            raise ValueError("unsupported pre-cognitive worker scheme version")
        if self.disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES:
            if not self.capability_indices:
                raise ValueError("ACQUIRE_CAPABILITIES requires capability indices")
        elif self.capability_indices:
            raise ValueError("only ACQUIRE_CAPABILITIES may select capabilities")
        if (
            self.disposition is CognitiveDisposition.ABSTAIN
            and self.evidence_state is not EvidenceState.INSUFFICIENT_AFTER_AVAILABLE_WORK
        ):
            raise ValueError("ABSTAIN requires terminal insufficient-evidence state")
        return self

    def validate_catalog(self, catalog: tuple[CapabilityDescriptor, ...]) -> None:
        if any(index >= len(catalog) for index in self.capability_indices):
            raise ValueError("pre-cognitive assessment selected a capability outside the catalog")


class PreCognitiveLLM(Protocol):
    """Optional explicit adapter interface used by tests or alternate model clients."""

    def assess_pre_cognition(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        *,
        phase: CognitivePhase,
        completed_results: tuple[CapabilityResultSummary, ...] = (),
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> PreCognitiveAssessment: ...


_PRE_COGNITIVE_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist pre-cognitive worker. You have no
inherited transcript, hidden conversation state, or previous model context.
Everything you may use is in the current percept, the bounded activated evidence,
structured completed-capability results, and the application-owned numbered
capability catalog supplied to this call.

Your job is not to answer the user. Produce only the closed structured assessment.
Classify:
- the broad intent mode;
- whether currently supplied evidence is sufficient;
- which claim scopes the eventual response will rely on;
- which closed requirement flags apply; and
- only when more work is genuinely required, the smallest set of capability
  indices from the supplied catalog needed to acquire that evidence/result.

Never write capability names, queries, tool arguments, event ids, retrieval text,
ordering instructions, plans, explanations, summaries, claims, or response prose.
The application owns capability identity, dependency closure, scheduling,
resource admission, ordering, execution, provenance, and persistence.

Use RESPOND when the current input plus activated evidence is sufficient. Use
ACQUIRE_CAPABILITIES only when one or more catalog capabilities are required.
Use ABSTAIN only when the available work represented by this phase is exhausted
and evidence remains insufficient. During POST_CAPABILITY, the catalog contains
only legal bounded follow-up work; do not ask to repeat work that is absent from
that catalog.
"""


def _format_memory_for_cognition(packet: MemoryPacket) -> str:
    if not packet.items:
        return "\n\n[Activated evidence]\nsupported: false\nitems: []"
    items = []
    for index, item in enumerate(packet.items):
        items.append(
            f"item: {index}\n"
            f"event_type: {item.event_type.value}\n"
            f"content: {item.content}"
        )
    return (
        "\n\n[Activated evidence]\n"
        f"supported: {str(packet.supported).lower()}\n"
        + "\n\n".join(items)
    )


def _format_catalog(catalog: tuple[CapabilityDescriptor, ...]) -> str:
    if not catalog:
        return "\n\n[Capability catalog]\nnone"
    return "\n\n[Capability catalog]\n" + "\n".join(
        f"{index}: {item.capability_id} | {item.kind.value} | {item.description}"
        for index, item in enumerate(catalog)
    )


def _format_completed_results(results: tuple[CapabilityResultSummary, ...]) -> str:
    if not results:
        return "\n\n[Completed capability results]\nnone"
    return "\n\n[Completed capability results]\n" + "\n".join(
        (
            f"round={item.round_index} capability={item.capability_id} "
            f"supported={item.supported} item_count={item.item_count} "
            f"result_keys={','.join(item.result_keys) or 'none'}"
        )
        for item in results
    )


def _format_capability_result_data(results: tuple[dict[str, Any], ...]) -> str:
    if not results:
        return ""
    return "\n\n[Structured capability results]\n" + json.dumps(
        list(results), sort_keys=True, default=str, separators=(",", ":")
    )


def _assessment_from_legacy_decision(
    decision: InteractionDecision,
    *,
    phase: CognitivePhase,
    memory_packet: MemoryPacket,
) -> PreCognitiveAssessment:
    """Compatibility fallback for fake/alternate clients that only implement classify."""

    if decision.next_action is InteractionAction.USE_CAPABILITIES:
        return PreCognitiveAssessment(
            phase=phase,
            disposition=CognitiveDisposition.ACQUIRE_CAPABILITIES,
            intent_mode=IntentMode.OTHER,
            evidence_state=EvidenceState.CAPABILITY_RESULT_REQUIRED,
            claim_scopes=[ClaimScope.CURRENT_INPUT],
            requirement_flags=[RequirementFlag.ABSTAIN_IF_UNSUPPORTED],
            capability_indices=list(decision.capability_indices),
        )
    return PreCognitiveAssessment(
        phase=phase,
        disposition=CognitiveDisposition.RESPOND,
        intent_mode=IntentMode.OTHER,
        evidence_state=(
            EvidenceState.ACTIVATED_MEMORY_SUFFICIENT
            if memory_packet.items
            else EvidenceState.CURRENT_INPUT_SUFFICIENT
        ),
        claim_scopes=[ClaimScope.CURRENT_INPUT],
        requirement_flags=[],
        capability_indices=[],
    )


def assess_pre_cognition(
    llm: Any,
    prompt: str,
    memory_packet: MemoryPacket,
    capability_catalog: tuple[CapabilityDescriptor, ...],
    *,
    phase: CognitivePhase,
    completed_results: tuple[CapabilityResultSummary, ...] = (),
    capability_results: tuple[dict[str, Any], ...] = (),
) -> PreCognitiveAssessment:
    """Run one independent bounded cognition call with compatibility fallbacks."""

    explicit = getattr(llm, "assess_pre_cognition", None)
    if callable(explicit):
        assessment = explicit(
            prompt,
            memory_packet,
            capability_catalog,
            phase=phase,
            completed_results=completed_results,
            capability_results=capability_results,
        )
        assessment = PreCognitiveAssessment.model_validate(assessment)
        assessment.validate_catalog(capability_catalog)
        return assessment

    structured = getattr(llm, "_structured", None)
    if callable(structured):
        user = (
            f"phase: {phase.value}\n"
            + prompt
            + _format_memory_for_cognition(memory_packet)
            + _format_completed_results(completed_results)
            + _format_capability_result_data(capability_results)
            + _format_catalog(capability_catalog)
        )
        last_error: Exception | None = None
        for token_cap in (96, 192):
            try:
                content = structured(
                    f"PRE_COGNITIVE_{phase.value}",
                    _PRE_COGNITIVE_SYSTEM_PROMPT,
                    user,
                    PreCognitiveAssessment.model_json_schema(),
                    token_cap,
                )
                assessment = PreCognitiveAssessment.model_validate_json(content)
                if assessment.phase is not phase:
                    raise ValueError("pre-cognitive assessment returned the wrong phase")
                assessment.validate_catalog(capability_catalog)
                return assessment
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"pre-cognitive assessment failed to validate: {last_error}")

    classify = getattr(llm, "classify", None)
    if not callable(classify):
        raise TypeError("LLM client provides neither pre-cognitive nor legacy routing interface")
    decision = classify(
        prompt,
        memory_packet,
        capability_catalog,
        completed_results,
        capability_results,
    )
    assessment = _assessment_from_legacy_decision(
        InteractionDecision.model_validate(decision),
        phase=phase,
        memory_packet=memory_packet,
    )
    assessment.validate_catalog(capability_catalog)
    return assessment


def newly_exposed_follow_up_catalog(
    registry: CapabilityRegistry,
    initial_catalog: tuple[CapabilityDescriptor, ...],
    executed_capability_ids: tuple[str, ...],
) -> tuple[CapabilityDescriptor, ...]:
    """Expose only capabilities made newly legal by the completed first tranche."""

    if not executed_capability_ids:
        return ()
    initial_ids = {item.capability_id for item in initial_catalog}
    expanded = registry.capability_catalog(executed_capability_ids=executed_capability_ids)
    return tuple(
        item
        for item in expanded
        if item.capability_id not in initial_ids
        and item.capability_id not in set(executed_capability_ids)
    )


def compose_memory_context(
    interaction_id: UUID,
    aperture_packet: MemoryPacket,
    executions: list[CapabilityExecution],
    *,
    tranche_index: int,
) -> MemoryPacket:
    """Compose bounded exact-source working context without rewriting source evidence."""

    packets = [
        execution.memory_packet
        for execution in reversed(executions)
        if execution.memory_packet is not None
    ]
    items = []
    seen = set()
    for packet in [*packets, aperture_packet]:
        for item in packet.items:
            if item.source_event_id in seen:
                continue
            seen.add(item.source_event_id)
            items.append(item.model_copy(deep=True))
            if len(items) == _MAX_FINAL_MEMORY_ITEMS:
                break
        if len(items) == _MAX_FINAL_MEMORY_ITEMS:
            break

    need = aperture_packet.need.model_copy(deep=True)
    need.limit = _MAX_FINAL_MEMORY_ITEMS
    return MemoryPacket(
        memory_request_id=uuid5(
            interaction_id,
            f"pre-cognitive-context:{tranche_index}",
        ),
        need=need,
        supported=bool(items),
        items=items,
        retrieval_trace={
            "composition": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "tranche_index": tranche_index,
            "initial_memory_request_id": str(aperture_packet.memory_request_id),
            "capability_memory_request_ids": [
                str(packet.memory_request_id) for packet in packets
            ],
        },
    )


def capability_result_summaries(
    executions: list[CapabilityExecution],
) -> tuple[CapabilityResultSummary, ...]:
    return tuple(
        CapabilityResultSummary(
            round_index=execution.round_index,
            capability_id=execution.capability_id,
            supported=(
                execution.memory_packet.supported
                if execution.memory_packet is not None
                else None
            ),
            item_count=(
                len(execution.memory_packet.items)
                if execution.memory_packet is not None
                else None
            ),
            result_keys=sorted(execution.result_data),
            result_data=dict(execution.result_data),
        )
        for execution in executions
    )


def structured_capability_result(execution: CapabilityExecution) -> dict[str, Any]:
    return {
        "round_index": execution.round_index,
        "plan_position": execution.plan_position,
        "capability_id": execution.capability_id,
        "executor": execution.executor,
        "result_data": dict(execution.result_data),
        "memory_request_id": (
            str(execution.memory_packet.memory_request_id)
            if execution.memory_packet is not None
            else None
        ),
    }


def cognitive_brief_result(
    pre: PreCognitiveAssessment,
    post: PreCognitiveAssessment | None,
    *,
    follow_up_executed: bool,
) -> dict[str, Any]:
    """Non-evidentiary control metadata for the final fresh response worker."""

    effective = post or pre
    return {
        "round_index": -1,
        "plan_position": -1,
        "capability_id": "pre_cognitive_brief",
        "executor": "application_control",
        "result_data": {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "intent_mode": effective.intent_mode.value,
            "evidence_state": effective.evidence_state.value,
            "claim_scopes": [value.value for value in effective.claim_scopes],
            "requirement_flags": [value.value for value in effective.requirement_flags],
            "acquisition_disposition": effective.disposition.value,
            "follow_up_executed": follow_up_executed,
        },
        "memory_request_id": None,
    }


def _stage_result(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    stage: InteractionStage,
    scheduler_key: str,
) -> dict[str, Any]:
    step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
    result = load_worker_result(conn, step_id, scheduler_key=scheduler_key)
    if result is None:
        raise RuntimeError(f"interaction stage {stage.value} is incomplete")
    return dict(result.output)


def _record_assessment_event(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    *,
    phase: CognitivePhase,
    assessment: PreCognitiveAssessment,
    catalog: tuple[CapabilityDescriptor, ...],
    plan: CapabilityExecutionPlan,
) -> None:
    event_store.record_event(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=SOURCE,
        payload={
            "kind": "PRE_COGNITIVE_ASSESSMENT",
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "phase": phase.value,
            "assessment": assessment.model_dump(mode="json"),
            "capability_catalog": [item.model_dump(mode="json") for item in catalog],
            "execution_plan": plan.model_dump(mode="json"),
        },
        event_id=uuid5(interaction.interaction_id, f"pre-cognitive:{phase.value}"),
    )


def _execute_plan(
    conn: psycopg.Connection,
    llm: Any,
    *,
    interaction: DurableInteraction,
    parent_step_id: UUID,
    registry: CapabilityRegistry,
    plan: CapabilityExecutionPlan,
    tranche_index: int,
    candidate_packet: MemoryPacket,
    prior_executions: list[CapabilityExecution],
    last_research_packet: MemoryPacket | None,
) -> tuple[list[CapabilityExecution], MemoryPacket | None, list[str]]:
    new_executions: list[CapabilityExecution] = []
    output_refs: list[str] = []
    already_executed = {item.capability_id for item in prior_executions}

    for plan_position, plan_item in enumerate(plan.items):
        if plan_item.capability_id in already_executed:
            continue
        registration = registry.get(plan_item.capability_id)
        selected_step_id = deterministic_selected_capability_step_id(
            parent_step_id,
            tranche_index,
            plan_item.capability_id,
        )
        memory_request_id = deterministic_capability_memory_request_id(
            interaction.interaction_id,
            tranche_index,
            plan_item.capability_id,
        )
        if registration.executor == "focused_recall":
            if last_research_packet is None or not last_research_packet.items:
                raise RuntimeError("focused_recall requires prior non-empty broader research")
            input_packet = last_research_packet
        else:
            input_packet = candidate_packet

        execution = execute_registered_capability(
            conn,
            llm,
            registration=registration,
            capability_execution_id=selected_step_id,
            requester_task_id=interaction.task_id,
            requester_step_id=selected_step_id,
            round_index=tranche_index,
            plan_position=plan_position,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            task_text=interaction.user_text,
            before_global_seq=interaction.before_global_seq,
            memory_request_id=memory_request_id,
            candidate_packet=input_packet,
        )
        new_executions.append(execution)
        if execution.memory_packet is not None:
            output_refs.append(f"memory-request:{execution.memory_packet.memory_request_id}")
        if (
            execution.executor in _RESEARCH_EVIDENCE_EXECUTORS
            and execution.memory_packet is not None
            and execution.memory_packet.items
        ):
            last_research_packet = execution.memory_packet.model_copy(deep=True)

    return new_executions, last_research_packet, output_refs


def execute_claimed_transient_interaction_step(
    conn: psycopg.Connection,
    llm: Any,
    *,
    claim_id: UUID,
    worker_id: str,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> InteractionStage:
    """Execute one already-guarded durable stage with disposable cognition."""

    envelope = load_worker_claim_envelope(
        conn,
        claim_id,
        worker_id=worker_id,
        scheduler_key=scheduler_key,
    )
    interaction = load_interaction_by_task(
        conn,
        envelope.step.task_id,
        scheduler_key=scheduler_key,
    )
    stage = InteractionStage(envelope.step.step_key)
    try:
        output, output_refs = _execute_stage(
            conn,
            llm,
            envelope,
            interaction=interaction,
            scheduler_key=scheduler_key,
            registry=registry,
        )
        complete_worker_claim(
            conn,
            claim_id=claim_id,
            worker_id=worker_id,
            output=output,
            output_refs=output_refs,
            scheduler_key=scheduler_key,
        )
        return stage
    except Exception as exc:
        event_store.record_event(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            event_type=EventType.ERROR,
            source=SOURCE,
            payload={
                "stage": stage.value,
                "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            event_id=uuid5(claim_id, "pre-cognitive-error-event"),
        )
        release_worker_claim(
            conn,
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )
        raise


def _execute_stage(
    conn: psycopg.Connection,
    llm: Any,
    envelope: WorkerClaimEnvelope,
    *,
    interaction: DurableInteraction,
    scheduler_key: str,
    registry: CapabilityRegistry,
) -> tuple[dict[str, Any], list[str]]:
    stage = InteractionStage(envelope.step.step_key)

    if stage is InteractionStage.RESOLVE_REFERENCES:
        return {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "working_state_available": (
                load_working_state(conn, interaction.conversation_id) is not None
            ),
        }, []

    if stage is InteractionStage.SELECT_CAPABILITY:
        aperture_packet = open_attention_aperture(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            requester_task_id=interaction.task_id,
            user_text=interaction.user_text,
            before_global_seq=interaction.before_global_seq,
        )
        catalog = registry.capability_catalog()
        assessment = assess_pre_cognition(
            llm,
            interaction.user_text,
            aperture_packet,
            catalog,
            phase=CognitivePhase.PRE_CAPABILITY,
        )
        plan = registry.plan_execution(catalog, assessment.capability_indices)
        _record_assessment_event(
            conn,
            interaction,
            phase=CognitivePhase.PRE_CAPABILITY,
            assessment=assessment,
            catalog=catalog,
            plan=plan,
        )
        return {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "attention_aperture_version": ATTENTION_APERTURE_VERSION,
            "aperture_packet": aperture_packet.model_dump(mode="json"),
            "assessment": assessment.model_dump(mode="json"),
            "capability_catalog": [item.model_dump(mode="json") for item in catalog],
            "execution_plan": plan.model_dump(mode="json"),
        }, [f"memory-request:{aperture_packet.memory_request_id}"]

    if stage is InteractionStage.EXECUTE_CAPABILITY:
        selection = _stage_result(
            conn, interaction, InteractionStage.SELECT_CAPABILITY, scheduler_key
        )
        aperture_packet = MemoryPacket.model_validate(selection["aperture_packet"])
        pre_assessment = PreCognitiveAssessment.model_validate(selection["assessment"])
        initial_catalog = tuple(
            CapabilityDescriptor.model_validate(item)
            for item in selection["capability_catalog"]
        )
        initial_plan = CapabilityExecutionPlan.model_validate(selection["execution_plan"])

        executions: list[CapabilityExecution] = []
        output_refs: list[str] = []
        last_research_packet: MemoryPacket | None = None
        post_assessment: PreCognitiveAssessment | None = None
        follow_up_catalog: tuple[CapabilityDescriptor, ...] = ()
        follow_up_plan = registry.plan_execution((), [])
        follow_up_executed = False

        if pre_assessment.disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES:
            first, last_research_packet, refs = _execute_plan(
                conn,
                llm,
                interaction=interaction,
                parent_step_id=envelope.step.step_id,
                registry=registry,
                plan=initial_plan,
                tranche_index=0,
                candidate_packet=aperture_packet,
                prior_executions=executions,
                last_research_packet=last_research_packet,
            )
            executions.extend(first)
            output_refs.extend(refs)
            context_packet = compose_memory_context(
                interaction.interaction_id,
                aperture_packet,
                executions,
                tranche_index=1,
            )
            usable_ids = tuple(
                item.capability_id
                for item in executions
                if item.result_data.get("supported") is not False
            )
            follow_up_catalog = newly_exposed_follow_up_catalog(
                registry,
                initial_catalog,
                usable_ids,
            )
            completed = capability_result_summaries(executions)
            structured = tuple(structured_capability_result(item) for item in executions)
            post_assessment = assess_pre_cognition(
                llm,
                interaction.user_text,
                context_packet,
                follow_up_catalog,
                phase=CognitivePhase.POST_CAPABILITY,
                completed_results=completed,
                capability_results=structured,
            )
            follow_up_plan = registry.plan_execution(
                follow_up_catalog,
                post_assessment.capability_indices,
            )
            _record_assessment_event(
                conn,
                interaction,
                phase=CognitivePhase.POST_CAPABILITY,
                assessment=post_assessment,
                catalog=follow_up_catalog,
                plan=follow_up_plan,
            )

            if post_assessment.disposition is CognitiveDisposition.ACQUIRE_CAPABILITIES:
                second, last_research_packet, refs = _execute_plan(
                    conn,
                    llm,
                    interaction=interaction,
                    parent_step_id=envelope.step.step_id,
                    registry=registry,
                    plan=follow_up_plan,
                    tranche_index=1,
                    candidate_packet=context_packet,
                    prior_executions=executions,
                    last_research_packet=last_research_packet,
                )
                executions.extend(second)
                output_refs.extend(refs)
                follow_up_executed = bool(second)

        final_packet = compose_memory_context(
            interaction.interaction_id,
            aperture_packet,
            executions,
            tranche_index=2 if follow_up_executed else 1,
        )
        return {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "fast_path": not executions,
            "pre_assessment": pre_assessment.model_dump(mode="json"),
            "post_assessment": (
                post_assessment.model_dump(mode="json")
                if post_assessment is not None
                else None
            ),
            "follow_up_catalog": [item.model_dump(mode="json") for item in follow_up_catalog],
            "follow_up_plan": follow_up_plan.model_dump(mode="json"),
            "follow_up_executed": follow_up_executed,
            "executions": [item.model_dump(mode="json") for item in executions],
            "final_memory_packet": final_packet.model_dump(mode="json"),
        }, output_refs

    if stage is InteractionStage.RESPOND:
        acquisition = _stage_result(
            conn, interaction, InteractionStage.EXECUTE_CAPABILITY, scheduler_key
        )
        final_packet = MemoryPacket.model_validate(acquisition["final_memory_packet"])
        executions = [
            CapabilityExecution.model_validate(item) for item in acquisition["executions"]
        ]
        pre_assessment = PreCognitiveAssessment.model_validate(acquisition["pre_assessment"])
        post_payload = acquisition.get("post_assessment")
        post_assessment = (
            PreCognitiveAssessment.model_validate(post_payload)
            if post_payload is not None
            else None
        )
        response_inputs = [
            cognitive_brief_result(
                pre_assessment,
                post_assessment,
                follow_up_executed=bool(acquisition.get("follow_up_executed")),
            ),
            *[structured_capability_result(item) for item in executions],
        ]
        response_text = llm.respond(
            interaction.user_text,
            final_packet,
            tuple(response_inputs),
        )
        return {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "response_text": response_text,
        }, []

    response_text = str(
        _stage_result(conn, interaction, InteractionStage.RESPOND, scheduler_key)[
            "response_text"
        ]
    )
    response_event = event_store.record_event(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        event_type=EventType.INTERACTION_RESPONSE,
        source=SOURCE,
        payload={
            "text": response_text,
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
        },
        payload_text=response_text,
        event_id=uuid5(interaction.interaction_id, "event:response"),
    )
    activate_working_state(
        conn,
        interaction_id=interaction.interaction_id,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        activated_event_ids=[response_event.event_id, interaction.user_prompt_event_id],
    )
    return {
        "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
        "response_text": response_text,
        "response_event_id": str(response_event.event_id),
    }, [f"event:{response_event.event_id}"]
