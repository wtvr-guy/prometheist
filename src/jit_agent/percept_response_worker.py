"""Fresh-process entry point for one v2 user-prompt response worker step.

Explicit user prompts have a deterministic response contract: Prometheist always
responds. The pre-cognitive LLM therefore selects only required non-memory work;
it never decides whether the user deserves a response.

Interactive workers also carry two system-level contracts that must not depend on
episodic recall: the disposable model invocation is a cognitive component of
Prometheist rather than the identity of the overall system, and information
supplied in the current user prompt is direct current evidence that does not need
historical-memory corroboration before it can be acknowledged or followed.
"""
from __future__ import annotations

import json
import os
import sys
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jit_agent import db
from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.models import MemoryPacket
from jit_agent.percept_response_runtime import (
    MemorySufficiencyDecision,
    PerceptLLM,
    PreCognitiveDisposition,
    execute_claimed_percept_step,
)


_USER_PROMPT_WORK_SELECTION = """\
You are a fresh disposable Prometheist pre-cognitive worker. You have no inherited
transcript or model state. This input is an explicit user prompt, and Prometheist
will respond to it unconditionally. Your only decision is which executable
non-memory capabilities, if any, must run before the final response.

Return only capability_indices. Capability indices are requirements, never
execution order. Prometheist owns dependencies, scheduling, permissions,
resources, retries, and effects. Do not decide whether to respond. Do not write
capability names, arguments, queries, explanations, schedules, or user-facing
language.
"""

_USER_PROMPT_COMPOSER = """\
You are the Prometheist v2 Composer, a fresh stateless memory-sufficiency worker.
Your only job is to determine whether historical/persistent-memory evidence is
sufficient for a separate final responder to answer the current user prompt
accurately.

The current user prompt is itself direct current evidence. Do NOT require a fact,
definition, preference, correction, instruction, or newly introduced piece of
information from the current prompt to already exist in historical memory. If the
responder can answer accurately from the current prompt plus general model
knowledge, return sufficient=true even when persistent memory is empty.

Return sufficient=false only when answering genuinely depends on prior system
history or remembered user-specific information that is not established by the
current prompt and is missing from the supplied persistent-memory evidence. In
that case, memory_deficit must identify only the missing remembered information.

Do not decide whether Prometheist should respond; direct user prompts already
require a response. Do not consume, summarize, reinterpret, or request tool/action
results. Do not write the user-facing answer. Adaptive Recall owns retrieval
mechanics. A legitimate historical unknown is acceptable; never invent memory.
"""

_INTERACTIVE_PERSONALITY_PROMPT = """\
You are Prometheist, the persistent cognitive system the user is interacting with.
Do not describe yourself as merely a language model. A language model is a fresh,
disposable semantic worker used by Prometheist; it is not Prometheist's identity
or continuity.

Prometheist is a locally hosted, stateless cognitive architecture. Durable
identity, memory, working state, attention, tasks, provenance, and policy belong
to Prometheist's deterministic system rather than to any model context. Past
experience is supplied to fresh model workers through bounded just-in-time memory
retrieval.

Treat the current user prompt as direct current evidence. Facts, definitions,
preferences, corrections, and instructions supplied now do not need to have
appeared in older persistent memory before you can acknowledge or follow them. A
historical-memory deficit matters only when the answer genuinely depends on prior
events that are not established by the current prompt or supplied memory.

Be precise, direct, context-aware, and useful. Treat supplied persistent memory as
evidence with provenance rather than unquestionable truth. Honor explicit user
constraints. Do not invent personal or history-specific facts absent from both the
current prompt and supplied memory. Do not expose internal retrieval mechanics
unless the user asks about them.
"""


class UserPromptWorkSelection(BaseModel):
    """The only model-authored pre-cognitive control output for a user prompt."""

    model_config = ConfigDict(extra="forbid")
    capability_indices: list[int] = Field(default_factory=list)

    @field_validator("capability_indices")
    @classmethod
    def validate_indices(cls, values: list[int]) -> list[int]:
        if any(index < 0 for index in values):
            raise ValueError("capability_indices must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("capability_indices must not contain duplicates")
        return values


def _normalize_memory_sufficiency_content(content: str) -> str:
    """Normalize semantically empty optional fields from constrained small models."""

    payload = json.loads(content)
    if not isinstance(payload, dict):
        return content
    deficit = payload.get("memory_deficit")
    if isinstance(deficit, str):
        normalized = deficit.strip()
        payload["memory_deficit"] = normalized or None
    return json.dumps(payload, separators=(",", ":"))


class UserPromptLLM(PerceptLLM):
    """Percept LLM with deterministic response and current-evidence contracts."""

    def decide_disposition(
        self,
        percept: str,
        memory_packet: MemoryPacket,
        capability_catalog: tuple[CapabilityDescriptor, ...],
    ) -> PreCognitiveDisposition:
        catalog_text = "\n".join(
            f"{index}: {item.capability_id} | {item.kind.value} | {item.description}"
            for index, item in enumerate(capability_catalog)
        ) or "none"
        memory_text = "\n".join(
            f"item {index}: {item.event_type.value}: {item.content}"
            for index, item in enumerate(memory_packet.items)
        ) or "none"
        user = (
            f"[Current user prompt]\n{percept}\n\n"
            f"[Bounded orientation memory]\n{memory_text}\n\n"
            f"[Executable capability catalog]\n{catalog_text}"
        )
        last_error: ValueError | None = None
        for token_cap in (48, 96):
            try:
                content = self._structured(
                    "PRECOGNITIVE_USER_PROMPT_WORK",
                    _USER_PROMPT_WORK_SELECTION,
                    user,
                    UserPromptWorkSelection.model_json_schema(),
                    token_cap,
                )
                selection = UserPromptWorkSelection.model_validate_json(content)
                if any(index >= len(capability_catalog) for index in selection.capability_indices):
                    raise ValueError("pre-cognitive worker selected an unavailable capability")
                return PreCognitiveDisposition(
                    response_required=True,
                    capability_indices=selection.capability_indices,
                )
            except ValueError as exc:
                last_error = exc
        raise ValueError(f"pre-cognitive work selection failed to validate: {last_error}")

    def assess_memory_sufficiency(
        self,
        percept: str,
        memory_packet: MemoryPacket,
    ) -> MemorySufficiencyDecision:
        memory_text = "\n".join(
            f"item {index}: {item.event_type.value}: {item.content}"
            for index, item in enumerate(memory_packet.items)
        ) or "none"
        user = f"[Current user prompt]\n{percept}\n\n[Persistent memory evidence]\n{memory_text}"
        last_error: ValueError | None = None
        for token_cap in (96, 192):
            try:
                content = self._structured(
                    "V2_MEMORY_SUFFICIENCY_USER_PROMPT",
                    _USER_PROMPT_COMPOSER,
                    user,
                    MemorySufficiencyDecision.model_json_schema(),
                    token_cap,
                )
                normalized = _normalize_memory_sufficiency_content(content)
                return MemorySufficiencyDecision.model_validate_json(normalized)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        raise ValueError(f"v2 Composer decision failed to validate: {last_error}")


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing guarded worker environment value: {name}")
    return value


def main() -> None:
    _configure_utf8_streams()
    os.environ.setdefault("PROMETHEIST_PERSONALITY_PROMPT", _INTERACTIVE_PERSONALITY_PROMPT)
    claim_id = UUID(_required_environment("PROMETHEIST_WORKER_CLAIM_ID"))
    worker_id = _required_environment("PROMETHEIST_WORKER_ID")
    scheduler_key = _required_environment("PROMETHEIST_WORKER_SCHEDULER_KEY")
    with db.get_connection() as conn:
        execute_claimed_percept_step(
            conn,
            UserPromptLLM(),
            claim_id=claim_id,
            worker_id=worker_id,
            scheduler_key=scheduler_key,
        )


if __name__ == "__main__":
    main()
