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
    """Remove model thinking markup without silently accepting an empty answer.

    Some thinking-model chat templates can emit only reasoning followed by a
    trailing ``</think>`` when generation is truncated. Persisting the empty
    post-tag string would turn a model failure into an apparently successful
    blank response. Treat missing answer content as an explicit inference
    failure instead.
    """
    text = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        _before, after = text.rsplit("</think>", 1)
        text = after

    stripped = text.strip()
    if not stripped:
        raise ValueError("LLM response contained no answer content after stripping thinking")
    return stripped


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
You are the decision step of Prometheist's Primary Agent. You receive only the
current user message; no earlier transcript is retained in your model context.
Choose exactly one action:
- RESPOND_DIRECTLY when no earlier persisted information is needed.
- RETRIEVE_CONTEXT when the Primary Agent can answer a simple memory-grounded
  request after retrieving persisted internal evidence. Set query_text to a
  short description of the needed information.
- DELEGATE_MEMORY_SPECIALIST when the user explicitly asks for a specialist or
  when the task calls for focused analysis/synthesis of persisted history. Set
  delegation_task to a self-contained bounded task for the specialist.
Do not invent system ids, retrieval limits, source filters, or persistence
metadata. Respond only with the structured decision.
"""

_RESPOND_SYSTEM_PROMPT = """\
You are Prometheist's Primary Agent. This is a fresh model invocation. Answer
using only the current user message and the bounded internal MemoryPacket, if
one is supplied. The packet contains canonical source-event metadata and exact
content. Do not claim to remember anything that is not supported by the packet.
If a memory-grounded question has no supporting packet evidence, say that the
stored history does not support an answer. Keep the response concise and do not
narrate retrieval mechanics unless the user asks.
"""

_SPECIALIST_PLAN_PROMPT = """\
You are a stateless memory-analysis specialist. You receive one bounded task and
no transcript. Describe the internal persisted information you need by returning
only: query_text (short and evidence-focused) and optional entity strings. Do
not choose retrieval algorithms, limits, databases, or system metadata.
"""

_SPECIALIST_ANSWER_PROMPT = """\
You are a stateless memory-analysis specialist. Complete the delegated task
using only the supplied bounded MemoryPacket. Treat canonical source events as
evidence. Do not infer an unsupported fact merely from topical similarity. If
the evidence is insufficient, explicitly say so. Return only the useful result,
not a discussion of your hidden reasoning.
"""


class LLMClient(Protocol):
    """One object may expose several roles; every method call is stateless."""

    def classify(self, prompt: str) -> AgentDecision: ...

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str: ...

    def plan_memory(self, task: str) -> MemoryNeedDecision: ...

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str: ...


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

    def plan_memory(self, task: str) -> MemoryNeedDecision:
        schema = MemoryNeedDecision.model_json_schema()
        last_error: Exception | None = None
        for _ in range(2):
            content = self._structured("SPECIALIST_PLAN", _SPECIALIST_PLAN_PROMPT, task, schema, 96)
            try:
                return MemoryNeedDecision.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
        raise ValueError(f"specialist memory plan failed to validate: {last_error}")

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        return self._text(
            "SPECIALIST_ANSWER",
            _SPECIALIST_ANSWER_PROMPT,
            task + _format_memory_packet(packet),
        )
