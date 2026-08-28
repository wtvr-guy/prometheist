"""Fresh-process entry point for one already-guarded interaction worker step."""
from __future__ import annotations

import os
import sys
from uuid import UUID, uuid5

import psycopg

from jit_agent import db, event_store
from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.interaction_runtime import execute_claimed_interaction_step
from jit_agent.interaction_store import load_interaction_by_task
from jit_agent.models import EventType
from jit_agent.response_policy import RESPONSE_POLICY_VERSION, ResponsePolicy
from jit_agent.worker_store import load_worker_claim_envelope


RESPONSE_POLICY_SOURCE = "response_policy"
RESPONSE_FALLBACK_SOURCE = "response_fallback"


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing guarded worker environment value: {name}")
    return value


def _record_response_policy_event(
    conn: psycopg.Connection,
    *,
    conversation_id: UUID,
    correlation_id: UUID,
    claim_id: UUID,
    step_id: UUID,
    stage: str,
    policy: ResponsePolicy,
) -> UUID:
    """Append the exact closed policy that governs one response attempt."""

    if stage != "RESPOND":
        raise RuntimeError("response policy was classified outside the RESPOND stage")
    event_id = uuid5(claim_id, "response-policy")
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=RESPONSE_POLICY_SOURCE,
        payload={
            "policy_version": RESPONSE_POLICY_VERSION,
            "claim_id": str(claim_id),
            "step_id": str(step_id),
            "stage": stage,
            "policy": policy.model_dump(mode="json"),
        },
        event_id=event_id,
    )
    return event_id


def _record_response_fallback_event(
    conn: psycopg.Connection,
    *,
    conversation_id: UUID,
    correlation_id: UUID,
    claim_id: UUID,
    step_id: UUID,
    stage: str,
    fallback_literal: str | None,
) -> UUID:
    """Append the validated current-percept fallback decision used by a response."""

    if stage != "RESPOND":
        raise RuntimeError("response fallback was selected outside the RESPOND stage")
    event_id = uuid5(claim_id, "response-fallback")
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.SYSTEM_EVENT,
        source=RESPONSE_FALLBACK_SOURCE,
        payload={
            "policy_version": RESPONSE_POLICY_VERSION,
            "claim_id": str(claim_id),
            "step_id": str(step_id),
            "stage": stage,
            "fallback_literal": fallback_literal,
        },
        event_id=event_id,
    )
    return event_id


def main() -> None:
    _configure_utf8_streams()
    claim_id = UUID(_required_environment("PROMETHEIST_WORKER_CLAIM_ID"))
    worker_id = _required_environment("PROMETHEIST_WORKER_ID")
    scheduler_key = _required_environment("PROMETHEIST_WORKER_SCHEDULER_KEY")
    with db.get_connection() as conn:
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

        def record_response_policy(policy: ResponsePolicy) -> None:
            _record_response_policy_event(
                conn,
                conversation_id=interaction.conversation_id,
                correlation_id=interaction.correlation_id,
                claim_id=claim_id,
                step_id=envelope.step.step_id,
                stage=envelope.step.step_key,
                policy=policy,
            )

        def record_response_fallback(fallback_literal: str | None) -> None:
            _record_response_fallback_event(
                conn,
                conversation_id=interaction.conversation_id,
                correlation_id=interaction.correlation_id,
                claim_id=claim_id,
                step_id=envelope.step.step_id,
                stage=envelope.step.step_key,
                fallback_literal=fallback_literal,
            )

        execute_claimed_interaction_step(
            conn,
            DurableResponseBudgetedOllamaClient(
                response_policy_sink=record_response_policy,
                response_fallback_sink=record_response_fallback,
            ),
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )


if __name__ == "__main__":
    main()
