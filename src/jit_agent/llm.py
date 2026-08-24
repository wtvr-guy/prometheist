"""Stateless LLM adapters for Primary and specialist-agent inference."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Protocol

import httpx
from pydantic import ValidationError

from jit_agent.models import AgentDecision, MemoryPacket

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


_RETRIEVAL_INTENT_GUIDANCE = """\
When the requested capability is access to persisted internal history, also set
retrieval_intent using only the schema's bounded enum values. This is a soft
query-time retrieval hint; it never labels stored events or asserts facts.
Choose target by the requested answer:
- FACT: a directly stated fact.
- CURRENT_STATE: the currently applicable state or value.
- PRIOR_STATE: the immediately preceding state or value.
- STATE_TRANSITION: a change from an earlier state to a later state.
- IDENTITY: the identity of a person, object, or named item.
- RELATIONSHIP: a relationship between referenced subjects.
- LOCATION: a requested location.
- TIME: a date, time, schedule, or temporal value.
- VALUE: a numeric, monetary, identifier, or other concrete value.
- BOOLEAN_STATUS: whether a requested condition is true or false.
- PREFERENCE: a preference or habitual choice.
- PROCEDURE: a procedure, method, or operational requirement.
- GENERAL: none of the more specific categories fits.
Choose temporal_focus as CURRENT, PREVIOUS, AS_OF_REFERENCE_TIME, HISTORICAL,
or UNSPECIFIED. Do not invent sources, repositories, locations, relationships,
or facts in order to choose these enums.
"""

_CLASSIFY_SYSTEM_PROMPT = f"""\
You are Prometheist's stateless Primary decision step. You receive only the
current user message. Choose exactly one action:
- RESPOND_DIRECTLY if the current message alone is sufficient.
- REQUEST_CAPABILITY if additional information access or functionality is needed.
For REQUEST_CAPABILITY, capability_query briefly describes the needed capability.
capability_input may contain a narrower input; omit it when the whole user message
should be passed unchanged. Do not name implementations, ids, limits, or routing.
{_RETRIEVAL_INTENT_GUIDANCE}
"""

_RESPOND_SYSTEM_PROMPT = """\
You are Prometheist's Primary Agent in a fresh invocation. Use only the current
message and supplied MemoryPacket, if any. ADMITTED items have passed the
system's deterministic evidence gate. SEMANTIC_CANDIDATE items are canonical
source events recovered by semantic similarity but are not admitted facts.
You may use a SEMANTIC_CANDIDATE only when its content itself directly supports
the answer requested by the current message. Never treat its similarity score,
retrieval rank, or mere presence as evidence. If no supplied item's source text
directly supports the answer, say that persisted evidence is insufficient.
Do not claim unsupported memory.
"""

_SPECIALIST_DECISION_PROMPT = f"""\
You are a stateless specialist in a fresh invocation. Given only your role and
current task, choose exactly one action:
- RESPOND_DIRECTLY if the task can be completed from supplied information alone.
- REQUEST_CAPABILITY if additional information access or functionality is needed.
For REQUEST_CAPABILITY, capability_query describes the needed functionality and
capability_input gives the narrow subtask or information needed. For prior or
persisted Prometheist information, describe the capability as persisted internal
history access and put only the specific recall target in capability_input.
Do not name implementations, capability ids, limits, or routing policy.
{_RETRIEVAL_INTENT_GUIDANCE}
"""

_SPECIALIST_ANSWER_PROMPT = """\
You are a stateless specialist in a fresh invocation. Complete the supplied task
using only the role, task, and bounded MemoryPacket if one is supplied. ADMITTED
items have passed deterministic evidence admission. SEMANTIC_CANDIDATE items are
canonical source events recovered by semantic similarity and are not themselves
assertions that the requested relation is true. You may use a candidate only
when its source text itself directly supports the requested conclusion. Ignore
similarity score and rank as evidence. If the supplied source text does not
actually establish the answer, state that persisted evidence is insufficient.
Do not invent unsupported facts.
"""


class LLMClient(Protocol):
    """One object may expose several roles; every method call is stateless."""

    def classify(self, prompt: str) -> AgentDecision: ...

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str: ...

    def decide_specialist_action(
        self,
        specialist_instruction: str,
        task: str,
    ) -> AgentDecision: ...

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket | None,
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
            f"   evidence_status: {item.evidence_status.value}\n"
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

    def _decision(self, kind: str, system: str, user: str) -> AgentDecision:
        schema = AgentDecision.model_json_schema()
        last_error: Exception | None = None
        for _ in range(2):
            content = self._structured(kind, system, user, schema, 160)
            try:
                return AgentDecision.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
        raise ValueError(f"agent decision failed to validate: {last_error}")

    def classify(self, prompt: str) -> AgentDecision:
        return self._decision("CLASSIFY", _CLASSIFY_SYSTEM_PROMPT, prompt)

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        return self._text(
            "RESPOND",
            _RESPOND_SYSTEM_PROMPT,
            prompt + _format_memory_packet(memory_packet),
        )

    def decide_specialist_action(
        self,
        specialist_instruction: str,
        task: str,
    ) -> AgentDecision:
        return self._decision(
            "SPECIALIST_DECISION",
            _SPECIALIST_DECISION_PROMPT,
            _specialist_input(specialist_instruction, task),
        )

    def answer_specialist_task(
        self,
        specialist_instruction: str,
        task: str,
        packet: MemoryPacket | None,
    ) -> str:
        return self._text(
            "SPECIALIST_ANSWER",
            _SPECIALIST_ANSWER_PROMPT,
            _specialist_input(specialist_instruction, task) + _format_memory_packet(packet),
        )
