"""Fresh-process entry point for one already-guarded interaction worker step."""
from __future__ import annotations

import os
import sys
from uuid import UUID, uuid5

from jit_agent import db, event_store
from jit_agent.durable_response_llm import DurableResponseBudgetedOllamaClient
from jit_agent.interaction_runtime import execute_claimed_interaction_step
from jit_agent.interaction_store import load_interaction_by_task
from jit_agent.models import EventType
from jit_agent.response_policy import RESPONSE_POLICY_VERSION, ResponsePolicy
from jit_agent.worker_store import load_worker_claim_envelope


RESPONSE_POLICY_SOURCE = "response_policy"


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
            if envelope.step.step_key != "RESPOND":
                raise RuntimeError("response policy was classified outside the RESPOND stage")
            event_store.record_event(
                conn,
                conversation_id=interaction.conversation_id,
                correlation_id=interaction.correlation_id,
                event_type=EventType.SYSTEM_EVENT,
                source=RESPONSE_POLICY_SOURCE,
                payload={
                    "policy_version": RESPONSE_POLICY_VERSION,
                    "claim_id": str(claim_id),
                    "step_id": str(envelope.step.step_id),
                    "stage": envelope.step.step_key,
                    "policy": policy.model_dump(mode="json"),
                },
                event_id=uuid5(claim_id, "response-policy"),
            )

        execute_claimed_interaction_step(
            conn,
            DurableResponseBudgetedOllamaClient(
                response_policy_sink=record_response_policy,
            ),
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )


if __name__ == "__main__":
    main()
