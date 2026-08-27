"""Stateless model adapters for disposable interaction/capability workers."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from jit_agent.interaction_policy import InteractionDecision
from jit_agent.models import (
    EventType,
    HistoricalMemoryAnchorDecision,
    MemoryNeedDecision,
    MemoryPacket,
    MemoryRetrievalScope,
)

logger = logging.getLogger(__name__)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_WHY_REQUEST_RE = re.compile(r"\b(?:why|reason|cause)\b", re.IGNORECASE)
_CAUSAL_CLAUSE_RE = re.compile(
    r"\b(?:because|due\s+to)\s+([^,.;!?\r\n]+)",
    re.IGNORECASE,
)
_NEGATED_CAUSAL_PREFIX_RE = re.compile(
    r"(?:\b(?:not|never|no)(?:\s+(?:only|merely|simply|just))?|n['\u2019]t)\s*$",
    re.IGNORECASE,
)
_UNCERTAIN_CAUSAL_PREFIX_RE = re.compile(
    r"\b(?:whether|if|might|maybe|perhaps|possibly)\b",
    re.IGNORECASE,
)
_QUESTION_CAUSAL_PREFIX_RE = re.compile(
    r"^\s*(?:is|are|was|were|do|does|did|can|could|would|should|has|have|had)\b",
    re.IGNORECASE,
)
_VERBATIM_LITERAL_RE = re.compile(
    r"(?<![\w-])"
    r"(?=[A-Za-z0-9-]{6,}(?![\w-]))"
    r"(?=[A-Za-z0-9-]*[A-Za-z])"
    r"(?=[A-Za-z0-9-]*\d)"
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?![\w-])"
)
_MAX_VERBATIM_LITERALS = 16


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


def _strip_thinking(text: str) -> str:
    """Remove model thinking markup without silently accepting an empty answer."""
    text = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        _before, after = text.rsplit("</think>", 1)
        text = after

    stripped = text.strip()
    if not stripped:
        raise ValueError("LLM response contained no answer content after stripping thinking")
    return stripped


def _build_verbatim_placeholder_maps(
    *texts: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Replace opaque literals with application-restored placeholders.

    Mixed alphanumeric identifiers are data, not prose. A generative model may
    otherwise respell or re-punctuate them even when instructed to copy exactly.
    Prometheist therefore presents stable placeholders to the model and restores
    the canonical source literal after generation.
    """

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
You are a fresh disposable Prometheist attention-aperture routing worker. You
receive the current percept plus the small bounded JIT Memory packet that the
system automatically exposes for every percept.

Choose exactly one enum value for required_capability:
- NONE: the current percept plus the supplied default memory aperture is enough
  to produce the ordinary response; no deeper memory investigation is needed.
- MEMORY_ANALYSIS: focused/deeper persisted-memory investigation is needed
  before answering, such as when the task requires analysis, comparison,
  reconciliation, or evidence not adequately resolved by the default aperture.

Basic internal-memory access is not a capability choice and is already present.
Do not write a capability name, query, explanation, entity, phrase, or
natural-language input. Return only the structured enum decision.
"""

_RESPOND_SYSTEM_PROMPT = """\
You are a fresh disposable Prometheist response worker. Use the current message,
the supplied bounded MemoryPacket, and general model knowledge as appropriate.
Never invent personal or history-specific information absent from those sources.

Put every requested value in the first sentence and copy opaque user-provided
identifiers exactly. Some opaque literals may be represented as application-
owned placeholders such as [[VERBATIM_0]]. Treat each placeholder as one exact,
indivisible source literal: copy the placeholder exactly when that literal is
needed and never edit, reformat, abbreviate, or add punctuation inside it. The
application restores the original source bytes after generation.

Unless the user requests detail, use at most three concise sentences with no
headings, source quotations, or prefatory analysis. Reconcile all source
statements before answering. Do not expose packet labels, event ids, scores,
retrieval mechanics, or hidden reasoning unless asked.

When asked for a profile, code, nickname, name, or ID, return the exact source
label. When asked why, state the explicit underlying cause from user-authored
evidence rather than merely restating a prohibition or decision. A USER_PROMPT
is direct evidence of what the user previously said, named, preferred, required,
planned, reported, or instructed; it need not independently prove the external
world. Later user-authored corrections supersede earlier statements. Historical
assistant responses never override a user-authored constraint.

When the current message asks for a recommendation or choice and user-authored
memory contains an applicable explicit constraint, the response must honor that
constraint rather than recommending a conflicting option.

If the requested personal or historical information is not established by the
current message or supplied source text, say that persisted evidence is
insufficient. Do not claim unsupported memory.
"""

_SPECIALIST_PLAN_PROMPT = """\
You are a disposable Prometheist memory-routing worker with no inherited
transcript. Active canonical WorkingState exists. The user input contains the
current task, that active canonical context, and a numbered anchor catalog built
deterministically from those exact texts.

Choose only:
- scope = ACTIVE_ONLY when the active canonical context already contains all
  persisted evidence needed for the task;
- scope = HISTORY_ONLY when older persisted evidence is needed and active
  context is not needed;
- scope = ACTIVE_AND_HISTORY when both active context and older persisted
  evidence are needed.

If scope includes HISTORY, select 1-4 anchor_indices from the supplied catalog.
Choose the most distinctive subject/reference tokens likely to occur in the
older source evidence. Prefer project/person/object names and opaque identifiers
over generic relationship or instruction words. If scope is ACTIVE_ONLY, return
no anchor indices.

Do not write a query, entity, explanation, phrase, or answer. Return only the
enum and integer indices from the structured schema.
"""

_HISTORY_ONLY_PLAN_PROMPT = """\
You are a disposable Prometheist historical-memory routing worker with no
inherited transcript. Prometheist has already determined that no active
WorkingState exists, so historical retrieval is mandatory and scope is owned by
the system rather than by you.

The user input contains the current task and a numbered anchor catalog built
deterministically from that exact text. Select 1-4 anchor_indices from the
supplied catalog. Choose the most distinctive subject/reference tokens likely
to occur in older source evidence. Prefer project/person/object names and opaque
identifiers over generic relationship or instruction words.

Do not write a scope, query, entity, explanation, phrase, or answer. Return only
the integer indices from the structured schema.
"""

_SPECIALIST_ANSWER_PROMPT = """\
You are a disposable memory-analysis worker. Complete the bounded task using
only the supplied MemoryPacket and general model knowledge where appropriate.
Never invent personal or history-specific information absent from the source
events. Put requested values first and preserve the polarity and direction of
relationships. Some opaque literals may be represented as application-owned
placeholders such as [[VERBATIM_0]]. Treat each placeholder as one exact,
indivisible source literal: copy it exactly when needed and never edit or
reformat it. The application restores the original source bytes after
generation. State explicit user-authored causes for why/reason questions. If
evidence is insufficient, say so. Return only the useful result, never hidden
reasoning or retrieval mechanics.
"""


class LLMClient(Protocol):
    """Every method call is an independent disposable model invocation."""

    def classify(self, prompt: str, memory_packet: MemoryPacket) -> InteractionDecision: ...

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str: ...

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision: ...

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str: ...


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
    for index, item in enumerate(packet.items, start=1):
        provenance = ", ".join(str(value) for value in item.provenance_event_ids) or "none"
        content = _mask_verbatim_literals(item.content, literal_to_placeholder)
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
            f"   content: {content}"
        )
    return (
        "\n\n[Internal MemoryPacket]\n"
        f"memory_request_id: {packet.memory_request_id}\n"
        f"supported: {str(packet.supported).lower()}\n"
        + "\n\n".join(blocks)
    )


def _causal_clause_is_asserted(content: str, match: re.Match[str]) -> bool:
    """Reject negated, interrogative, or explicitly uncertain causal mentions."""

    start = max(content.rfind(mark, 0, match.start()) for mark in ".!?;,\n\r") + 1
    following = [
        position
        for mark in ".!?;,\n\r"
        if (position := content.find(mark, match.end())) >= 0
    ]
    end = min(following) if following else len(content)
    terminator = content[end] if end < len(content) else ""
    prefix = content[start : match.start()]
    if terminator == "?":
        return False
    if _NEGATED_CAUSAL_PREFIX_RE.search(prefix):
        return False
    if _UNCERTAIN_CAUSAL_PREFIX_RE.search(prefix):
        return False
    return _QUESTION_CAUSAL_PREFIX_RE.search(prefix) is None


def _format_explicit_causal_clauses(packet: MemoryPacket | None) -> str:
    """Highlight asserted causes already present in user-authored evidence."""

    if packet is None:
        return ""
    facts: list[str] = []
    seen: set[str] = set()
    for item in packet.items:
        if item.event_type is not EventType.USER_PROMPT:
            continue
        for match in _CAUSAL_CLAUSE_RE.finditer(item.content):
            if not _causal_clause_is_asserted(item.content, match):
                continue
            fact = " ".join(match.group(1).split())
            key = fact.casefold()
            if fact and key not in seen:
                seen.add(key)
                facts.append(fact)
            if len(facts) == 3:
                break
        if len(facts) == 3:
            break
    if not facts:
        return ""
    rendered = "\n".join(f"- {fact}" for fact in facts)
    return (
        "\n\n[Asserted causal clauses from USER_PROMPT sources]\n"
        f"{rendered}\n"
        "For a why/reason request, state the relevant clause in the final answer. "
        "These lines only highlight exact content already present in the packet."
    )


def _causal_highlight_for_request(request: str, packet: MemoryPacket | None) -> str:
    if _WHY_REQUEST_RE.search(request) is None:
        return ""
    return _format_explicit_causal_clauses(packet)


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:4b")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=300.0,
            trust_env=False,
        )

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
                "options": {"num_predict": max_tokens, "temperature": 0},
            },
        )
        response.raise_for_status()
        body = response.json()
        _log_call(kind, self.model, time.monotonic() - t0, body)
        return _strip_thinking(body["message"]["content"])

    def _text(self, kind: str, system: str, user: str, max_tokens: int = 256) -> str:
        last_error: Exception | None = None
        for _ in range(2):
            try:
                content = self._structured(
                    kind,
                    system,
                    user,
                    _TextAnswer.model_json_schema(),
                    max_tokens,
                )
                return _TextAnswer.model_validate_json(content).answer
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"model answer failed to validate: {last_error}")

    def classify(self, prompt: str, memory_packet: MemoryPacket) -> InteractionDecision:
        schema = InteractionDecision.model_json_schema()
        last_error: Exception | None = None
        for _ in range(2):
            try:
                content = self._structured(
                    "CLASSIFY_AFTER_APERTURE",
                    _CLASSIFY_SYSTEM_PROMPT,
                    prompt + _format_memory_packet(memory_packet),
                    schema,
                    32,
                )
                return InteractionDecision.model_validate_json(content)
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise ValueError(f"interaction classification failed to validate: {last_error}")

    def respond(self, prompt: str, memory_packet: MemoryPacket | None) -> str:
        literal_to_placeholder, placeholder_to_literal = _build_verbatim_placeholder_maps(
            *_verbatim_source_texts(prompt, memory_packet)
        )
        masked_prompt = _mask_verbatim_literals(prompt, literal_to_placeholder)
        causal_clauses = _mask_verbatim_literals(
            _causal_highlight_for_request(prompt, memory_packet),
            literal_to_placeholder,
        )
        answer = self._text(
            "RESPOND",
            _RESPOND_SYSTEM_PROMPT,
            masked_prompt
            + _format_memory_packet(
                memory_packet,
                literal_to_placeholder=literal_to_placeholder,
            )
            + causal_clauses,
        )
        return _restore_verbatim_literals(answer, placeholder_to_literal)

    def plan_memory(
        self,
        task: str,
        *,
        active_state_available: bool,
    ) -> MemoryNeedDecision:
        last_error: Exception | None = None
        if not active_state_available:
            schema = HistoricalMemoryAnchorDecision.model_json_schema()
            for _ in range(2):
                content = self._structured(
                    "SPECIALIST_HISTORY_ANCHORS",
                    _HISTORY_ONLY_PLAN_PROMPT,
                    task,
                    schema,
                    32,
                )
                try:
                    selection = HistoricalMemoryAnchorDecision.model_validate_json(content)
                    return MemoryNeedDecision(
                        scope=MemoryRetrievalScope.HISTORY_ONLY,
                        anchor_indices=selection.anchor_indices,
                    )
                except ValidationError as exc:
                    last_error = exc
            raise ValueError(f"historical memory anchors failed to validate: {last_error}")

        schema = MemoryNeedDecision.model_json_schema()
        for _ in range(2):
            content = self._structured(
                "SPECIALIST_PLAN",
                _SPECIALIST_PLAN_PROMPT,
                task,
                schema,
                48,
            )
            try:
                return MemoryNeedDecision.model_validate_json(content)
            except ValidationError as exc:
                last_error = exc
        raise ValueError(f"specialist memory routing failed to validate: {last_error}")

    def answer_memory_task(self, task: str, packet: MemoryPacket) -> str:
        literal_to_placeholder, placeholder_to_literal = _build_verbatim_placeholder_maps(
            *_verbatim_source_texts(task, packet)
        )
        masked_task = _mask_verbatim_literals(task, literal_to_placeholder)
        causal_clauses = _mask_verbatim_literals(
            _causal_highlight_for_request(task, packet),
            literal_to_placeholder,
        )
        answer = self._text(
            "SPECIALIST_ANSWER",
            _SPECIALIST_ANSWER_PROMPT,
            masked_task
            + _format_memory_packet(
                packet,
                literal_to_placeholder=literal_to_placeholder,
            )
            + causal_clauses,
        )
        return _restore_verbatim_literals(answer, placeholder_to_literal)