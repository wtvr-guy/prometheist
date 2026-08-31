"""Stateless model adapters for disposable interaction/capability workers."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.interaction_policy import (
    CapabilityResultSummary,
    InteractionDecision,
)
from jit_agent.models import (
    CrossReferenceCandidateSelection,
    FocusedMemoryCandidateSelection,
    MemoryCandidateSelection,
    MemoryPacket,
)
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
_RESPONSE_KINDS = frozenset({"RESPOND", "FINAL_RESPONSE_V2"})


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


_CLASSIFY_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist routing worker. You have no inherited
transcript or model context. You receive the current percept, the bounded memory
currently available to cognition, structured results from completed capabilities,
and an application-owned numbered catalog of capabilities that are legal now.

Return exactly one closed action:
- RESPOND: the available information is sufficient to answer now. Return no
  capability indices.
- USE_CAPABILITIES: more work is required before answering. Select the capability
  indices from the supplied catalog that are actually required. Prefer the
  smallest requirement set that can advance the task.

Capability indices are a requirement set, never an execution order. Prometheist
owns dependencies, ordering, resource admission, and execution. A later fresh
routing call may receive an expanded catalog after capabilities complete. You
may select an original capability again or a newly exposed follow-up capability
when further work is genuinely needed.

Do not write capability names, queries, arguments, explanations, entities,
phrases, ordering instructions, or any other natural-language control value.
Return only the closed action and bounded integer indices required by the schema.
"""

_RESPOND_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist response worker. You are summoned only
after a fresh routing worker explicitly selected RESPOND. Use the current
message, the supplied bounded final evidence timeline, completed structured
capability results, and general model knowledge as appropriate. Never invent
personal or history-specific information absent from those sources.

The evidence timeline is presented in chronological order from oldest to newest.
Event types identify who or what produced each statement. Resolve temporal and
relational references such as "just", "previous", "this", and "that" against
the latest relevant evidence, not merely the closest lexical match. When a
request asks for multiple named fields, resolve each field independently from
its most specific supporting evidence, then place the fields in exactly the
user-requested order. Do not substitute a semantically related value for a
differently named field.

Put every requested value in the first sentence and copy opaque user-provided
identifiers exactly. Some opaque literals may be represented as application-
owned placeholders such as [[VERBATIM_0]]. Treat each placeholder as one exact,
indivisible source literal: copy the placeholder exactly when that literal is
needed and never edit, reformat, abbreviate, or add punctuation inside it. The
application restores the original source bytes after generation.

Unless the user requests detail, answer concisely with no headings, source
quotations, or prefatory analysis. Reconcile all source statements before
answering. Do not expose packet labels, event ids, scores, retrieval mechanics,
or hidden reasoning unless asked.

A USER_PROMPT is direct evidence of what the user previously said, named,
preferred, required, planned, reported, or instructed; it need not independently
prove the external world. Later user-authored corrections supersede earlier
statements. Historical assistant responses never override a user-authored
constraint. When an applicable explicit user constraint exists, honor it rather
than recommending a conflicting option.

If requested personal or historical information is not established by the
current message or supplied source evidence, say that persisted evidence is
insufficient. Do not claim unsupported memory.
"""

_DEEPER_RESEARCH_SELECTION_PROMPT = """\
You are a fresh disposable Prometheist internal-research worker. The current
MemoryPacket is a broad or accumulated bounded candidate set. Select one or more
candidate_indices whose canonical source events deserve deeper associative
investigation for the current task.

Choose candidates, not words. Prometheist will resolve each selected index to an
application-owned canonical event ID and expand deterministic associations around
those events. Prefer the smallest set that covers the unresolved question.

Do not write queries, entities, event IDs, explanations, phrases, or answers.
Return only candidate_indices from the supplied MemoryPacket.
"""

_CROSS_REFERENCE_SELECTION_PROMPT = """\
You are a fresh disposable Prometheist cross-reference worker. Select multiple
candidate_indices from the supplied MemoryPacket that should be investigated
together because their relationship, agreement, conflict, causality, or shared
context may resolve the current task.

Prometheist will resolve the indices to canonical source events and run one joint,
bounded associative investigation over the selected set. Do not describe the
relationship yourself.

Do not write queries, entities, event IDs, explanations, phrases, or answers.
Return only candidate_indices from the supplied MemoryPacket.
"""

_FOCUSED_RECALL_SELECTION_PROMPT = """\
You are a fresh disposable Prometheist focused-recall worker. The supplied
MemoryPacket contains candidates returned by broader internal research. Select a
single candidate_index for the deepest bounded associative investigation.

Choose the candidate most likely to resolve the remaining ambiguity. Prometheist
will resolve the index to the canonical event and expand a larger association
neighborhood around that event. If a previous focused attempt failed, a later
fresh routing worker may choose this capability again and focus on a different
candidate.

Do not write a query, entity, event ID, explanation, phrase, or answer. Return
only candidate_index.
"""


class LLMClient(Protocol):
    """Every method call is an independent disposable model invocation."""

    def classify(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        completed_results: tuple[CapabilityResultSummary, ...] = (),
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> InteractionDecision: ...

    def respond(
        self,
        prompt: str,
        memory_packet: MemoryPacket | None,
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> str: ...

    def select_research_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> MemoryCandidateSelection: ...

    def select_cross_reference_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> CrossReferenceCandidateSelection: ...

    def select_focused_candidate(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> FocusedMemoryCandidateSelection: ...


def _format_memory_packet(
    packet: MemoryPacket | None,
    *,
    literal_to_placeholder: dict[str, str] | None = None,
) -> str:
    if packet is None:
        return ""
    if not packet.items:
        return "\n\n[Internal MemoryPacket]\nsupported: false\nitems: []"

    literal_to_placeholder = literal_to_placeholder or {}
    blocks = []
    for index, item in enumerate(packet.items):
        provenance = ", ".join(str(value) for value in item.provenance_event_ids) or "none"
        content = _mask_verbatim_literals(item.content, literal_to_placeholder)
        blocks.append(
            f"candidate_index: {index}\n"
            f"   event_id: {item.source_event_id}\n"
            f"   conversation_id: {item.conversation_id}\n"
            f"   conversation_seq: {item.conversation_seq}\n"
            f"   global_seq: {item.global_seq}\n"
            f"   created_at: {item.created_at.isoformat()}\n"
            f"   event_type: {item.event_type.value}\n"
            f"   source: {item.source}\n"
            f"   score: {item.score}\n"
            f"   retrieval_reasons: {', '.join(item.retrieval_reasons) or 'none'}\n"
            f"   association_provenance_event_ids: {provenance}\n"
            f"   content: {content}"
        )
    return (
        "\n\n[Internal MemoryPacket]\n"
        f"memory_request_id: {packet.memory_request_id}\n"
        f"supported: {str(packet.supported).lower()}\n"
        + "\n\n".join(blocks)
    )


def _format_router_memory_packet(packet: MemoryPacket) -> str:
    """Expose only cognition-relevant memory evidence to the routing worker.

    Durable event identifiers, chronology, scores, retrieval diagnostics, and
    association provenance remain application-owned. The router needs evidence
    content to decide whether another capability is required, not transport or
    audit metadata.
    """

    if not packet.items:
        return "\n\n[Activated memory]\nsupported: false\nitems: []"
    blocks = [
        (
            f"item: {index}\n"
            f"event_type: {item.event_type.value}\n"
            f"content: {item.content}"
        )
        for index, item in enumerate(packet.items)
    ]
    return (
        "\n\n[Activated memory]\n"
        f"supported: {str(packet.supported).lower()}\n"
        + "\n\n".join(blocks)
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


def _format_capability_catalog(catalog: tuple[CapabilityDescriptor, ...]) -> str:
    if not catalog:
        return "\n\n[Capability catalog]\nnone"
    entries = "\n".join(
        f"{index}: {descriptor.capability_id} | {descriptor.kind.value} | {descriptor.description}"
        for index, descriptor in enumerate(catalog)
    )
    return f"\n\n[Capability catalog]\n{entries}"


def _format_completed_results(results: tuple[CapabilityResultSummary, ...]) -> str:
    if not results:
        return "\n\n[Completed capability results]\nnone"
    entries = "\n".join(
        (
            f"round={item.round_index} capability={item.capability_id} "
            f"supported={item.supported} item_count={item.item_count} "
            f"result_keys={','.join(item.result_keys) or 'none'}"
        )
        for item in results
    )
    return f"\n\n[Completed capability results]\n{entries}"


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

    def classify(
        self,
        prompt: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
        completed_results: tuple[CapabilityResultSummary, ...] = (),
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> InteractionDecision:
        schema = InteractionDecision.model_json_schema()
        last_error: Exception | None = None
        user = (
            prompt
            + _format_router_memory_packet(memory_packet)
            + _format_completed_results(completed_results)
            + _format_capability_result_data(capability_results)
            + _format_capability_catalog(capability_catalog)
        )
        for token_cap in _retry_token_caps(48):
            try:
                content = self._structured(
                    "RECURRENT_CAPABILITY_DECISION",
                    _CLASSIFY_SYSTEM_PROMPT,
                    user,
                    schema,
                    token_cap,
                )
                return InteractionDecision.model_validate_json(content)
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"interaction capability selection failed to validate: {last_error}")

    def respond(
        self,
        prompt: str,
        memory_packet: MemoryPacket | None,
        capability_results: tuple[dict[str, Any], ...] = (),
    ) -> str:
        literal_to_placeholder, placeholder_to_literal = _build_verbatim_placeholder_maps(
            *_verbatim_source_texts(prompt, memory_packet)
        )
        masked_prompt = _mask_verbatim_literals(prompt, literal_to_placeholder)
        answer = self._text(
            "RESPOND",
            _RESPOND_SYSTEM_PROMPT,
            masked_prompt
            + _format_response_memory_packet(
                memory_packet,
                literal_to_placeholder=literal_to_placeholder,
            )
            + _format_capability_result_data(capability_results),
        )
        return _restore_verbatim_literals(answer, placeholder_to_literal)

    def select_research_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> MemoryCandidateSelection:
        if not packet.items:
            raise ValueError("deeper research requires at least one memory candidate")
        schema = MemoryCandidateSelection.model_json_schema()
        last_error: Exception | None = None
        user = task + _format_memory_packet(packet)
        for token_cap in _retry_token_caps(32):
            try:
                content = self._structured(
                    "DEEPER_RESEARCH_CANDIDATES",
                    _DEEPER_RESEARCH_SELECTION_PROMPT,
                    user,
                    schema,
                    token_cap,
                )
                selection = MemoryCandidateSelection.model_validate_json(content)
                if any(index >= len(packet.items) for index in selection.candidate_indices):
                    raise ValueError("deeper research selected a candidate outside the packet")
                return selection
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"deeper-research candidate selection failed: {last_error}")

    def select_cross_reference_candidates(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> CrossReferenceCandidateSelection:
        if len(packet.items) < 2:
            raise ValueError("cross reference requires at least two memory candidates")
        schema = CrossReferenceCandidateSelection.model_json_schema()
        last_error: Exception | None = None
        user = task + _format_memory_packet(packet)
        for token_cap in _retry_token_caps(32):
            try:
                content = self._structured(
                    "CROSS_REFERENCE_CANDIDATES",
                    _CROSS_REFERENCE_SELECTION_PROMPT,
                    user,
                    schema,
                    token_cap,
                )
                selection = CrossReferenceCandidateSelection.model_validate_json(content)
                if any(index >= len(packet.items) for index in selection.candidate_indices):
                    raise ValueError("cross reference selected a candidate outside the packet")
                return selection
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"cross-reference candidate selection failed: {last_error}")

    def select_focused_candidate(
        self,
        task: str,
        packet: MemoryPacket,
    ) -> FocusedMemoryCandidateSelection:
        if not packet.items:
            raise ValueError("focused recall requires at least one research candidate")
        schema = FocusedMemoryCandidateSelection.model_json_schema()
        last_error: Exception | None = None
        user = task + _format_memory_packet(packet)
        for token_cap in _retry_token_caps(24):
            try:
                content = self._structured(
                    "FOCUSED_RECALL_CANDIDATE",
                    _FOCUSED_RECALL_SELECTION_PROMPT,
                    user,
                    schema,
                    token_cap,
                )
                selection = FocusedMemoryCandidateSelection.model_validate_json(content)
                if selection.candidate_index >= len(packet.items):
                    raise ValueError("focused recall selected a candidate outside the packet")
                return selection
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"focused-recall candidate selection failed: {last_error}")
