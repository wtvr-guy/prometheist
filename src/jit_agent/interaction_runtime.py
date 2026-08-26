"""Durable, attention-centric interaction execution for Increment G."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

import psycopg

from jit_agent import event_store, jit_memory
from jit_agent.attention import (
    AttentionTask,
    InterruptionPolicy,
    SchedulingMetadata,
    ServiceClass,
    TaskCriticality,
)
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
from jit_agent.interaction_policy import (
    INTERACTION_CAPABILITIES,
    INTERACTION_STAGES,
    DurableInteraction,
    InteractionStage,
    ReferenceAnalysis,
    apply_continuity_policy,
    deterministic_interaction_event_id,
    deterministic_interaction_id,
    deterministic_interaction_task_id,
    deterministic_memory_request_id,
    requires_persisted_context,
)
from jit_agent.interaction_store import (
    load_interaction,
    load_interaction_by_task,
    save_interaction,
)
from jit_agent.llm import LLMClient
from jit_agent.models import AgentAction, AgentDecision, EventType, MemoryPacket
from jit_agent.worker_protocol import (
    WorkerClaimEnvelope,
    WorkerEffectPolicy,
    deterministic_worker_step_id,
)
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
            if stage in {InteractionStage.RETRIEVE, InteractionStage.PERSIST_RESULT}
            else WorkerEffectPolicy.NO_EXTERNAL_EFFECT
        )
        register_worker_step(
            conn,
            assignment_id=assignment.assignment_id,
            step_key=stage.value,
            capability=stage.capability,
            input_refs=[f"event:{prompt.event_id}"],
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
        try:
            output, output_refs = _execute_claimed_stage(
                conn,
                llm,
                attempt.envelope,
                clock=clock,
                scheduler_key=scheduler_key,
            )
            complete_worker_claim(
                conn,
                claim_id=attempt.envelope.claim.claim_id,
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
                event_id=uuid5(attempt.envelope.claim.claim_id, "error-event"),
            )
            release_worker_claim(
                conn,
                claim_id=attempt.envelope.claim.claim_id,
                worker_id=worker_id,
                clock=clock,
                scheduler_key=scheduler_key,
            )
            raise
    return None


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


def _execute_claimed_stage(
    conn: psycopg.Connection,
    llm: LLMClient,
    envelope: WorkerClaimEnvelope,
    *,
    clock: Callable[[], datetime] | None,
    scheduler_key: str,
) -> tuple[dict, list[str]]:
    loaded = load_worker_claim_envelope(
        conn,
        envelope.claim.claim_id,
        worker_id=envelope.claim.worker_id,
        clock=clock,
        scheduler_key=scheduler_key,
    )
    interaction = load_interaction_by_task(
        conn,
        loaded.step.task_id,
        scheduler_key=scheduler_key,
    )
    stage = InteractionStage(loaded.step.step_key)
    if stage is InteractionStage.RESOLVE_REFERENCES:
        analysis = ReferenceAnalysis(
            requires_persisted_context=requires_persisted_context(interaction.user_text)
        )
        return analysis.model_dump(mode="json"), []

    if stage is InteractionStage.CLASSIFY:
        raw = llm.classify(interaction.user_text)
        analysis = ReferenceAnalysis.model_validate(
            _stage_result(conn, interaction, InteractionStage.RESOLVE_REFERENCES, scheduler_key)
        )
        decision, applied_policy = apply_continuity_policy(
            interaction.user_text,
            raw,
            analysis,
        )
        return {
            "decision": decision.model_dump(mode="json"),
            "continuity_policy": applied_policy,
        }, []

    decision = _load_decision(conn, interaction, scheduler_key)
    if stage is InteractionStage.RETRIEVE:
        if decision.action is AgentAction.RESPOND_DIRECTLY:
            return {"packet": None}, []
        if decision.action is AgentAction.DELEGATE_MEMORY_SPECIALIST:
            planned = llm.plan_memory(decision.delegation_task or interaction.user_text)
            need = jit_memory.build_memory_need(
                planned.query_text,
                entities=planned.entities,
                conversation_id=interaction.conversation_id,
            )
        else:
            supplemental = [decision.query_text] if decision.query_text else []
            need = jit_memory.build_memory_need(
                interaction.user_text,
                supplemental_query_texts=supplemental,
                conversation_id=interaction.conversation_id,
            )
        packet = jit_memory.request_memory(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            requesting_agent=SOURCE,
            need=need,
            before_global_seq=interaction.before_global_seq,
            memory_request_id=deterministic_memory_request_id(interaction.interaction_id),
        )
        return {"packet": packet.model_dump(mode="json")}, [
            f"memory-request:{packet.memory_request_id}"
        ]

    if stage is InteractionStage.RESPOND:
        packet_payload = _stage_result(
            conn, interaction, InteractionStage.RETRIEVE, scheduler_key
        )["packet"]
        packet = MemoryPacket.model_validate(packet_payload) if packet_payload else None
        if decision.action is AgentAction.DELEGATE_MEMORY_SPECIALIST:
            if packet is None:
                raise RuntimeError("specialist response requires a MemoryPacket")
            response_text = llm.answer_memory_task(
                decision.delegation_task or interaction.user_text,
                packet,
            )
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
        event_type=EventType.AGENT_RESPONSE,
        source=SOURCE,
        payload={"text": response_text},
        payload_text=response_text,
        event_id=deterministic_interaction_event_id(interaction.interaction_id, "response"),
    )
    return {
        "response_text": response_text,
        "response_event_id": str(response_event.event_id),
    }, [f"event:{response_event.event_id}"]


def _load_decision(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    scheduler_key: str,
) -> AgentDecision:
    payload = _stage_result(conn, interaction, InteractionStage.CLASSIFY, scheduler_key)
    return AgentDecision.model_validate(payload["decision"])


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
