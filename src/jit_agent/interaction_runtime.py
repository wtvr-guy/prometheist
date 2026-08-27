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
    CapabilityNeed,
    CapabilityPacket,
    CapabilityRegistry,
    request_capability,
)
from jit_agent.capability_runtime import CapabilityExecution, execute_registered_capability
from jit_agent.interaction_policy import (
    INTERACTION_CAPABILITIES,
    INTERACTION_STAGES,
    DurableInteraction,
    InteractionAction,
    InteractionDecision,
    InteractionStage,
    ReferenceAnalysis,
    deterministic_interaction_event_id,
    deterministic_interaction_id,
    deterministic_interaction_task_id,
    deterministic_memory_request_id,
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

    persist_result = _stage_result(conn, interaction, InteractionStage.PERSIST_RESULT, scheduler_key)
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
    """Compatibility-shaped entry point backed entirely by durable workers."""

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
    """Run every interaction stage in a separately guarded Python process."""

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
        # Basic access to persistent memory is cognitive substrate, not an
        # optional capability. Open the small system-owned aperture first.
        aperture_packet = open_attention_aperture(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            requester_task_id=interaction.task_id,
            user_text=interaction.user_text,
            before_global_seq=interaction.before_global_seq,
        )
        decision = llm.classify(interaction.user_text, aperture_packet)
        capability_packet = None
        if decision.action is InteractionAction.REQUEST_CAPABILITY:
            capability_id = decision.capability_id
            if capability_id is None:
                raise RuntimeError("capability decision has no deterministic capability id")
            capability_packet = request_capability(
                conn,
                conversation_id=interaction.conversation_id,
                correlation_id=interaction.correlation_id,
                requester_task_id=interaction.task_id,
                requester_step_id=envelope.step.step_id,
                need=CapabilityNeed(query_text=capability_id, limit=1),
                registry=registry,
            )
        refs = [f"memory-request:{aperture_packet.memory_request_id}"]
        if capability_packet is not None:
            refs.append(f"capability-request:{capability_packet.capability_request_id}")
        return {
            "decision": decision.model_dump(mode="json"),
            "attention_aperture_version": ATTENTION_APERTURE_VERSION,
            "aperture_packet": aperture_packet.model_dump(mode="json"),
            "capability_packet": (
                capability_packet.model_dump(mode="json")
                if capability_packet is not None
                else None
            ),
        }, refs

    decision = _load_decision(conn, interaction, scheduler_key)
    if stage is InteractionStage.EXECUTE_CAPABILITY:
        selection = _stage_result(
            conn,
            interaction,
            InteractionStage.SELECT_CAPABILITY,
            scheduler_key,
        )
        packet_payload = selection["capability_packet"]
        if decision.action is InteractionAction.RESPOND_DIRECTLY:
            if packet_payload is not None:
                raise RuntimeError("direct response unexpectedly selected a capability")
            return {"execution": None, "no_match": False}, []
        if packet_payload is None:
            raise RuntimeError("capability request has no discovery packet")
        packet = CapabilityPacket.model_validate(packet_payload)
        if not packet.matches:
            return {"execution": None, "no_match": True}, []

        selected = packet.matches[0].descriptor
        registration = registry.get(selected.capability_id)
        if registration.descriptor != selected:
            raise RuntimeError("capability configuration changed after discovery")
        execution = execute_registered_capability(
            conn,
            llm,
            registration=registration,
            capability_request_id=packet.capability_request_id,
            requester_task_id=interaction.task_id,
            requester_step_id=envelope.step.step_id,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            task_text=interaction.user_text,
            before_global_seq=interaction.before_global_seq,
            memory_request_id=deterministic_memory_request_id(interaction.interaction_id),
        )
        return {
            "execution": execution.model_dump(mode="json"),
            "no_match": False,
        }, [f"memory-request:{execution.memory_packet.memory_request_id}"]

    if stage is InteractionStage.RESPOND:
        selection = _stage_result(
            conn,
            interaction,
            InteractionStage.SELECT_CAPABILITY,
            scheduler_key,
        )
        aperture_packet = MemoryPacket.model_validate(selection["aperture_packet"])
        capability_output = _stage_result(
            conn,
            interaction,
            InteractionStage.EXECUTE_CAPABILITY,
            scheduler_key,
        )
        execution_payload = capability_output["execution"]
        if execution_payload is None and capability_output["no_match"]:
            response_text = "No installed capability matches that request."
        elif execution_payload is None:
            response_text = llm.respond(interaction.user_text, aperture_packet)
        else:
            execution = CapabilityExecution.model_validate(execution_payload)
            packet = execution.memory_packet
            if packet is None:
                raise RuntimeError("selected memory capability returned no packet")
            if execution.executor == "memory_analysis":
                response_text = llm.answer_memory_task(interaction.user_text, packet)
            else:
                response_text = llm.respond(interaction.user_text, packet)
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


def _load_decision(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    scheduler_key: str,
) -> InteractionDecision:
    payload = _stage_result(
        conn,
        interaction,
        InteractionStage.SELECT_CAPABILITY,
        scheduler_key,
    )
    return InteractionDecision.model_validate(payload["decision"])


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