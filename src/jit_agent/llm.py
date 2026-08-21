"""Stateless LLM adapters for Primary and specialist agent inference."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Protocol

import httpx
from pydantic import ValidationError

from jit_agent.models import AgentDecision, MemoryNeedDecision, MemoryPacket

logger = logging.getLogger(__name__)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    text = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def _log_call(kind: str, model: str, elapsed: float, response_json: dict) -> None:
    logger.info(
        "%s model=%s elapsed=%.2fs load_duration=%sns prompt_eval_duration=%sns "
        "eval_duration=%sns prompt_eval_count=%s eval_count=%s",
        kind,
        model,
        elapsed,
        response_json.get("load_duration"),
        response_json.get("prompt_eval_duration"),
        response_json.get("eval_duration"),
        response_json.get("prompt_eval_count"),
        response_json.get("eval_count"),
    )


_CLASSIFY_SYSTEM_PROMPT = """\
You are Prometheist's stateless Primary decision step. You receive only the
current user message. Choose exactly one action:
- RESPOND_DIRECTLY when no persisted context or specialist capability is needed.
- RETRIEVE_CONTEXT for a simple memory-grounded answer; set query_text.
- DELEGATE when a bounded specialist task would help; set delegation_task.
Do not name or invent specialists, tools, ids, limits, or routing policy.
"""

_RESPOND_SYSTEM_PROMPT = """\
You are Prometheist's Primary Agent in a fresh invocation. Use only the current
message and supplied MemoryPacket, if any. Do not claim unsupported memory.
"""

_SPECIALIST_PLAN_PROMPT = """\
You are a stateless specialist in a fresh invocation. Given the role and task,
return only the persisted information need: query_text and optional entities.
Do not choose retrieval algorithms, limits, databases, or system metadata.
"""

_SPECIALIST_ANSWER_PROMPT = """\
You are a stateless specialist in a fresh invocation. Complete the task using
only the supplied MemoryPacket as evidence. Do not invent unsupported facts.
"""

_MEMORY_SPECIALIST_INSTRUCTION = (
    "Recall and synthesize persisted internal history. Preserve exact facts and "
    "distinguish unsupported claims from evidence."
)


class LLMClient(Protocol):
    """One object may expose several roles; every method call is stateless."""

    def classify(self, prompt: str) -> AgentDecision: ...

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str: ...

    def plan_specialist_memory(
        self,
        specialist_instruction: str,
        task: str,
    ) -> MemoryNeedDecision: ...

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket,
    ) -> str: ...


def _format_memory_packet(packet: MemoryPacket | None) -> str:
    if packet is None:
        return ""
    if not packet.items:
        return "\n\n[Internal MemoryPacket]\nsupported: false\nitems: []"

    blocks = []
    for index, item in enumerate(packet.items, start=1):
        provenance = ", ".join(str(value) for value in item.provenance_event_ids) or "none"
        blocks.append(
            f"{index}. event_id: {item.source_event_id}\n"
            f"   conversation_id: {item.conversation_id}\n"
            f"   conversation_seq: {item.conversation_seq}\n"
            f"   global_seq: {item.global_seq}\n"
            f"   created_at: {item.created_at.isoformat()}\n"
            f"   event_type: {item.event_type.value}\n"
            f"   source: {item.source}\n"
            f"   score: {item.score}\n"
            f"   retrieval_reasons: {', '.join(item.retrieval_reasons) or 'none'}\n"
            f"   association_provenance_event_ids: {provenance}\n"
            f"   content: {item.content}"
        )
    return (
        "\n\n[Internal MemoryPacket]\n"
        f"memory_request_id: {packet.memory_request_id}\n"
        f"supported: {str(packet.supported).lower()}\n"
        + "\n\n".join(blocks)
    )


def _specialist_input(specialist_instruction: str, task: str) -> str:
    return f"[Role]\n{specialist_instruction}\n\n[Task]\n{task}"


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:4b")
        self._client = httpx.Client(base_url=self.base_url, timeout=300.0)

    def _structured(self, kind: str, system: str, user: str, schema: dict, max_tokens: int) -> str:
        t0 = time.monotonic()
        response = self._client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema,
                "think": False,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        body = response.json()
        _log_call(kind, self.model, time.monotonic() - t0, body)
        return _strip_thinking(body["message"]["content"])

    def _text(self, kind: str, system: str, user: str, max_tokens: int = 256) -> str:
        t0 = time.monotonic()
        response = self._client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "think": False,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        response.raise_for_status()
        body = response.json()
        _log_call(kind, self.model, time.monotonic() - t0, body)
        return _strip_thinking(body["message"]["content"])

    def classify(self, prompt: str) -> AgentDecision:
        schema = AgentDecision.model_json_schema()
        last_error: Exception | None = None
        for _ in range(2):
            content = self._structured("CLASSIFY", _CLASSIFY_SYSTEM_PROMPT, prompt, schema, 96)
            try:
                return AgentDecision.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
        raise ValueError(f"LLM classification failed to validate: {last_error}")

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        return self._text(
            "RESPOND",
            _RESPOND_SYSTEM_PROMPT,
            prompt + _format_memory_packet(memory_packet),
        )

    def plan_specialist_memory(
        self,
        specialist_instruction: str,
        task: str,
    ) -> MemoryNeedDecision:
        schema = MemoryNeedDecision.model_json_schema()
        last_error: Exception | None = None
        user = _specialist_input(specialist_instruction, task)
        for _ in range(2):
            content = self._structured(
                "SPECIALIST_PLAN",
                _SPECIALIST_PLAN_PROMPT,
                user,
                schema,
                96,
            )
            try:
                return MemoryNeedDecision.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
        raise ValueError(f"specialist memory plan failed to validate: {last_error}")

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket,
    ) -> str:
        return self._text(
            "SPECIALIST_ANSWER",
            _SPECIALIST_ANSWER_PROMPT,
            _specialist_input(specialist_instruction, task) + _format_memory_packet(packet),
        )

    # Compatibility wrappers for the original v0.6 memory_specialist module.
    # The live Primary Agent now uses generic capability discovery/dispatch.
    def plan_memory(self, task: str) -> MemoryNeedDecision:
        return self.plan_specialist_memory(_MEMORY_SPECIALIST_INSTRUCTION, task)

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        return self.answer_specialist_task(_MEMORY_SPECIALIST_INSTRUCTION, task, packet)
