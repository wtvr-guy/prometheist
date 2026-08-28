"""Terminalization layered over the staged transient-worker interaction runtime.

The five durable v0.7 stage keys remain unchanged for restart compatibility, but
the production path now carries one typed ``InteractionWorkpiece`` through those
stages. Conditional deterministic, LLM, and capability stations contribute small
validated components. The terminal workpiece is materialized as one JSON snapshot
while the underlying append-only events/results remain authoritative history.

The current CLI is an interactive surface, so its terminal path attaches a user
output. The workpiece contract itself is broader: future action workflows may
terminalize successfully without invoking any final response worker.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid5

import psycopg
from pydantic import ValidationError

from jit_agent import event_store
from jit_agent.attention_store import DEFAULT_SCHEDULER_KEY
from jit_agent.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityDescriptor,
    CapabilityExecutionPlan,
    CapabilityRegistry,
)
from jit_agent.capability_runtime import CapabilityExecution
from jit_agent.epistemic_authority import format_authority_bound_response_memory_packet
from jit_agent.evidence_bound_llm import (
    _admitted_capability_results,
    _format_capability_result_data,
    _quarantined_evidence,
)
from jit_agent.final_response_directive import (
    FINAL_READINESS_VERSION,
    FINAL_RESPONSE_DIRECTIVE_VERSION,
    FinalAbstainReason,
    FinalReadinessDecision,
    FinalResponseAction,
    FinalResponseDirective,
)
from jit_agent.interaction_policy import DurableInteraction, InteractionStage
from jit_agent.interaction_store import load_interaction_by_task
from jit_agent.interaction_working_state import activate_working_state
from jit_agent.interaction_workpiece import (
    INTERACTION_WORKPIECE_VERSION,
    AttentionApertureComponent,
    CapabilityWorkComponent,
    FinalEvidenceComponent,
    FinalResponseDirectiveComponent,
    InteractionWorkpiece,
    PreCognitiveControlComponent,
    ReferenceResolutionComponent,
    TerminalOutcomeComponent,
    TerminalOutcomeKind,
    UserOutputComponent,
    begin_interaction_workpiece,
)
from jit_agent.models import EventType, MemoryPacket
from jit_agent.personality import configured_personality_prompt
from jit_agent.pre_cognitive_specialists import (
    CapabilitySelectionDecision,
    CapabilitySelectionStationComponent,
    EvidenceSufficiency,
    EvidenceSufficiencyDecision,
    EvidenceSufficiencyStationComponent,
)
from jit_agent.pre_cognitive_workers import (
    PRE_COGNITIVE_WORKER_SCHEME_VERSION,
    CognitiveDisposition,
    PreCognitiveAssessment,
    _execute_stage,
    _stage_result,
    structured_capability_result,
)
from jit_agent.response_policy import (
    ResponsePolicy,
    filter_memory_packet_for_scope,
    scope_requires_historical_support,
)
from jit_agent.worker_store import (
    complete_worker_claim,
    load_worker_claim_envelope,
    release_worker_claim,
)


FINALIZATION_SOURCE = "pre_cognitive_response_finalizer"
_FINAL_READINESS_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist final-readiness worker. All capability
work allowed for this interaction has ended. You have no inherited transcript,
hidden model context, or authority to request additional work.

Inspect only the current user percept and the supplied quarantined final evidence.
Return one closed terminal action:
- RESPOND when the available current input/evidence is sufficient to support a
  user-facing answer without inventing personal or history-specific facts.
- ABSTAIN when the required answer remains unsupported after the work already
  performed.

You cannot select capabilities, write queries, propose plans, explain your
choice, draft response prose, alter source admissibility, or issue tool calls.
Return only the FinalReadinessDecision schema.
"""
_GENERIC_INSUFFICIENT_RESPONSE = "Persisted evidence is insufficient."


def _final_readiness_event_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "pre-cognitive:FINAL_RESPONSE_READINESS")


def _final_directive_event_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "pre-cognitive:FINAL_RESPONSE_DIRECTIVE")


def _workpiece_snapshot_event_id(interaction_id: UUID) -> UUID:
    return uuid5(interaction_id, "event:interaction-workpiece-terminal")


def _structured_results(executions: list[CapabilityExecution]) -> tuple[dict[str, Any], ...]:
    return tuple(structured_capability_result(item) for item in executions)


def _assess_final_readiness(
    llm: Any,
    prompt: str,
    final_packet: MemoryPacket,
    capability_results: tuple[dict[str, Any], ...],
) -> FinalReadinessDecision:
    explicit = getattr(llm, "assess_final_readiness", None)
    if callable(explicit):
        return FinalReadinessDecision.model_validate(
            explicit(prompt, final_packet, capability_results)
        )

    validate_inputs = getattr(llm, "_validate_evidence_inputs", None)
    if callable(validate_inputs):
        validate_inputs(final_packet, capability_results)

    structured = getattr(llm, "_structured_with_evidence", None)
    if not callable(structured):
        raise TypeError("LLM client does not provide final-readiness structured inference")

    evidence = _quarantined_evidence(
        format_authority_bound_response_memory_packet(final_packet),
        _format_capability_result_data(capability_results),
    )
    last_error: Exception | None = None
    for token_cap in (64, 128):
        try:
            content = structured(
                "FINAL_READINESS",
                _FINAL_READINESS_SYSTEM_PROMPT,
                prompt,
                evidence,
                FinalReadinessDecision.model_json_schema(),
                token_cap,
            )
            return FinalReadinessDecision.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            last_error = exc
    raise ValueError(f"final readiness failed to validate: {last_error}")


def _load_or_create_final_readiness(
    conn: psycopg.Connection,
    llm: Any,
    *,
    interaction: DurableInteraction,
    final_packet: MemoryPacket,
    capability_results: tuple[dict[str, Any], ...],
) -> FinalReadinessDecision:
    event_id = _final_readiness_event_id(interaction.interaction_id)
    existing = event_store.get_event_by_id(conn, event_id)
    capability_ids = [str(item.get("capability_id")) for item in capability_results]
    if existing is not None:
        payload = existing.payload
        if payload.get("kind") != "FINAL_READINESS_DECISION":
            raise RuntimeError("persisted final-readiness event has invalid kind")
        if payload.get("version") != FINAL_READINESS_VERSION:
            raise RuntimeError("persisted final-readiness event uses a different version")
        if payload.get("memory_request_id") != str(final_packet.memory_request_id):
            raise RuntimeError("persisted final-readiness event references different evidence")
        if payload.get("capability_ids") != capability_ids:
            raise RuntimeError("capability results changed after final-readiness decision")
        return FinalReadinessDecision.model_validate(payload["decision"])

    decision = _assess_final_readiness(
        llm,
        interaction.user_text,
        final_packet,
        capability_results,
    )
    event_store.record_event(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=FINALIZATION_SOURCE,
        payload={
            "kind": "FINAL_READINESS_DECISION",
            "version": FINAL_READINESS_VERSION,
            "memory_request_id": str(final_packet.memory_request_id),
            "capability_ids": capability_ids,
            "decision": decision.model_dump(mode="json"),
        },
        event_id=event_id,
    )
    return decision


def _classify_response_policy(llm: Any, prompt: str) -> ResponsePolicy:
    classify = getattr(llm, "classify_response_policy", None)
    if not callable(classify):
        raise TypeError("LLM client does not provide pre-cognitive response-policy classification")
    return ResponsePolicy.model_validate(classify(prompt))


def _select_fallback_literal(llm: Any, prompt: str) -> str | None:
    select = getattr(llm, "select_current_fallback_literal", None)
    if not callable(select):
        raise TypeError("LLM client does not provide pre-cognitive fallback selection")
    fallback = select(prompt)
    if fallback is not None and fallback not in prompt:
        raise ValueError("pre-cognitive fallback literal is not current-prompt text")
    return fallback


def _terminal_assessment(
    conn: psycopg.Connection,
    llm: Any,
    *,
    interaction: DurableInteraction,
    acquisition: dict[str, Any],
    final_packet: MemoryPacket,
    capability_results: tuple[dict[str, Any], ...],
) -> tuple[PreCognitiveAssessment, FinalResponseAction, str]:
    pre = PreCognitiveAssessment.model_validate(acquisition["pre_assessment"])
    post_payload = acquisition.get("post_assessment")
    post = (
        PreCognitiveAssessment.model_validate(post_payload)
        if post_payload is not None
        else None
    )
    effective = post or pre

    if effective.disposition is CognitiveDisposition.RESPOND:
        return effective, FinalResponseAction.RESPOND, effective.evidence_state.value
    if effective.disposition is CognitiveDisposition.ABSTAIN:
        return effective, FinalResponseAction.ABSTAIN, effective.evidence_state.value

    readiness = _load_or_create_final_readiness(
        conn,
        llm,
        interaction=interaction,
        final_packet=final_packet,
        capability_results=capability_results,
    )
    return effective, readiness.action, readiness.evidence_state


def _load_or_create_final_directive(
    conn: psycopg.Connection,
    llm: Any,
    *,
    interaction: DurableInteraction,
    acquisition: dict[str, Any],
) -> FinalResponseDirective:
    final_packet = MemoryPacket.model_validate(acquisition["final_memory_packet"])
    executions = [
        CapabilityExecution.model_validate(item) for item in acquisition.get("executions", [])
    ]
    capability_results = _structured_results(executions)
    capability_ids = [item.capability_id for item in executions]
    personality = configured_personality_prompt()

    event_id = _final_directive_event_id(interaction.interaction_id)
    existing = event_store.get_event_by_id(conn, event_id)
    if existing is not None:
        payload = existing.payload
        if payload.get("kind") != "FINAL_RESPONSE_DIRECTIVE":
            raise RuntimeError("persisted final response directive has invalid kind")
        directive = FinalResponseDirective.model_validate(payload["directive"])
        if directive.final_memory_request_id != final_packet.memory_request_id:
            raise RuntimeError("persisted final response directive references different evidence")
        if directive.capability_ids != capability_ids:
            raise RuntimeError("capability results changed after final response directive")
        if directive.personality_prompt_version != personality.version:
            raise RuntimeError("personality prompt version changed after final response directive")
        if directive.personality_prompt_sha256 != personality.sha256:
            raise RuntimeError("personality prompt content changed after final response directive")
        return directive

    effective, cognitive_action, evidence_state = _terminal_assessment(
        conn,
        llm,
        interaction=interaction,
        acquisition=acquisition,
        final_packet=final_packet,
        capability_results=capability_results,
    )
    policy = _classify_response_policy(llm, interaction.user_text)
    admitted_packet = filter_memory_packet_for_scope(final_packet, policy.evidence_scope)
    admitted_capability_results = _admitted_capability_results(
        policy.evidence_scope,
        capability_results,
    )
    has_admitted_history = bool(admitted_packet and admitted_packet.items)
    has_admitted_capability = bool(admitted_capability_results)
    source_supported = (
        not scope_requires_historical_support(policy.evidence_scope)
        or has_admitted_history
        or has_admitted_capability
    )

    if not source_supported:
        action = FinalResponseAction.ABSTAIN
        abstain_reason = FinalAbstainReason.SOURCE_POLICY_UNSUPPORTED
    elif cognitive_action is FinalResponseAction.ABSTAIN:
        action = FinalResponseAction.ABSTAIN
        abstain_reason = FinalAbstainReason.PRE_COGNITIVE_INSUFFICIENT
    else:
        action = FinalResponseAction.RESPOND
        abstain_reason = None

    fallback_literal = (
        _select_fallback_literal(llm, interaction.user_text)
        if action is FinalResponseAction.ABSTAIN
        else None
    )
    directive = FinalResponseDirective(
        action=action,
        abstain_reason=abstain_reason,
        intent_mode=effective.intent_mode.value,
        evidence_state=evidence_state,
        claim_scopes=[value.value for value in effective.claim_scopes],
        requirement_flags=[value.value for value in effective.requirement_flags],
        response_policy=policy,
        fallback_literal=fallback_literal,
        final_memory_request_id=final_packet.memory_request_id,
        capability_ids=capability_ids,
        follow_up_executed=bool(acquisition.get("follow_up_executed")),
        personality_prompt_version=personality.version,
        personality_prompt_sha256=personality.sha256,
    )
    event_store.record_event(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=FINALIZATION_SOURCE,
        payload={
            "kind": "FINAL_RESPONSE_DIRECTIVE",
            "version": FINAL_RESPONSE_DIRECTIVE_VERSION,
            "pre_cognitive_scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "directive": directive.model_dump(mode="json"),
        },
        event_id=event_id,
    )
    return directive


def _begin_workpiece(interaction: DurableInteraction) -> InteractionWorkpiece:
    return begin_interaction_workpiece(
        interaction_id=interaction.interaction_id,
        task_id=interaction.task_id,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        user_text=interaction.user_text,
        user_prompt_event_id=interaction.user_prompt_event_id,
    )


def _workpiece_from_payload(payload: dict[str, Any]) -> InteractionWorkpiece | None:
    raw = payload.get("workpiece")
    return InteractionWorkpiece.model_validate(raw) if raw is not None else None


def _resolved_workpiece(
    interaction: DurableInteraction,
    resolved: dict[str, Any],
) -> InteractionWorkpiece:
    existing = _workpiece_from_payload(resolved)
    if existing is not None:
        return existing
    return _begin_workpiece(interaction).attach(
        ReferenceResolutionComponent(
            working_state_available=bool(resolved.get("working_state_available")),
        )
    )


def _station_components(
    assessment: PreCognitiveAssessment,
    catalog: tuple[CapabilityDescriptor, ...],
) -> tuple[EvidenceSufficiencyStationComponent | CapabilitySelectionStationComponent, ...]:
    sufficient = assessment.disposition is CognitiveDisposition.RESPOND
    components: list[
        EvidenceSufficiencyStationComponent | CapabilitySelectionStationComponent
    ] = [
        EvidenceSufficiencyStationComponent(
            phase=assessment.phase.value,
            decision=EvidenceSufficiencyDecision(
                sufficiency=(
                    EvidenceSufficiency.SUFFICIENT
                    if sufficient
                    else EvidenceSufficiency.INSUFFICIENT
                )
            ),
        )
    ]
    if not sufficient and catalog:
        components.append(
            CapabilitySelectionStationComponent(
                phase=assessment.phase.value,
                decision=CapabilitySelectionDecision(
                    capability_indices=list(assessment.capability_indices)
                ),
            )
        )
    return tuple(components)


def _selection_workpiece(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    selection: dict[str, Any],
    scheduler_key: str,
) -> InteractionWorkpiece:
    existing = _workpiece_from_payload(selection)
    if existing is not None:
        return existing

    resolved = _stage_result(
        conn,
        interaction,
        InteractionStage.RESOLVE_REFERENCES,
        scheduler_key,
    )
    workpiece = _resolved_workpiece(interaction, resolved)
    packet = MemoryPacket.model_validate(selection["aperture_packet"])
    workpiece = workpiece.attach(
        AttentionApertureComponent(
            aperture_version=str(selection["attention_aperture_version"]),
            memory_packet=packet,
        )
    )
    assessment = PreCognitiveAssessment.model_validate(selection["assessment"])
    catalog = tuple(
        CapabilityDescriptor.model_validate(item)
        for item in selection.get("capability_catalog", [])
    )
    plan = CapabilityExecutionPlan.model_validate(selection["execution_plan"])
    for component in _station_components(assessment, catalog):
        workpiece = workpiece.attach(component)
    return workpiece.attach(
        PreCognitiveControlComponent(
            phase=assessment.phase,
            assessment=assessment,
            capability_catalog=list(catalog),
            execution_plan=plan,
        )
    )


def _acquisition_workpiece(
    conn: psycopg.Connection,
    interaction: DurableInteraction,
    acquisition: dict[str, Any],
    scheduler_key: str,
    directive: FinalResponseDirective,
) -> InteractionWorkpiece:
    existing = _workpiece_from_payload(acquisition)
    if existing is not None:
        return existing

    selection = _stage_result(
        conn,
        interaction,
        InteractionStage.SELECT_CAPABILITY,
        scheduler_key,
    )
    workpiece = _selection_workpiece(conn, interaction, selection, scheduler_key)
    executions = [
        CapabilityExecution.model_validate(item) for item in acquisition.get("executions", [])
    ]
    tranche_indices = sorted({item.round_index for item in executions})
    later_tranche_indices: list[int] = []
    if tranche_indices:
        initial_tranche_index, *later_tranche_indices = tranche_indices
        initial_tranche = [
            item for item in executions if item.round_index == initial_tranche_index
        ]
        workpiece = workpiece.attach(
            CapabilityWorkComponent(
                tranche_index=initial_tranche_index,
                executions=initial_tranche,
            )
        )

    post_payload = acquisition.get("post_assessment")
    if post_payload is not None:
        post = PreCognitiveAssessment.model_validate(post_payload)
        follow_up_catalog = tuple(
            CapabilityDescriptor.model_validate(item)
            for item in acquisition.get("follow_up_catalog", [])
        )
        follow_up_plan = CapabilityExecutionPlan.model_validate(acquisition["follow_up_plan"])
        for component in _station_components(post, follow_up_catalog):
            workpiece = workpiece.attach(component)
        workpiece = workpiece.attach(
            PreCognitiveControlComponent(
                phase=post.phase,
                assessment=post,
                capability_catalog=list(follow_up_catalog),
                execution_plan=follow_up_plan,
            )
        )

    for tranche_index in later_tranche_indices:
        tranche = [item for item in executions if item.round_index == tranche_index]
        workpiece = workpiece.attach(
            CapabilityWorkComponent(tranche_index=tranche_index, executions=tranche)
        )

    workpiece = workpiece.attach(
        FinalEvidenceComponent(
            memory_packet=MemoryPacket.model_validate(acquisition["final_memory_packet"])
        )
    )
    return workpiece.attach(FinalResponseDirectiveComponent(directive=directive))


def _record_error_best_effort(
    conn: psycopg.Connection,
    *,
    interaction: DurableInteraction,
    claim_id: UUID,
    stage: InteractionStage,
    exc: Exception,
) -> None:
    try:
        event_store.record_event(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            event_type=EventType.ERROR,
            source=FINALIZATION_SOURCE,
            payload={
                "stage": stage.value,
                "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            event_id=uuid5(claim_id, "pre-cognitive-finalized-error-event"),
        )
    except Exception:
        pass


def _release_claim_best_effort(
    conn: psycopg.Connection,
    *,
    claim_id: UUID,
    worker_id: str,
    scheduler_key: str,
) -> None:
    try:
        release_worker_claim(
            conn,
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )
    except Exception:
        pass


def _persist_terminal_workpiece(
    conn: psycopg.Connection,
    *,
    interaction: DurableInteraction,
    workpiece: InteractionWorkpiece,
) -> tuple[dict[str, Any], list[str]]:
    if workpiece.state.value != "TERMINAL":
        raise RuntimeError("PERSIST_RESULT requires a terminal interaction workpiece")

    workpiece_event = event_store.record_event(
        conn,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=FINALIZATION_SOURCE,
        payload={
            "kind": "INTERACTION_WORKPIECE_SNAPSHOT",
            "version": INTERACTION_WORKPIECE_VERSION,
            "workpiece": workpiece.model_dump(mode="json"),
        },
        event_id=_workpiece_snapshot_event_id(interaction.interaction_id),
    )
    refs = [f"event:{workpiece_event.event_id}"]
    output = workpiece.user_output()
    response_event = None
    if output is not None:
        response_event = event_store.record_event(
            conn,
            conversation_id=interaction.conversation_id,
            correlation_id=interaction.correlation_id,
            event_type=EventType.INTERACTION_RESPONSE,
            source=FINALIZATION_SOURCE,
            payload={
                "text": output.text,
                "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
                "workpiece_event_id": str(workpiece_event.event_id),
            },
            payload_text=output.text,
            event_id=uuid5(interaction.interaction_id, "event:response"),
        )
        refs.append(f"event:{response_event.event_id}")

    activated_event_ids = [interaction.user_prompt_event_id]
    if response_event is not None:
        activated_event_ids.insert(0, response_event.event_id)
    activate_working_state(
        conn,
        interaction_id=interaction.interaction_id,
        conversation_id=interaction.conversation_id,
        correlation_id=interaction.correlation_id,
        activated_event_ids=activated_event_ids,
    )
    return {
        "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
        "workpiece_version": INTERACTION_WORKPIECE_VERSION,
        "workpiece_snapshot_event_id": str(workpiece_event.event_id),
        "response_text": output.text if output is not None else None,
        "response_event_id": str(response_event.event_id) if response_event is not None else None,
        "workpiece": workpiece.model_dump(mode="json"),
    }, refs


def _execute_finalized_stage(
    conn: psycopg.Connection,
    llm: Any,
    envelope: Any,
    *,
    interaction: DurableInteraction,
    scheduler_key: str,
    registry: CapabilityRegistry,
) -> tuple[dict[str, Any], list[str]]:
    stage = InteractionStage(envelope.step.step_key)

    if stage is InteractionStage.RESOLVE_REFERENCES:
        output, refs = _execute_stage(
            conn,
            llm,
            envelope,
            interaction=interaction,
            scheduler_key=scheduler_key,
            registry=registry,
        )
        workpiece = _resolved_workpiece(interaction, output)
        output = dict(output)
        output["workpiece"] = workpiece.model_dump(mode="json")
        return output, refs

    if stage is InteractionStage.SELECT_CAPABILITY:
        output, refs = _execute_stage(
            conn,
            llm,
            envelope,
            interaction=interaction,
            scheduler_key=scheduler_key,
            registry=registry,
        )
        workpiece = _selection_workpiece(conn, interaction, output, scheduler_key)
        output = dict(output)
        output["workpiece"] = workpiece.model_dump(mode="json")
        return output, refs

    if stage is InteractionStage.EXECUTE_CAPABILITY:
        acquisition, refs = _execute_stage(
            conn,
            llm,
            envelope,
            interaction=interaction,
            scheduler_key=scheduler_key,
            registry=registry,
        )
        directive = _load_or_create_final_directive(
            conn,
            llm,
            interaction=interaction,
            acquisition=acquisition,
        )
        workpiece = _acquisition_workpiece(
            conn,
            interaction,
            acquisition,
            scheduler_key,
            directive,
        )
        acquisition = dict(acquisition)
        acquisition["final_response_directive"] = directive.model_dump(mode="json")
        acquisition["workpiece"] = workpiece.model_dump(mode="json")
        return acquisition, refs

    if stage is InteractionStage.RESPOND:
        acquisition = _stage_result(
            conn,
            interaction,
            InteractionStage.EXECUTE_CAPABILITY,
            scheduler_key,
        )
        directive = FinalResponseDirective.model_validate(
            acquisition["final_response_directive"]
        )
        final_packet = MemoryPacket.model_validate(acquisition["final_memory_packet"])
        executions = [
            CapabilityExecution.model_validate(item) for item in acquisition.get("executions", [])
        ]
        capability_results = _structured_results(executions)
        workpiece = _workpiece_from_payload(acquisition) or _acquisition_workpiece(
            conn,
            interaction,
            acquisition,
            scheduler_key,
            directive,
        )

        if directive.action is FinalResponseAction.ABSTAIN:
            response_text = directive.fallback_literal or _GENERIC_INSUFFICIENT_RESPONSE
            producer = "pre_cognitive_finalizer"
            outcome = TerminalOutcomeKind.ABSTAINED
        else:
            respond = getattr(llm, "respond_with_final_directive", None)
            if not callable(respond):
                raise TypeError("final response client does not accept FinalResponseDirective")
            response_text = respond(
                interaction.user_text,
                final_packet,
                capability_results,
                directive,
            )
            producer = "final_response"
            outcome = TerminalOutcomeKind.RESPONSE_EMITTED

        workpiece = workpiece.attach(
            UserOutputComponent(producer_profile_id=producer, text=response_text)
        )
        workpiece = workpiece.attach(
            TerminalOutcomeComponent(outcome=outcome, user_output_required=True)
        )
        return {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "workpiece_version": INTERACTION_WORKPIECE_VERSION,
            "final_response_directive_version": FINAL_RESPONSE_DIRECTIVE_VERSION,
            "response_action": directive.action.value,
            "response_text": response_text,
            "workpiece": workpiece.model_dump(mode="json"),
        }, []

    if stage is InteractionStage.PERSIST_RESULT:
        response = _stage_result(
            conn,
            interaction,
            InteractionStage.RESPOND,
            scheduler_key,
        )
        workpiece = InteractionWorkpiece.model_validate(response["workpiece"])
        return _persist_terminal_workpiece(
            conn,
            interaction=interaction,
            workpiece=workpiece,
        )

    return _execute_stage(
        conn,
        llm,
        envelope,
        interaction=interaction,
        scheduler_key=scheduler_key,
        registry=registry,
    )


def execute_claimed_finalized_interaction_step(
    conn: psycopg.Connection,
    llm: Any,
    *,
    claim_id: UUID,
    worker_id: str,
    scheduler_key: str = DEFAULT_SCHEDULER_KEY,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> InteractionStage:
    """Execute one durable stage while carrying the typed interaction workpiece."""

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
        output, output_refs = _execute_finalized_stage(
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
        _record_error_best_effort(
            conn,
            interaction=interaction,
            claim_id=claim_id,
            stage=stage,
            exc=exc,
        )
        _release_claim_best_effort(
            conn,
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )
        raise
