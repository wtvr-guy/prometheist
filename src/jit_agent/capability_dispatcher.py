"""Runtime dispatch for capabilities selected by the deterministic registry.

Agents never invoke JIT Memory or named specialists directly. They request a
capability; the registry resolves a current registration; this dispatcher binds
that registration to its application-owned executor.
"""
from __future__ import annotations

import uuid

import psycopg

from jit_agent import event_store, jit_memory
from jit_agent.capability_registry import CapabilityRegistry, DEFAULT_REGISTRY, RegisteredCapability
from jit_agent.models import (
    AgentDelegation,
    AgentResult,
    EventType,
    MemoryPacket,
    SemanticRetrievalIntentV1,
)
from jit_agent.semantic_memory import EmbeddingProvider

CapabilityOutput = MemoryPacket | AgentResult
MAX_CAPABILITY_DEPTH = 4


def invoke_capability(
    conn: psycopg.Connection,
    llm,
    *,
    registration: RegisteredCapability,
    task: str,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    before_global_seq: int,
    requesting_agent: str,
    capability_request_id: uuid.UUID | None = None,
    supplemental_query_texts: list[str] | None = None,
    semantic_intent: SemanticRetrievalIntentV1 | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
    depth: int = 0,
) -> CapabilityOutput:
    """Invoke one resolved capability without exposing implementation to callers."""
    if depth > MAX_CAPABILITY_DEPTH:
        raise RuntimeError("maximum capability invocation depth exceeded")

    capability_id = registration.descriptor.capability_id

    if registration.executor == "internal_memory":
        need = jit_memory.build_memory_need(
            task,
            supplemental_query_texts=supplemental_query_texts or [],
            semantic_intent=semantic_intent,
            conversation_id=conversation_id,
        )
        return jit_memory.request_memory(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            requesting_agent=requesting_agent,
            need=need,
            before_global_seq=before_global_seq,
            embedding_provider=embedding_provider,
        )

    if registration.executor == "stateless_specialist":
        delegation = AgentDelegation(
            specialist=capability_id,
            task=task,
            capability_request_id=capability_request_id,
        )
        event_store.record_event(
            conn,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            event_type=EventType.AGENT_DELEGATION,
            source=requesting_agent,
            payload=delegation.model_dump(mode="json"),
            payload_text=task,
        )

        from jit_agent import specialist_agent

        return specialist_agent.handle_task(
            conn,
            llm,
            registration=registration,
            task=task,
            conversation_id=conversation_id,
            correlation_id=correlation_id,
            before_global_seq=before_global_seq,
            registry=registry,
            depth=depth + 1,
            embedding_provider=embedding_provider,
        )

    raise ValueError(
        f"Capability {capability_id!r} has unsupported executor {registration.executor!r}"
    )
