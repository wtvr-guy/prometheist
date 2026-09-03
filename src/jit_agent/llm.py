"""Stateless Ollama transport and evidence-formatting primitives."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from jit_agent.models import MemoryPacket
from jit_agent.ollama_runtime import configured_ollama_model

logger = logging.getLogger(__name__)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_VERBATIM_LITERAL_RE = re.compile(
    r"(?<![\w-])"
    r"(?=[A-Za-z0-9-]{6,}(?![\w-]))"
    r"(?=[A-Za-z0-9-]*[A-Za-z])"
    r"(?=[A-Za-z0-9-]*\d)"
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?![\w-])"
)
_MAX_VERBATIM_LITERALS = 16
_CONTROL_TEMPERATURE = 0.0
_DEFAULT_RESPONSE_TEMPERATURE = 0.65
_MIN_RESPONSE_TEMPERATURE = 0.0
_MAX_RESPONSE_TEMPERATURE = 2.0
_RESPONSE_KINDS = frozenset({"FINAL_RESPONSE_V2"})


class OllamaStructuredOutputError(ValueError):
    """Ollama completed a request without usable final structured content."""


class _TextAnswer(BaseModel):
    """Validated envelope for irreducibly user-facing natural language."""

    answer: str = Field(
        min_length=1,
        description="Final user-facing answer only, with no analysis or preamble.",
    )

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("answer must not be blank")
        return normalized


def configured_response_temperature() -> float:
    """Return the user-facing response temperature without affecting control workers."""

    raw = os.environ.get("PROMETHEIST_RESPONSE_TEMPERATURE", "").strip()
    if not raw:
        return _DEFAULT_RESPONSE_TEMPERATURE
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid PROMETHEIST_RESPONSE_TEMPERATURE=%r; using %.2f",
            raw,
            _DEFAULT_RESPONSE_TEMPERATURE,
        )
        return _DEFAULT_RESPONSE_TEMPERATURE
    if not _MIN_RESPONSE_TEMPERATURE <= value <= _MAX_RESPONSE_TEMPERATURE:
        logger.warning(
            "PROMETHEIST_RESPONSE_TEMPERATURE=%r outside %.1f..%.1f; using %.2f",
            raw,
            _MIN_RESPONSE_TEMPERATURE,
            _MAX_RESPONSE_TEMPERATURE,
            _DEFAULT_RESPONSE_TEMPERATURE,
        )
        return _DEFAULT_RESPONSE_TEMPERATURE
    return value


def _strip_thinking(text: str) -> str:
    text = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        _before, after = text.rsplit("</think>", 1)
        text = after
    stripped = text.strip()
    if not stripped:
        raise ValueError("LLM response contained no answer content after stripping thinking")
    return stripped


def _is_qwen3_instruct(model: str) -> bool:
    """Return whether Ollama is serving a dedicated non-thinking Qwen3 instruct model."""

    leaf = model.rsplit("/", 1)[-1].strip().casefold()
    return leaf.startswith("qwen3") and "instruct" in leaf


def _uses_qwen3_soft_switch(model: str) -> bool:
    """Return whether a hybrid Qwen3 model may need the legacy /no_think hint."""

    leaf = model.rsplit("/", 1)[-1].strip().casefold()
    return leaf.startswith("qwen3") and not _is_qwen3_instruct(model)


def _nonthinking_user_input(model: str, user: str) -> str:
    """Apply the Qwen3 hybrid soft switch without modifying instruct-model input."""

    if not _uses_qwen3_soft_switch(model):
        return user
    return f"{user}\n\n/no_think"


def _render_qwen3_instruct_raw_prompt(system: str, user: str) -> str:
    """Render the official no-tools Qwen3 Instruct 2507 chat-template shape."""

    return (
        "<|im_start|>system\n"
        f"{system}<|im_end|>\n"
        "<|im_start|>user\n"
        f"{user}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def _retry_token_caps(initial: int) -> tuple[int, int]:
    if initial < 1:
        raise ValueError("initial token cap must be positive")
    return initial, min(512, max(initial + 16, initial * 2))


def _build_verbatim_placeholder_maps(
    *texts: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Replace opaque literals with application-restored placeholders."""

    literal_to_placeholder: dict[str, str] = {}
    placeholder_to_literal: dict[str, str] = {}
    for text in texts:
        for match in _VERBATIM_LITERAL_RE.finditer(text):
            literal = match.group(0)
            if literal in literal_to_placeholder:
                continue
            if len(literal_to_placeholder) == _MAX_VERBATIM_LITERALS:
                return literal_to_placeholder, placeholder_to_literal
            placeholder = f"[[VERBATIM_{len(literal_to_placeholder)}]]"
            literal_to_placeholder[literal] = placeholder
            placeholder_to_literal[placeholder] = literal
    return literal_to_placeholder, placeholder_to_literal


def _mask_verbatim_literals(text: str, literal_to_placeholder: dict[str, str]) -> str:
    if not literal_to_placeholder:
        return text
    return _VERBATIM_LITERAL_RE.sub(
        lambda match: literal_to_placeholder.get(match.group(0), match.group(0)),
        text,
    )


def _restore_verbatim_literals(text: str, placeholder_to_literal: dict[str, str]) -> str:
    restored = text
    for placeholder, literal in placeholder_to_literal.items():
        restored = restored.replace(placeholder, literal)
    if "VERBATIM_" in restored:
        raise ValueError("model altered an application-owned verbatim placeholder")
    return restored


def _verbatim_source_texts(prompt: str, packet: MemoryPacket | None) -> tuple[str, ...]:
    if packet is None:
        return (prompt,)
    return (prompt, *(item.content for item in packet.items))


def _log_call(kind: str, model: str, elapsed: float, response_json: dict) -> None:
    message = response_json.get("message")
    if not isinstance(message, dict):
        message = {}
    content = message.get("content")
    if not isinstance(content, str):
        generated = response_json.get("response")
        content = generated if isinstance(generated, str) else ""
    thinking = message.get("thinking")
    if not isinstance(thinking, str):
        raw_thinking = response_json.get("thinking")
        thinking = raw_thinking if isinstance(raw_thinking, str) else ""
    logger.info(
        "%s model=%s elapsed=%.2fs load_duration=%sns prompt_eval_duration=%sns "
        "eval_duration=%sns prompt_eval_count=%s eval_count=%s done_reason=%s "
        "content_chars=%s thinking_chars=%s",
        kind,
        model,
        elapsed,
        response_json.get("load_duration"),
        response_json.get("prompt_eval_duration"),
        response_json.get("eval_duration"),
        response_json.get("prompt_eval_count"),
        response_json.get("eval_count"),
        response_json.get("done_reason"),
        len(content),
        len(thinking),
    )


def _format_response_memory_packet(
    packet: MemoryPacket | None,
    *,
    literal_to_placeholder: dict[str, str] | None = None,
) -> str:
    """Render a compact chronology for final answer synthesis.

    Retrieval ranking, event identifiers, timestamps, and provenance remain
    application-owned. The response worker receives only evidence content,
    event role, relative chronology, and whether evidence belongs to the most
    recent conversation represented in the bounded packet.
    """

    if packet is None:
        return ""
    if not packet.items:
        return "\n\n[Evidence timeline: oldest to newest]\nsupported: false\nitems: []"

    literal_to_placeholder = literal_to_placeholder or {}
    ordered_items = sorted(
        packet.items,
        key=lambda item: (item.global_seq, item.conversation_seq, str(item.source_event_id)),
    )
    recent_conversation_id = ordered_items[-1].conversation_id
    blocks = []
    for index, item in enumerate(ordered_items):
        content = _mask_verbatim_literals(item.content, literal_to_placeholder)
        scope = (
            "recent_conversation"
            if item.conversation_id == recent_conversation_id
            else "historical_context"
        )
        blocks.append(
            f"evidence_order: {index}\n"
            f"conversation_scope: {scope}\n"
            f"event_type: {item.event_type.value}\n"
            f"content: {content}"
        )
    return (
        "\n\n[Evidence timeline: oldest to newest]\n"
        f"supported: {str(packet.supported).lower()}\n"
        + "\n\n".join(blocks)
    )


def _format_capability_result_data(results: tuple[dict[str, Any], ...]) -> str:
    if not results:
        return ""
    return "\n\n[Structured capability results]\n" + json.dumps(
        list(results),
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or configured_ollama_model()
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=300.0,
            trust_env=False,
        )

    def temperature_for_kind(self, kind: str) -> float:
        """Keep control workers deterministic while allowing expressive responses."""

        if kind in _RESPONSE_KINDS:
            return configured_response_temperature()
        return _CONTROL_TEMPERATURE

    def _structured(
        self,
        kind: str,
        system: str,
        user: str,
        schema: dict,
        max_tokens: int,
    ) -> str:
        t0 = time.monotonic()
        temperature = self.temperature_for_kind(kind)
        if _is_qwen3_instruct(self.model):
            request_path = "/api/generate"
            request_json: dict[str, Any] = {
                "model": self.model,
                "prompt": _render_qwen3_instruct_raw_prompt(system, user),
                "raw": True,
                "format": schema,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }
        else:
            request_path = "/api/chat"
            request_json = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": _nonthinking_user_input(self.model, user),
                    },
                ],
                "format": schema,
                "think": False,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }
        response = self._client.post(request_path, json=request_json)
        response.raise_for_status()
        body = response.json()
        _log_call(kind, self.model, time.monotonic() - t0, body)

        raw_thinking: Any = None
        if request_path == "/api/generate":
            raw_content = body.get("response")
            raw_thinking = body.get("thinking")
        else:
            message = body.get("message")
            if not isinstance(message, dict):
                raise OllamaStructuredOutputError(
                    "Ollama response omitted the chat message object"
                )
            raw_content = message.get("content")
            raw_thinking = message.get("thinking")

        content = raw_content if isinstance(raw_content, str) else ""
        try:
            return _strip_thinking(content)
        except ValueError as exc:
            diagnostics = {
                "content_length": len(content),
                "done_reason": body.get("done_reason"),
                "eval_count": body.get("eval_count"),
                "max_tokens": max_tokens,
                "prompt_eval_count": body.get("prompt_eval_count"),
                "temperature": temperature,
                "thinking_length": (
                    len(raw_thinking) if isinstance(raw_thinking, str) else 0
                ),
                "transport": "raw-generate" if request_path == "/api/generate" else "chat",
            }
            raise OllamaStructuredOutputError(
                "Ollama produced no usable final content: "
                + json.dumps(diagnostics, sort_keys=True, separators=(",", ":"))
            ) from exc

    def _text(self, kind: str, system: str, user: str, max_tokens: int = 256) -> str:
        last_error: Exception | None = None
        for token_cap in _retry_token_caps(max_tokens):
            try:
                content = self._structured(
                    kind,
                    system,
                    user,
                    _TextAnswer.model_json_schema(),
                    token_cap,
                )
                return _TextAnswer.model_validate_json(content).answer
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"model answer failed to validate: {last_error}")
