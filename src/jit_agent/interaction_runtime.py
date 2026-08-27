"""Durable, attention-centric interaction execution for Increment G."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import subprocess
import sys
from uuid import UUID, uuid4, uuid5

import psycopg

from jit_agent import db, event_store
from jit_agent.attention import (
    AttentionTask,
    InterruptionPolicy,
    SchedulingMetadata,
    ServiceClass,
    TaskCriticality,
)
from jit_agent.attention_aperture import ATTENTION_APERTURE_VERSION, open_attention_aperture
from jit_agent.attention_observation import (
    HostResourceProbe,
    LocalResourceAdmissionController,
    ResourceSafetyPolicy,
)
from jit_agent.attention_resources import ProcessResourceEstimate, ResourceEstimateSource
from jit_agent.attention_store import (
    DEFAULT_SCHEDULER_KEY,
    allocate_created_seq,
    load_scheduler,
    save_scheduler,
)
from jit_agent.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityDescriptor,
    CapabilityExecutionPlan,
    CapabilityRegistry,
    deterministic_selected_capability_step_id,
)
from jit_agent.capability_runtime import CapabilityExecution, execute_registered_capability
from jit_agent.interaction_policy import (
    INTERACTION_CAPABILITIES,
    INTERACTION_STAGES,
    MAX_CAPABILITY_ROUNDS,
    CapabilityResultSummary,
    DurableInteraction,
    InteractionAction,
    InteractionDecision,
    InteractionStage,
    ReferenceAnalysis,
    deterministic_capability_memory_request_id,
    deterministic_capability_round_event_id,
    deterministic_interaction_event_id,
    deterministic_interaction_id,
    deterministic_interaction_task_id,
)
from jit_agent.interaction_store import (
    load_interaction,
    load_interaction_by_task,
    save_interaction,
)
from jit_agent.interaction_working_state import activate_working_state, load_working_state
from jit_agent.llm import LLMClient
from jit_agent.models import EventType, MemoryPacket
from jit_agent.worker_protocol import (
    WorkerClaimEnvelope,
    WorkerEffectPolicy,
    deterministic_worker_step_id,
)
from jit_agent.worker_runtime import GuardedWorkerLauncher
from jit_agent.worker_store import (
    complete_worker_claim,
    guarded_claim_worker_step,
    load_worker_claim_envelope,
    load_worker_result,
    register_worker_step,
    release_worker_claim,
)


SOURCE = "attention_interaction"
_MAX_FINAL_MEMORY_ITEMS = 20
_RESEARCH_EVIDENCE_EXECUTORS = {"deeper_research", "cross_reference"}


def begin_interaction(
    conn: psycopg.Connection,
    user_text: str,
    conversation_id: UUID,
    *,
    correlation_id: UUID | None = None,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> DurableInteraction:
    """Persist one external percept and publish its bounded worker steps."""

    normalized = user_text.strip()
    if not normalized:
        raise ValueError("user_text must not be empty")
    event_store.start_conversation(conn, conversation_id)
    correlation = correlation_id or uuid4()
    interaction_id = deterministic_interaction_id(conversation_id, correlation)
    prompt = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation,
        event_type=EventType.USER_PROMPT,
        source="user",
        payload={"text": normalized},
        payload_text=normalized,
        event_id=deterministic_interaction_event_id(interaction_id, "user-prompt"),
    )

    scheduler = load_scheduler(conn, scheduler_key=scheduler_key)
    task_id = deterministic_interaction_task_id(interaction_id)
    task = AttentionTask(
        task_id=task_id,
        task_key=f"interaction:{interaction_id}",
        created_seq=allocate_created_seq(conn),
        metadata=SchedulingMetadata(
            criticality=TaskCriticality.USER_BLOCKING,
            service_class=ServiceClass.INTERACTIVE,
            interruption_policy=InterruptionPolicy.CHECKPOINT_ONLY,
            required_capabilities=list(INTERACTION_CAPABILITIES),
            process_resource_estimate=ProcessResourceEstimate(
                cpu_units=1,
                memory_mib=4096,
                llm_slots=1,
                source=ResourceEstimateSource.CONSERVATIVE_DEFAULT,
                basis="v0.7-g bounded stateless interaction worker",
            ),
        ),
        resumable_state={"interaction_id": str(interaction_id)},
    )
    scheduler.submit(task)
    controller = LocalResourceAdmissionController(
        scheduler,
        probe=probe,
        policy=policy,
        clock=clock,
    )
    controller.plan_scheduling_epoch()
    save_scheduler(conn, scheduler, scheduler_key=scheduler_key)
    assignments = [
        value
        for value in scheduler.worker_visible_assignments()
        if value.task_id == task_id
    ]
    if len(assignments) != 1:
        raise RuntimeError("interaction was not safely admitted to one assignment")
    assignment = assignments[0]
    interaction = DurableInteraction(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation,
        user_prompt_event_id=prompt.event_id,
        before_global_seq=prompt.global_seq,
        task_id=task_id,
        assignment_id=assignment.assignment_id,
        user_text=normalized,
    )
    save_interaction(conn, interaction, scheduler_key=scheduler_key)
    _ensure_interaction_steps(conn, interaction, scheduler_key=scheduler_key)
    return interaction


def _ensure_interaction_steps(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    *,
    scheduler_key: str,
) -> None:
    """Idempotently finish step publication after an interrupted intake."""

    for stage in INTERACTION_STAGES:
        effect_policy = (
            WorkerEffectPolicy.IDEMPOTENT_WITH_KEY
            if stage
            in {
                InteractionStage.SELECT_CAPABILITY,
                InteractionStage.EXECUTE_CAPABILITY,
                InteractionStage.PERSIST_RESULT,
            }
            else WorkerEffectPolicy.NO_EXTERNAL_EFFECT
        )
        register_worker_step(
            conn,
            assignment_id=interaction.assignment_id,
            step_key=stage.value,
            capability=stage.capability,
            input_refs=[f"event:{interaction.user_prompt_event_id}"],
            effect_policy=effect_policy,
            scheduler_key=scheduler_key,
        )


def execute_next_interaction_step(
    conn: psycopg.Connection,
    llm: LLMClient,
    interaction: DurableInteraction,
    *,
    worker_id: str,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> InteractionStage | None:
    """Claim and execute the first incomplete stage with a fresh worker identity."""

    authoritative = load_interaction(
        conn,
        interaction.interaction_id,
        scheduler_key=scheduler_key,
    )
    if authoritative != interaction:
        raise ValueError("interaction input does not match authoritative state")
    _ensure_interaction_steps(conn, interaction, scheduler_key=scheduler_key)
    for stage in INTERACTION_STAGES:
        step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
        if load_worker_result(conn, step_id, scheduler_key=scheduler_key) is not None:
            continue
        attempt = guarded_claim_worker_step(
            conn,
            step_id=step_id,
            worker_id=worker_id,
            probe=probe,
            policy=policy,
            clock=clock,
            scheduler_key=scheduler_key,
        )
        if attempt.envelope is None:
            raise RuntimeError(attempt.observation.reason)
        return execute_claimed_interaction_step(
            conn,
            llm,
            claim_id=attempt.envelope.claim.claim_id,
            worker_id=worker_id,
            clock=clock,
            scheduler_key=scheduler_key,
            registry=registry,
        )
    return None


def execute_claimed_interaction_step(
    conn: psycopg.Connection,
    llm: LLMClient,
    *,
    claim_id: UUID,
    worker_id: str,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> InteractionStage:
    """Execute an already-guarded lease from a fresh child process."""

    envelope = load_worker_claim_envelope(
        conn,
        claim_id,
        worker_id=worker_id,
        clock=clock,
        scheduler_key=scheduler_key,
    )
    interaction = load_interaction_by_task(
        conn,
        envelope.step.task_id,
        scheduler_key=scheduler_key,
    )
    stage = InteractionStage(envelope.step.step_key)
    try:
        output, output_refs = _execute_claimed_stage(
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
            clock=clock,
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
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            event_id=uuid5(claim_id, "error-event"),
        )
        release_worker_claim(
            conn,
            claim_id=claim_id,
            worker_id=worker_id,
            clock=clock,
            scheduler_key=scheduler_key,
        )
        raise


def finish_interaction(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    *,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> str:
    """Close the durable task and return its already-persisted response."""

    persist_result = _stage_result(
        conn,
        interaction,
        InteractionStage.PERSIST_RESULT,
        scheduler_key,
    )
    response_text = str(persist_result["response_text"])
    scheduler = load_scheduler(conn, scheduler_key=scheduler_key)
    if scheduler.tasks[interaction.task_id].status.value != "COMPLETED":
        scheduler.complete_task(
            interaction.task_id,
            {"interaction_id": str(interaction.interaction_id), "response_text": response_text},
        )
        controller = LocalResourceAdmissionController(
            scheduler,
            probe=probe,
            policy=policy,
            clock=clock,
        )
        controller.plan_scheduling_epoch()
        save_scheduler(conn, scheduler, scheduler_key=scheduler_key)
    return response_text


def handle_interaction(
    conn: psycopg.Connection,
    llm: LLMClient,
    user_text: str,
    conversation_id: UUID,
    *,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> str:
    interaction = begin_interaction(
        conn,
        user_text,
        conversation_id,
        probe=probe,
        policy=policy,
        clock=clock,
        scheduler_key=scheduler_key,
    )
    for index in range(len(INTERACTION_STAGES)):
        executed = execute_next_interaction_step(
            conn,
            llm,
            interaction,
            worker_id=f"interaction-{interaction.interaction_id}-stage-{index}",
            probe=probe,
            policy=policy,
            clock=clock,
            scheduler_key=scheduler_key,
            registry=registry,
        )
        if executed is None:
            break
    return finish_interaction(
        conn,
        interaction,
        probe=probe,
        policy=policy,
        clock=clock,
        scheduler_key=scheduler_key,
    )


def handle_interaction_in_worker_processes(
    conn: psycopg.Connection,
    user_text: str,
    conversation_id: UUID,
    *,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    worker_lease_seconds: int = 600,
    worker_timeout_seconds: int = 660,
) -> str:
    """Run every durable interaction stage in a separately guarded process."""

    interaction = begin_interaction(
        conn,
        user_text,
        conversation_id,
        scheduler_key=scheduler_key,
    )
    launcher = GuardedWorkerLauncher(
        db.get_connection,
        scheduler_key=scheduler_key,
    )
    for stage in INTERACTION_STAGES:
        step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
        worker_id = f"interaction-{interaction.interaction_id}-{stage.value.casefold()}"
        launched = launcher.launch(
            step_id=step_id,
            worker_id=worker_id,
            command=[sys.executable, "-m", "jit_agent.interaction_worker"],
            lease_seconds=worker_lease_seconds,
        )
        try:
            return_code = launched.process.wait(timeout=worker_timeout_seconds)
        except subprocess.TimeoutExpired:
            launched.process.kill()
            launched.process.wait(timeout=10)
            raise RuntimeError(
                f"interaction worker timed out at stage {stage.value}"
            ) from None
        if return_code != 0:
            raise RuntimeError(
                f"interaction worker failed at stage {stage.value} "
                f"with exit code {return_code}"
            )
    return finish_interaction(
        conn,
        interaction,
        scheduler_key=scheduler_key,
    )


def _execute_claimed_stage(
    conn: psycopg.Connection,
    llm: LLMClient,
    envelope: WorkerClaimEnvelope,
    *,
    interaction: DurableInteraction,
    scheduler_key: str,
    registry: CapabilityRegistry,
) -> tuple[dict, list[str]]:
    stage = InteractionStage(envelope.step.step_key)
    if stage is InteractionStage.RESOLVE_REFERENCES:
        analysis = ReferenceAnalysis(
            working_state_available=(
                load_working_state(conn, interaction.conversation_id) is not None
            )
        )
        return analysis.model_dump(mode="json"), []

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
        round_record = _load_or_create_round(
            conn,
            llm,
            interaction=interaction,
            round_index=0,
            memory_packet=aperture_packet,
            catalog=catalog,
            completed_results=(),
            capability_results=(),
            registry=registry,
        )
        return {
            "attention_aperture_version": ATTENTION_APERTURE_VERSION,
            "aperture_packet": aperture_packet.model_dump(mode="json"),
            "initial_round": round_record,
        }, [f"memory-request:{aperture_packet.memory_request_id}"]

    if stage is InteractionStage.EXECUTE_CAPABILITY:
        selection = _stage_result(
            conn,
            interaction,
            InteractionStage.SELECT_CAPABILITY,
            scheduler_key,
        )
        aperture_packet = MemoryPacket.model_validate(selection["aperture_packet"])
        current_round = dict(selection["initial_round"])
        rounds: list[dict] = [current_round]
        executions: list[CapabilityExecution] = []
        catalog_eligible_ids: list[str] = []
        context_packet = aperture_packet.model_copy(deep=True)
        last_research_packet: MemoryPacket | None = None
        output_refs: list[str] = []

        for round_index in range(MAX_CAPABILITY_ROUNDS):
            decision = InteractionDecision.model_validate(current_round["decision"])
            if decision.next_action is InteractionAction.RESPOND:
                return {
                    "rounds": rounds,
                    "executions": [item.model_dump(mode="json") for item in executions],
                    "final_decision": decision.model_dump(mode="json"),
                    "final_memory_packet": context_packet.model_dump(mode="json"),
                }, output_refs

            catalog = tuple(
                CapabilityDescriptor.model_validate(item)
                for item in current_round["capability_catalog"]
            )
            persisted_plan = CapabilityExecutionPlan.model_validate(
                current_round["execution_plan"]
            )
            current_plan = registry.plan_execution(catalog, decision.capability_indices)
            if current_plan.model_dump(mode="json") != persisted_plan.model_dump(mode="json"):
                raise RuntimeError("capability configuration changed after round selection")

            for plan_position, plan_item in enumerate(persisted_plan.items):
                registration = registry.get(plan_item.capability_id)
                selected_step_id = deterministic_selected_capability_step_id(
                    envelope.step.step_id,
                    round_index,
                    plan_item.capability_id,
                )
                memory_request_id = deterministic_capability_memory_request_id(
                    interaction.interaction_id,
                    round_index,
                    plan_item.capability_id,
                )
                if registration.executor == "focused_recall":
                    if last_research_packet is None or not last_research_packet.items:
                        raise RuntimeError(
                            "focused_recall requires prior non-empty broader research"
                        )
                    candidate_packet = last_research_packet
                else:
                    candidate_packet = context_packet

                execution = execute_registered_capability(
                    conn,
                    llm,
                    registration=registration,
                    capability_execution_id=selected_step_id,
                    requester_task_id=interaction.task_id,
                    requester_step_id=selected_step_id,
                    round_index=round_index,
                    plan_position=plan_position,
                    conversation_id=interaction.conversation_id,
                    correlation_id=interaction.correlation_id,
                    task_text=interaction.user_text,
                    before_global_seq=interaction.before_global_seq,
                    memory_request_id=memory_request_id,
                    candidate_packet=candidate_packet,
                )
                executions.append(execution)
                if execution.memory_packet is not None:
                    output_refs.append(
                        f"memory-request:{execution.memory_packet.memory_request_id}"
                    )
                supported = execution.result_data.get("supported")
                if supported is not False:
                    catalog_eligible_ids.append(execution.capability_id)
                if (
                    execution.executor in _RESEARCH_EVIDENCE_EXECUTORS
                    and execution.memory_packet is not None
                    and execution.memory_packet.items
                ):
                    last_research_packet = execution.memory_packet.model_copy(deep=True)

            context_packet = _compose_memory_context(
                interaction.interaction_id,
                aperture_packet,
                executions,
                round_index=round_index + 1,
            )
            if round_index + 1 >= MAX_CAPABILITY_ROUNDS:
                raise RuntimeError(
                    "capability round limit reached without an explicit RESPOND decision"
                )

            summaries = _capability_result_summaries(executions)
            structured_results = tuple(
                _structured_capability_result(item) for item in executions
            )
            catalog = registry.capability_catalog(
                executed_capability_ids=tuple(catalog_eligible_ids)
            )
            current_round = _load_or_create_round(
                conn,
                llm,
                interaction=interaction,
                round_index=round_index + 1,
                memory_packet=context_packet,
                catalog=catalog,
                completed_results=summaries,
                capability_results=structured_results,
                registry=registry,
            )
            rounds.append(current_round)

        raise RuntimeError("unreachable capability round state")

    if stage is InteractionStage.RESPOND:
        capability_output = _stage_result(
            conn,
            interaction,
            InteractionStage.EXECUTE_CAPABILITY,
            scheduler_key,
        )
        final_decision = InteractionDecision.model_validate(
            capability_output["final_decision"]
        )
        if final_decision.next_action is not InteractionAction.RESPOND:
            raise RuntimeError("final response worker requires an explicit RESPOND decision")
        final_packet = MemoryPacket.model_validate(
            capability_output["final_memory_packet"]
        )
        executions = [
            CapabilityExecution.model_validate(payload)
            for payload in capability_output["executions"]
        ]
        response_text = llm.respond(
            interaction.user_text,
            final_packet,
            tuple(_structured_capability_result(item) for item in executions),
        )
        return {"response_text": response_text}, []

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
        payload={"text": response_text},
        payload_text=response_text,
        event_id=deterministic_interaction_event_id(interaction.interaction_id, "response"),
    )
    activate_working_state(
        conn,
        interaction_id=interaction.interaction_id,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        activated_event_ids=[response_event.event_id, interaction.user_prompt_event_id],
    )
    return {
        "response_text": response_text,
        "response_event_id": str(response_event.event_id),
    }, [f"event:{response_event.event_id}"]


def _load_or_create_round(
    conn: psycopg.Connection,
    llm: LLMClient,
    *,
    interaction: DurableInteraction,
    round_index: int,
    memory_packet: MemoryPacket,
    catalog: tuple[CapabilityDescriptor, ...],
    completed_results: tuple[CapabilityResultSummary, ...],
    capability_results: tuple[dict, ...],
    registry: CapabilityRegistry,
) -> dict:
    """Return one durable recurrent decision, reusing it after worker restart."""

    event_id = deterministic_capability_round_event_id(
        interaction.interaction_id,
        round_index,
    )
    existing = event_store.get_event_by_id(conn, event_id)
    if existing is not None:
        if existing.payload.get("kind") != "CAPABILITY_DECISION_ROUND":
            raise RuntimeError("persisted capability round has an invalid kind")
        if existing.payload.get("round_index") != round_index:
            raise RuntimeError("persisted capability round index mismatch")
        if existing.payload.get("memory_request_id") != str(memory_packet.memory_request_id):
            raise RuntimeError("persisted capability round references different memory context")
        return dict(existing.payload["round"])

    decision = llm.classify(
        interaction.user_text,
        memory_packet,
        catalog,
        completed_results,
        capability_results,
    )
    plan = registry.plan_execution(catalog, decision.capability_indices)
    round_record = {
        "round_index": round_index,
        "decision": decision.model_dump(mode="json"),
        "capability_catalog": [item.model_dump(mode="json") for item in catalog],
        "execution_plan": plan.model_dump(mode="json"),
        "completed_results": [item.model_dump(mode="json") for item in completed_results],
        "capability_results": list(capability_results),
    }
    event_store.record_event(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=SOURCE,
        payload={
            "kind": "CAPABILITY_DECISION_ROUND",
            "round_index": round_index,
            "memory_request_id": str(memory_packet.memory_request_id),
            "round": round_record,
        },
        event_id=event_id,
    )
    return round_record


def _capability_result_summaries(
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
        )
        for execution in executions
    )


def _structured_capability_result(execution: CapabilityExecution) -> dict:
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


def _compose_memory_context(
    interaction_id: UUID,
    aperture_packet: MemoryPacket,
    executions: list[CapabilityExecution],
    *,
    round_index: int,
) -> MemoryPacket:
    """Compose bounded accumulated evidence for the next fresh model call.

    Newer capability evidence is ordered before older capability evidence and the
    initial broad packet. Canonical source IDs are deduplicated. This is working
    context composition, not a claim that every item is true or sufficient.
    """

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
            f"capability-context:{round_index}",
        ),
        need=need,
        supported=bool(items),
        items=items,
        retrieval_trace={
            "composition": "initial_memory_plus_completed_capabilities",
            "round_index": round_index,
            "initial_memory_request_id": str(aperture_packet.memory_request_id),
            "capability_memory_request_ids": [
                str(packet.memory_request_id) for packet in packets
            ],
        },
    )


def _stage_result(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    stage: InteractionStage,
    scheduler_key: str,
) -> dict:
    step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
    result = load_worker_result(conn, step_id, scheduler_key=scheduler_key)
    if result is None:
        raise RuntimeError(f"interaction stage {stage.value} is incomplete")
    return dict(result.output)
