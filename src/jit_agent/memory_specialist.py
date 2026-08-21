"""Compatibility wrapper for the original v0.6 memory specialist API.

The live MAS resolves ``memory_specialist`` through the deterministic capability
registry and executes it through ``specialist_agent``. This module remains so
older direct callers/tests can use the original ``plan_memory`` /
``answer_memory_task`` interface without creating a second execution path.
"""
from __future__ import annotations

import uuid
from typing import Protocol

import psycopg

from jit_agent import capability_registry, specialist_agent
from jit_agent.models import AgentResult, MemoryNeedDecision, MemoryPacket

SOURCE = "memory_specialist"


class MemorySpecialistLLM(Protocol):
    def plan_memory(self, task: str) -> MemoryNeedDecision: ...

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str: ...


class _LegacyLLMAdapter:
    def __init__(self, llm: MemorySpecialistLLM) -> None:
        self._llm = llm

    def plan_specialist_memory(
        self,
        specialist_instruction: str,
        task: str,
    ) -> MemoryNeedDecision:
        return self._llm.plan_memory(task)

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket,
    ) -> str:
        return self._llm.answer_memory_task(task, packet)


def handle_task(
    conn: psycopg.Connection,
    llm: MemorySpecialistLLM,
    *,
    task: str,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    before_global_seq: int,
) -> AgentResult:
    registration = capability_registry.DEFAULT_REGISTRY.get(SOURCE)
    return specialist_agent.handle_task(
        conn,
        _LegacyLLMAdapter(llm),
        registration=registration,
        task=task,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        before_global_seq=before_global_seq,
    )
