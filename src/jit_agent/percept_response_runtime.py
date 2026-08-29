"""Current percept-to-response runtime for the 2026-08-29 architecture.

This is the live interaction path used by the CLI.  It implements the architecture
recorded in docs/architecture/PERCEPT_TO_RESPONSE_PIPELINE.md:

* one pre-cognitive LLM decides work requirements and response requirement;
* deterministic execution owns work ordering and effects;
* the v2 Composer sees memory only and judges memory-context sufficiency;
* Adaptive Recall deterministically expands persistent memory when requested;
* authoritative work results bypass the Composer;
* a separate final responder receives personality + percept + memory + work results;
* every LLM request is stateless.

The older recurrent capability router remains in interaction_runtime.py only as a
compatibility/test surface while migration finishes.  New interactive use must
enter through this module.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import Enum
import os
import subprocess
import sys
from typing import Any
from uuid import UUID, uuid4, uuid5

import psycopg
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from jit_agent import db, event_store, jit_memory
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
    SystemHostResourceProbe,
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
)
from jit_agent.capability_runtime import CapabilityExecution, execute_registered_capability
from jit_agent.interaction_policy import (
    DurableInteraction,
    deterministic_capability_memory_request_id,
    deterministic_interaction_event_id,
    deterministic_interaction_id,
    deterministic_interaction_task_id,
)
from jit_agent.interaction_store import load_interaction_by_task, save_interaction
from jit_agent.interaction_working_state import activate_working_state, load_working_state
from jit_agent.llm import (
    OllamaClient,
    _build_verbatim_placeholder_maps,
    _format_capability_result_data,
    _format_response_memory_packet,
    _mask_verbatim_literals,
    _restore_verbatim_literals,
    _verbatim_source_texts,
)
from jit_agent.models import EventType, MemoryPacket
from jit_agent.native_policy import native_resource_safety_policy
from jit_agent.ollama_runtime import (
    OllamaClaimHostResourceProbe,
    OllamaRuntimeProbe,
    OllamaRuntimeState,
)
from jit_agent.worker_protocol import WorkerClaimEnvelope, WorkerEffectPolicy, deterministic_worker_step_id
from jit_agent.worker_runtime import GuardedWorkerLauncher
from jit_agent.worker_store import (
    complete_worker_claim,
    guarded_claim_worker_step,
    load_worker_claim_envelope,
    load_worker_result,
    register_worker_step,
    release_worker_claim,
)


SOURCE = "percept_response_v2"
MAX_ADAPTIVE_RECALL_ROUNDS = 3
MAX_RESPONSE_MEMORY_ITEMS = 20
_MEMORY_EXECUTORS = {"jit_memory", "deeper_research", "cross_reference", "focused_recall"}

DEFAULT_PERSONALITY_PROMPT = """\
You are Prometheist. Be precise, direct, context-aware, and useful. Treat supplied
persistent memory as evidence with provenance rather than unquestionable truth.
Honor explicit user constraints. Do not claim personal/history-specific facts
that are not established by the supplied memory or current percept. Do not expose
internal retrieval mechanics unless the user asks about them.
"""


class PerceptStage(str, Enum):
    RESOLVE_REFERENCES = "V2_RESOLVE_REFERENCES"
    PRECOGNITIVE = "V2_PRECOGNITIVE"
    EXECUTE_WORK = "V2_EXECUTE_WORK"
    COMPOSE_MEMORY = "V2_COMPOSE_MEMORY"
    RESPOND = "V2_RESPOND"
    PERSIST_RESULT = "V2_PERSIST_RESULT"

    @property
    def capability(self) -> str:
        return {
            PerceptStage.RESOLVE_REFERENCES: "interaction.resolve_references",
            PerceptStage.PRECOGNITIVE: "interaction.precognitive_disposition",
            PerceptStage.EXECUTE_WORK: "capability.execute",
            PerceptStage.COMPOSE_MEMORY: "interaction.compose_memory",
            PerceptStage.RESPOND: "interaction.respond",
            PerceptStage.PERSIST_RESULT: "interaction.persist_result",
        }[self]


PERCEPT_STAGES = tuple(PerceptStage)
PERCEPT_CAPABILITIES = tuple(stage.capability for stage in PERCEPT_STAGES)


class PreCognitiveDisposition(BaseModel):
    """Bounded semantic disposition of one percept.

    The LLM may say whether a response is required and select application-owned
    capability indices.  It cannot author capability names, schedules, effects,
    resource policy, or durable identifiers.
    """

    model_config = ConfigDict(extra="forbid")
    response_required: bool
    capability_indices: list[int] = Field(default_factory=list)

    @field_validator("capability_indices")
    @classmethod
    def validate_indices(cls, values: list[int]) -> list[int]:
        if any(index < 0 for index in values):
            raise ValueError("capability_indices must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("capability_indices must not contain duplicates")
        return values


class MemorySufficiencyDecision(BaseModel):
    """The v2 Composer's entire semantic responsibility."""

    model_config = ConfigDict(extra="forbid")
    sufficient: bool
    memory_deficit: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_contract(self) -> "MemorySufficiencyDecision":
        if self.sufficient:
            if self.memory_deficit is not None:
                raise ValueError("sufficient memory must not include a deficit")
        else:
            if self.memory_deficit is None or not self.memory_deficit.strip():
                raise ValueError("insufficient memory requires a semantic deficit")
            self.memory_deficit = self.memory_deficit.strip()
        return self


class ResponseMemoryPackage(BaseModel):
    """Bounded memory-only package approved or exhausted by the Composer path."""

    model_config = ConfigDict(extra="forbid")
    memory_packet: MemoryPacket
    sufficient: bool
    unresolved_memory_deficit: str | None = None
    composer_rounds: int = Field(ge=1)
    adaptive_recall_rounds: int = Field(ge=0)


_PRECOGNITIVE_PROMPT = """\
You are a fresh disposable Prometheist pre-cognitive worker. You have no inherited
chat transcript or model state. Given the current percept, bounded orientation
memory, and a numbered catalog of executable non-memory capabilities, determine
what Prometheist must do.

Return only:
- response_required: whether a user-facing response is required after committed
  work completes; and
- capability_indices: the smallest set of supplied capability indices whose work
  is required.

A percept does not automatically require a response. Work may be required without
conversation, a response may be required without external work, both may be
required, or neither may be required. Capability indices are requirements, not an
execution order. Prometheist owns dependencies, scheduling, permissions, resource
admission, retries, and effects. Do not write capability names, arguments,
queries, explanations, or schedules.
"""

_COMPOSER_PROMPT = """\
You are the Prometheist v2 Composer, a fresh stateless memory-sufficiency worker.
Your only job is to judge whether the supplied persistent-memory evidence is
sufficient context for a separate final responder to answer the current percept
accurately.

Do not decide whether Prometheist should respond; that decision was already made.
Do not interpret, summarize, or request tool/action results. Do not write the
user-facing answer. If memory is insufficient, identify only the missing semantic
memory information in memory_deficit. Adaptive Recall, not you, owns retrieval
mechanics. If memory is sufficient, set sufficient=true and memory_deficit=null.
A legitimate unknown is acceptable; never invent missing memory.
"""

_FINAL_RESPONSE_PROMPT = """\
You are a fresh disposable Prometheist final response worker. The pre-cognitive
system has already committed that a user-facing response is required. Your job is
expression, not control.

Use the current percept, the supplied response-ready memory package, authoritative
structured work/action results, general model knowledge when appropriate, and the
personality instructions supplied below. Work/action results are authoritative
inputs from their execution paths and have deliberately bypassed the memory
Composer. Never decide whether to respond, retrieve memory, or execute side
effects. Never invent personal or history-specific information absent from the
current percept or supplied memory. If the memory package explicitly reports an
unresolved deficit, state the resulting uncertainty when it matters.

[Personality]
{personality}
"""


class PerceptLLM(OllamaClient):
    """Stateless semantic roles implemented as independent Ollama requests."""

    def decide_disposition(
        self,
        percept: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
    ) -> PreCognitiveDisposition:
        catalog_text = "\n".join(
            f"{index}: {item.capability_id} | {item.kind.value} | {item.description}"
            for index, item in enumerate(capability_catalog)
        ) or "none"
        memory_text = "\n".join(
            f"item {index}: {item.event_type.value}: {item.content}"
            for index, item in enumerate(memory_packet.items)
        ) or "none"
        user = (
            f"[Current percept]\n{percept}\n\n"
            f"[Bounded orientation memory]\n{memory_text}\n\n"
            f"[Executable capability catalog]\n{catalog_text}"
        )
        last_error: Exception | None = None
        for token_cap in (48, 96):
            try:
                content = self._structured(
                    "PRECOGNITIVE_DISPOSITION",
                    _PRECOGNITIVE_PROMPT,
                    user,
                    PreCognitiveDisposition.model_json_schema(),
                    token_cap,
                )
                decision = PreCognitiveDisposition.model_validate_json(content)
                if any(index >= len(capability_catalog) for index in decision.capability_indices):
                    raise ValueError("pre-cognitive worker selected an unavailable capability")
                return decision
            except (ValueError, Exception) as exc:
                last_error = exc
                if not isinstance(exc, ValueError):
                    raise
        raise ValueError(f"pre-cognitive disposition failed to validate: {last_error}")

    def assess_memory_sufficiency(
        self,
        percept: str,
        memory_packet: MemoryPacket,
    ) -> MemorySufficiencyDecision:
        memory_text = "\n".join(
            f"item {index}: {item.event_type.value}: {item.content}"
            for index, item in enumerate(memory_packet.items)
        ) or "none"
        user = f"[Current percept]\n{percept}\n\n[Persistent memory evidence]\n{memory_text}"
        last_error: Exception | None = None
        for token_cap in (96, 192):
            try:
                content = self._structured(
                    "V2_MEMORY_SUFFICIENCY",
                    _COMPOSER_PROMPT,
                    user,
                    MemorySufficiencyDecision.model_json_schema(),
                    token_cap,
                )
                return MemorySufficiencyDecision.model_validate_json(content)
            except ValueError as exc:
                last_error = exc
        raise ValueError(f"v2 Composer decision failed to validate: {last_error}")

    def generate_final_response(
        self,
        percept: str,
        package: ResponseMemoryPackage,
        work_results: tuple[dict[str, Any], ...],
    ) -> str:
        personality = os.environ.get("PROMETHEIST_PERSONALITY_PROMPT", "").strip()
        if not personality:
            personality = DEFAULT_PERSONALITY_PROMPT.strip()
        packet = package.memory_packet
        literal_to_placeholder, placeholder_to_literal = _build_verbatim_placeholder_maps(
            *_verbatim_source_texts(percept, packet)
        )
        masked_percept = _mask_verbatim_literals(percept, literal_to_placeholder)
        package_status = (
            "memory_sufficient=true"
            if package.sufficient
            else "memory_sufficient=false\n"
            f"unresolved_memory_deficit={package.unresolved_memory_deficit or 'unknown'}"
        )
        answer = self._text(
            "FINAL_RESPONSE_V2",
            _FINAL_RESPONSE_PROMPT.format(personality=personality),
            masked_percept
            + "\n\n[Memory package status]\n"
            + package_status
            + _format_response_memory_packet(
                packet,
                literal_to_placeholder=literal_to_placeholder,
            )
            + _format_capability_result_data(work_results),
        )
        return _restore_verbatim_literals(answer, placeholder_to_literal)


def _external_capability_catalog(registry: CapabilityRegistry) -> tuple[CapabilityDescriptor, ...]:
    """Memory expansion is cognitive substrate, never a pre-cognitive selectable tool."""

    return tuple(
        descriptor
        for descriptor in registry.descriptors()
        if registry.get(descriptor.capability_id).executor not in _MEMORY_EXECUTORS
    )


def _merge_memory_packets(
    interaction_id: UUID,
    base: MemoryPacket,
    expansion: MemoryPacket,
    *,
    round_index: int,
) -> MemoryPacket:
    items = []
    seen: set[UUID] = set()
    for packet in (expansion, base):
        for item in packet.items:
            if item.source_event_id in seen:
                continue
            seen.add(item.source_event_id)
            items.append(item.model_copy(deep=True))
            if len(items) >= MAX_RESPONSE_MEMORY_ITEMS:
                break
        if len(items) >= MAX_RESPONSE_MEMORY_ITEMS:
            break
    need = base.need.model_copy(deep=True)
    need.limit = MAX_RESPONSE_MEMORY_ITEMS
    return MemoryPacket(
        memory_request_id=uuid5(interaction_id, f"adaptive-memory-context:{round_index}"),
        need=need,
        supported=bool(items),
        items=items,
        retrieval_trace={
            "composition": "adaptive_recall_plus_prior_memory",
            "round_index": round_index,
            "base_memory_request_id": str(base.memory_request_id),
            "expansion_memory_request_id": str(expansion.memory_request_id),
        },
    )


def _adaptive_recall(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    current_packet: MemoryPacket,
    deficit: str,
    *,
    round_index: int,
) -> MemoryPacket:
    """Deterministically choose how to expand memory for a semantic deficit."""

    focus_ids = [item.source_event_id for item in current_packet.items]
    if round_index == 0:
        profile = jit_memory.MemoryRecallProfile.STANDARD
        focus_ids = []
    elif round_index == 1:
        profile = jit_memory.MemoryRecallProfile.DEEPER_RESEARCH
        focus_ids = focus_ids[:4]
    else:
        if len(focus_ids) >= 2:
            profile = jit_memory.MemoryRecallProfile.CROSS_REFERENCE
            focus_ids = focus_ids[:2]
        else:
            profile = jit_memory.MemoryRecallProfile.FOCUSED_RECALL
            focus_ids = focus_ids[:1]

    need = jit_memory.build_memory_need(
        deficit,
        focus_event_ids=focus_ids,
        include_persisted_history=True,
        conversation_id=None,
        limit=10,
    )
    expansion = jit_memory.request_memory(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        requesting_component=(
            f"task:{interaction.task_id}/adaptive-recall:{round_index}/v2-composer"
        ),
        need=need,
        before_global_seq=interaction.before_global_seq,
        memory_request_id=uuid5(interaction.interaction_id, f"adaptive-recall:{round_index}"),
        recall_profile=profile,
    )
    return _merge_memory_packets(
        interaction.interaction_id,
        current_packet,
        expansion,
        round_index=round_index,
    )


def _compose_memory_package(
    conn: psycopg.Connection,
    llm: PerceptLLM,
    interaction: DurableInteraction,
    initial_packet: MemoryPacket,
) -> ResponseMemoryPackage:
    packet = initial_packet.model_copy(deep=True)
    last_decision: MemorySufficiencyDecision | None = None
    composer_rounds = 0
    adaptive_rounds = 0

    for round_index in range(MAX_ADAPTIVE_RECALL_ROUNDS + 1):
        composer_rounds += 1
        last_decision = llm.assess_memory_sufficiency(interaction.user_text, packet)
        if last_decision.sufficient:
            return ResponseMemoryPackage(
                memory_packet=packet,
                sufficient=True,
                composer_rounds=composer_rounds,
                adaptive_recall_rounds=adaptive_rounds,
            )
        if round_index >= MAX_ADAPTIVE_RECALL_ROUNDS:
            break
        packet = _adaptive_recall(
            conn,
            interaction,
            packet,
            last_decision.memory_deficit or interaction.user_text,
            round_index=round_index,
        )
        adaptive_rounds += 1

    assert last_decision is not None
    return ResponseMemoryPackage(
        memory_packet=packet,
        sufficient=False,
        unresolved_memory_deficit=last_decision.memory_deficit,
        composer_rounds=composer_rounds,
        adaptive_recall_rounds=adaptive_rounds,
    )


def begin_percept(
    conn: psycopg.Connection,
    user_text: str,
    conversation_id: UUID,
    *,
    correlation_id: UUID | None = None,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    ollama_runtime_state: OllamaRuntimeState | None = None,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> DurableInteraction:
    normalized = user_text.strip()
    if not normalized:
        raise ValueError("user_text must not be empty")
    effective_policy = policy or native_resource_safety_policy()
    interaction_memory_mib = (
        ollama_runtime_state.incremental_process_memory_mib(effective_policy)
        if ollama_runtime_state is not None
        else effective_policy.default_llm_process_memory_mib
    )
    residency_label = (
        ollama_runtime_state.residency_label
        if ollama_runtime_state is not None
        else "unobserved-cold-fallback"
    )
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
        task_key=f"percept-v2:{interaction_id}",
        created_seq=allocate_created_seq(conn),
        metadata=SchedulingMetadata(
            criticality=TaskCriticality.USER_BLOCKING,
            service_class=ServiceClass.INTERACTIVE,
            interruption_policy=InterruptionPolicy.CHECKPOINT_ONLY,
            required_capabilities=list(PERCEPT_CAPABILITIES),
            process_resource_estimate=ProcessResourceEstimate(
                cpu_units=effective_policy.default_process_cpu_units,
                memory_mib=interaction_memory_mib,
                llm_slots=1,
                source=ResourceEstimateSource.CONSERVATIVE_DEFAULT,
                basis=(
                    f"{effective_policy.policy_version}: bounded stateless percept pipeline; "
                    f"Ollama admission state={residency_label}"
                ),
            ),
        ),
        resumable_state={"interaction_id": str(interaction_id)},
    )
    scheduler.submit(task)
    controller = LocalResourceAdmissionController(
        scheduler,
        probe=probe,
        policy=effective_policy,
        clock=clock,
    )
    controller.plan_scheduling_epoch()
    save_scheduler(conn, scheduler, scheduler_key=scheduler_key)
    assignments = [
        value for value in scheduler.worker_visible_assignments() if value.task_id == task_id
    ]
    if len(assignments) != 1:
        raise RuntimeError("interaction was not safely admitted to one assignment")
    interaction = DurableInteraction(
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation,
        user_prompt_event_id=prompt.event_id,
        before_global_seq=prompt.global_seq,
        task_id=task_id,
        assignment_id=assignments[0].assignment_id,
        user_text=normalized,
    )
    save_interaction(conn, interaction, scheduler_key=scheduler_key)
    _ensure_steps(conn, interaction, scheduler_key=scheduler_key)
    return interaction


def _ensure_steps(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    *,
    scheduler_key: str,
) -> None:
    for stage in PERCEPT_STAGES:
        effect_policy = (
            WorkerEffectPolicy.IDEMPOTENT_WITH_KEY
            if stage in {PerceptStage.EXECUTE_WORK, PerceptStage.PERSIST_RESULT}
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


def _stage_result(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    stage: PerceptStage,
    scheduler_key: str,
) -> dict[str, Any]:
    step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
    result = load_worker_result(conn, step_id, scheduler_key=scheduler_key)
    if result is None:
        raise RuntimeError(f"percept stage {stage.value} is incomplete")
    return dict(result.output)


def _structured_execution(execution: CapabilityExecution) -> dict[str, Any]:
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


def _execute_stage(
    conn: psycopg.Connection,
    llm: PerceptLLM,
    envelope: WorkerClaimEnvelope,
    interaction: DurableInteraction,
    *,
    scheduler_key: str,
    registry: CapabilityRegistry,
) -> tuple[dict[str, Any], list[str]]:
    stage = PerceptStage(envelope.step.step_key)

    if stage is PerceptStage.RESOLVE_REFERENCES:
        return {
            "working_state_available": load_working_state(
                conn, interaction.conversation_id
            ) is not None
        }, []

    if stage is PerceptStage.PRECOGNITIVE:
        aperture_packet = open_attention_aperture(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            requester_task_id=interaction.task_id,
            user_text=interaction.user_text,
            before_global_seq=interaction.before_global_seq,
        )
        catalog = _external_capability_catalog(registry)
        disposition = llm.decide_disposition(interaction.user_text, aperture_packet, catalog)
        plan = registry.plan_execution(catalog, disposition.capability_indices)
        return {
            "attention_aperture_version": ATTENTION_APERTURE_VERSION,
            "aperture_packet": aperture_packet.model_dump(mode="json"),
            "disposition": disposition.model_dump(mode="json"),
            "capability_catalog": [item.model_dump(mode="json") for item in catalog],
            "execution_plan": plan.model_dump(mode="json"),
        }, [f"memory-request:{aperture_packet.memory_request_id}"]

    if stage is PerceptStage.EXECUTE_WORK:
        precognitive = _stage_result(
            conn, interaction, PerceptStage.PRECOGNITIVE, scheduler_key
        )
        plan = CapabilityExecutionPlan.model_validate(precognitive["execution_plan"])
        executions: list[CapabilityExecution] = []
        for position, item in enumerate(plan.items):
            registration = registry.get(item.capability_id)
            if registration.executor in _MEMORY_EXECUTORS:
                raise RuntimeError("memory retrieval cannot execute as pre-cognitive work")
            # Current default registry intentionally exposes no external work yet.
            # This call remains the application-owned binding point as tools are installed.
            execution = execute_registered_capability(
                conn,
                llm,
                registration=registration,
                capability_execution_id=uuid5(
                    envelope.step.step_id, f"work:{position}:{item.capability_id}"
                ),
                requester_task_id=interaction.task_id,
                requester_step_id=envelope.step.step_id,
                round_index=0,
                plan_position=position,
                conversation_id=interaction.conversation_id,
                correlation_id=interaction.correlation_id,
                task_text=interaction.user_text,
                before_global_seq=interaction.before_global_seq,
                memory_request_id=deterministic_capability_memory_request_id(
                    interaction.interaction_id, 0, item.capability_id
                ),
                candidate_packet=MemoryPacket.model_validate(precognitive["aperture_packet"]),
            )
            executions.append(execution)
        return {
            "executions": [item.model_dump(mode="json") for item in executions],
            "work_results": [_structured_execution(item) for item in executions],
        }, []

    if stage is PerceptStage.COMPOSE_MEMORY:
        precognitive = _stage_result(
            conn, interaction, PerceptStage.PRECOGNITIVE, scheduler_key
        )
        disposition = PreCognitiveDisposition.model_validate(precognitive["disposition"])
        if not disposition.response_required:
            return {"skipped": True, "reason": "response_not_required"}, []
        initial_packet = MemoryPacket.model_validate(precognitive["aperture_packet"])
        package = _compose_memory_package(conn, llm, interaction, initial_packet)
        return {"skipped": False, "memory_package": package.model_dump(mode="json")}, [
            f"memory-request:{package.memory_packet.memory_request_id}"
        ]

    if stage is PerceptStage.RESPOND:
        precognitive = _stage_result(
            conn, interaction, PerceptStage.PRECOGNITIVE, scheduler_key
        )
        disposition = PreCognitiveDisposition.model_validate(precognitive["disposition"])
        if not disposition.response_required:
            return {
                "response_required": False,
                "response_text": None,
                "skipped": True,
            }, []
        compose = _stage_result(
            conn, interaction, PerceptStage.COMPOSE_MEMORY, scheduler_key
        )
        package = ResponseMemoryPackage.model_validate(compose["memory_package"])
        work = _stage_result(conn, interaction, PerceptStage.EXECUTE_WORK, scheduler_key)
        response_text = llm.generate_final_response(
            interaction.user_text,
            package,
            tuple(work["work_results"]),
        )
        return {
            "response_required": True,
            "response_text": response_text,
            "skipped": False,
        }, []

    response = _stage_result(conn, interaction, PerceptStage.RESPOND, scheduler_key)
    response_required = bool(response["response_required"])
    response_text = response.get("response_text")
    output_refs: list[str] = []
    response_event_id: UUID | None = None
    if response_required:
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError("response-required percept produced no final response text")
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
        response_event_id = response_event.event_id
        output_refs.append(f"event:{response_event.event_id}")
    activated = [interaction.user_prompt_event_id]
    if response_event_id is not None:
        activated.insert(0, response_event_id)
    activate_working_state(
        conn,
        interaction_id=interaction.interaction_id,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        activated_event_ids=activated,
    )
    return {
        "response_required": response_required,
        "response_text": response_text,
        "response_event_id": str(response_event_id) if response_event_id else None,
    }, output_refs


def execute_claimed_percept_step(
    conn: psycopg.Connection,
    llm: PerceptLLM,
    *,
    claim_id: UUID,
    worker_id: str,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> PerceptStage:
    envelope = load_worker_claim_envelope(
        conn,
        claim_id,
        worker_id=worker_id,
        clock=clock,
        scheduler_key=scheduler_key,
    )
    interaction = load_interaction_by_task(
        conn, envelope.step.task_id, scheduler_key=scheduler_key
    )
    stage = PerceptStage(envelope.step.step_key)
    try:
        output, output_refs = _execute_stage(
            conn,
            llm,
            envelope,
            interaction,
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


def finish_percept(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    *,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    clock: Callable[[], datetime] | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
) -> str | None:
    persisted = _stage_result(
        conn, interaction, PerceptStage.PERSIST_RESULT, scheduler_key
    )
    response_text = persisted.get("response_text")
    scheduler = load_scheduler(conn, scheduler_key=scheduler_key)
    if scheduler.tasks[interaction.task_id].status.value != "COMPLETED":
        scheduler.complete_task(
            interaction.task_id,
            {
                "interaction_id": str(interaction.interaction_id),
                "response_required": bool(persisted["response_required"]),
                "response_text": response_text,
            },
        )
        observation = scheduler.current_resource_observation()
        effective_policy = (
            policy
            or (observation.policy.model_copy(deep=True) if observation is not None else None)
            or native_resource_safety_policy()
        )
        controller = LocalResourceAdmissionController(
            scheduler, probe=probe, policy=effective_policy, clock=clock
        )
        controller.plan_scheduling_epoch()
        save_scheduler(conn, scheduler, scheduler_key=scheduler_key)
    return str(response_text) if response_text is not None else None


def handle_percept_in_worker_processes(
    conn: psycopg.Connection,
    user_text: str,
    conversation_id: UUID,
    *,
    probe: HostResourceProbe | None = None,
    policy: ResourceSafetyPolicy | None = None,
    ollama_runtime_probe: OllamaRuntimeProbe | None = None,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    worker_lease_seconds: int = 600,
    worker_timeout_seconds: int = 660,
) -> str | None:
    """Run each architectural role/stage in a separately guarded fresh process."""

    effective_policy = policy or native_resource_safety_policy()
    physical_probe = probe or SystemHostResourceProbe()
    runtime_probe = ollama_runtime_probe or OllamaRuntimeProbe()
    admission_runtime_state = runtime_probe.capture()
    scheduled_memory_mib = admission_runtime_state.incremental_process_memory_mib(
        effective_policy
    )
    interaction = begin_percept(
        conn,
        user_text,
        conversation_id,
        probe=physical_probe,
        policy=effective_policy,
        ollama_runtime_state=admission_runtime_state,
        scheduler_key=scheduler_key,
    )
    claim_probe = OllamaClaimHostResourceProbe(
        base_probe=physical_probe,
        runtime_probe=runtime_probe,
        policy=effective_policy,
        scheduled_memory_mib=scheduled_memory_mib,
    )
    launcher = GuardedWorkerLauncher(
        db.get_connection,
        probe=claim_probe,
        policy=effective_policy,
        scheduler_key=scheduler_key,
    )
    for stage in PERCEPT_STAGES:
        step_id = deterministic_worker_step_id(interaction.assignment_id, stage.value)
        worker_id = f"percept-v2-{interaction.interaction_id}-{stage.value.casefold()}"
        launched = launcher.launch(
            step_id=step_id,
            worker_id=worker_id,
            command=[sys.executable, "-m", "jit_agent.percept_response_worker"],
            lease_seconds=worker_lease_seconds,
        )
        try:
            return_code = launched.process.wait(timeout=worker_timeout_seconds)
        except subprocess.TimeoutExpired:
            launched.process.kill()
            launched.process.wait(timeout=10)
            raise RuntimeError(f"percept worker timed out at stage {stage.value}") from None
        if return_code != 0:
            raise RuntimeError(
                f"percept worker failed at stage {stage.value} with exit code {return_code}"
            )
    return finish_percept(
        conn,
        interaction,
        probe=physical_probe,
        policy=effective_policy,
        scheduler_key=scheduler_key,
    )
