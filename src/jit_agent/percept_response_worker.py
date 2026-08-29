"""Fresh-process entry point for one v2 user-prompt response worker step.

Explicit user prompts have a deterministic response contract: Prometheist always
responds. The pre-cognitive LLM therefore selects only required non-memory work;
it never decides whether the user deserves a response.
"""
from __future__ import annotations

import os
import sys
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jit_agent import db
from jit_agent.capability_registry import CapabilityDescriptor
from jit_agent.models import MemoryPacket
from jit_agent.percept_response_runtime import (
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


class UserPromptLLM(PerceptLLM):
    """Percept LLM whose response requirement is fixed by interactive intake."""

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
