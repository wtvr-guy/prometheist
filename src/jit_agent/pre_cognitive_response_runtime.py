"""Terminal pre-cognitive finalization layered over the staged transient-worker runtime.

The existing five durable interaction stages remain unchanged. This module owns
the production boundary between capability acquisition and response synthesis:
it converts the last acquisition assessment into one persisted terminal
FinalResponseDirective before the RESPOND stage can invoke a final responder.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid5

import psycopg
from pydantic import ValidationError

from jit_agent import event_store
from jit_agent.attention_store import DEFAULT_SCHEDULER_KEY
from jit_agent.capability_registry import DEFAULT_REGISTRY, CapabilityRegistry
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
from jit_agent.models import EventType, MemoryPacket
from jit_agent.personality import configured_personality_prompt
from jit_agent.pre_cognitive_workers import (
    PRE_COGNITIVE_WORKER_SCHEME_VERSION,
    SOURCE,
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
        # Error observability is subordinate to claim liveness. A duplicate or
        # otherwise failed diagnostic write must never strand the worker lease.
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
        # Preserve the original worker exception. Lease expiry/recovery remains
        # the scheduler's fallback if explicit release itself fails.
        pass


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
        acquisition = dict(acquisition)
        acquisition["final_response_directive"] = directive.model_dump(mode="json")
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

        if directive.action is FinalResponseAction.ABSTAIN:
            response_text = directive.fallback_literal or _GENERIC_INSUFFICIENT_RESPONSE
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
        return {
            "scheme_version": PRE_COGNITIVE_WORKER_SCHEME_VERSION,
            "final_response_directive_version": FINAL_RESPONSE_DIRECTIVE_VERSION,
            "response_action": directive.action.value,
            "response_text": response_text,
        }, []

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
    """Execute one durable stage with a terminal pre-cognitive response boundary."""

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
