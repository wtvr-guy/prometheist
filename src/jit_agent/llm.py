"""LLM client abstraction. Kept swappable behind a plain Protocol (spec section 12)."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Protocol

import httpx
from pydantic import ValidationError

from jit_agent.models import AgentDecision, RetrievalItem

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    """Some Qwen3 chat templates emit reasoning ending in a bare `</think>`
    marker (without a matching opening tag) even with think=false; keep only
    the text after the last such marker, or the whole text if none is found.
    """
    text = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def _log_call(kind: str, model: str, elapsed: float, response_json: dict) -> None:
    """Surfaces Ollama's own timing breakdown so latency issues can be
    isolated to model loading, prompt processing, or token generation.
    """
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
You are the decision step of a persistent-memory assistant. You never see prior
conversation turns automatically -- only the current message. Decide:
- RESPOND_DIRECTLY if the current message can be answered without any earlier
  persisted information (greetings, general knowledge, statements to remember).
- RETRIEVE_CONTEXT if answering requires information the user or system
  provided earlier (e.g. "what did I tell you...", "what was that number...").
  When choosing RETRIEVE_CONTEXT, set query_text to a short free-text
  description of what is needed.
Respond only with the structured decision.
"""

_RESPOND_SYSTEM_PROMPT = """\
You are a helpful assistant with persistent memory. Answer the user's message
using only the current message and any retrieved context items below. Each
item carries conversation_id, conversation_seq, global_seq, created_at,
event_type, and event_id alongside its content. conversation_seq is
authoritative for event order within one conversation; global_seq is
authoritative across all conversations. Use retrieved metadata when it is
relevant to the user's request -- do not assume the newest item is always
the one requested. Answer in one short, direct sentence; do not narrate your
reasoning or list the retrieved items.
"""


class LLMClient(Protocol):
    def classify(self, prompt: str) -> AgentDecision: ...

    def respond(self, prompt: str, retrieved_items: list[RetrievalItem] | None) -> str: ...


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:4b")
        self._client = httpx.Client(base_url=self.base_url, timeout=300.0)

    def classify(self, prompt: str) -> AgentDecision:
        schema = AgentDecision.model_json_schema()
        last_error: Exception | None = None
        for _ in range(2):
            t0 = time.monotonic()
            response = self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "format": schema,
                    "think": False,
                    "stream": False,
                    "options": {"num_predict": 64},
                },
            )
            response.raise_for_status()
            body = response.json()
            _log_call("CLASSIFY", self.model, time.monotonic() - t0, body)
            content = _strip_thinking(body["message"]["content"])
            try:
                return AgentDecision.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
        raise ValueError(f"LLM classification failed to validate: {last_error}")

    def respond(self, prompt: str, retrieved_items: list[RetrievalItem] | None) -> str:
        context_block = ""
        if retrieved_items:
            blocks = [
                f"{i}. conversation_id: {item.conversation_id}\n"
                f"   conversation_seq: {item.conversation_seq}\n"
                f"   global_seq: {item.global_seq}\n"
                f"   created_at: {item.created_at.isoformat()}\n"
                f"   event_type: {item.event_type.value}\n"
                f"   event_id: {item.source_event_id}\n"
                f"   content: {item.content}"
                for i, item in enumerate(retrieved_items, start=1)
            ]
            context_block = "\n\n[Retrieved context]\n" + "\n\n".join(blocks)

        t0 = time.monotonic()
        response = self._client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _RESPOND_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt + context_block},
                ],
                "think": False,
                "stream": False,
                "options": {"num_predict": 256},
            },
        )
        response.raise_for_status()
        body = response.json()
        _log_call("RESPOND", self.model, time.monotonic() - t0, body)
        return _strip_thinking(body["message"]["content"])
