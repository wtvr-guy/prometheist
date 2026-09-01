"""Immutable interaction artifacts for exact stateless LLM invocation envelopes."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from jit_agent import artifact_journal


def write_llm_invocation(
    *,
    interaction_id: UUID,
    conversation_id: UUID,
    correlation_id: UUID,
    task_id: UUID,
    assignment_id: UUID,
    stage: str,
    claim_id: UUID,
    invocation_index: int,
    kind: str,
    model: str,
    base_url: str,
    system_prompt: str,
    user_prompt: str,
    schema: dict[str, Any],
    max_tokens: int,
    temperature: float,
    output: str | None,
    error_type: str | None,
    error_message: str | None,
) -> dict[str, Any]:
    """Persist the exact request contract and resulting normalized model output."""

    return artifact_journal.write_interaction_artifact(
        artifact_key=(
            f"llm-invocation:{stage}:{claim_id}:{invocation_index}:{kind}"
        ),
        artifact_type="LLM_INVOCATION",
        interaction_id=interaction_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        task_id=task_id,
        assignment_id=assignment_id,
        stage=stage,
        producer="percept_response_v2/ollama",
        payload={
            "claim_id": str(claim_id),
            "invocation_index": invocation_index,
            "kind": kind,
            "model": model,
            "base_url": base_url,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "schema": schema,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "output": output,
            "error_type": error_type,
            "error_message": error_message,
        },
    )
