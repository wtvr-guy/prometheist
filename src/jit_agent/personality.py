"""Application-owned persona prompt supplied only to user-facing response workers.

A Prometheist worker is not inherently an LLM role and does not inherently have a
persona. Deterministic workers are governed entirely by code. LLM-powered workers
receive narrow role-specific system instructions for their one bounded job. Only
workers that generate user-facing responses additionally receive this persona
prompt.

Persona is response-surface authority, not historical evidence and not cognitive
control. It therefore must never be reconstructed implicitly from retrieved
memory or capability output. A future personalization subsystem may derive a
versioned user model from durable application state, but every generative final
responder must still receive one explicit, non-empty persona prompt for the
invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os


DEFAULT_PERSONALITY_PROMPT_VERSION = "prometheist-response-persona-v2"
DEFAULT_PERSONALITY_PROMPT = """\
You are Prometheist's user-facing voice. Respond as the user's modeled digital
counterpart rather than as an internal worker, tool, or detached system narrator.
Use only the user-specific communication style, tone, priorities, preferences,
and personality traits that the application explicitly provides in this persona
prompt. If no learned user-specific trait is provided, use a neutral, precise,
context-appropriate style rather than inventing one.

This persona governs only how an already-authorized answer is expressed. It does
not establish biographical facts, preferences, beliefs, experiences, or external
facts; it does not expand the evidence set; and it does not change source
admissibility, capability policy, or the already-final respond/abstain decision.
"""


@dataclass(frozen=True, slots=True)
class PersonalityPrompt:
    version: str
    text: str
    sha256: str


def configured_personality_prompt() -> PersonalityPrompt:
    """Return the mandatory application-owned user-facing response persona."""

    configured_text = os.environ.get("PROMETHEIST_PERSONALITY_PROMPT", "").strip()
    text = configured_text or DEFAULT_PERSONALITY_PROMPT.strip()
    if not text:
        raise RuntimeError("final response personality prompt must not be empty")

    configured_version = os.environ.get("PROMETHEIST_PERSONALITY_PROMPT_VERSION", "").strip()
    version = configured_version or DEFAULT_PERSONALITY_PROMPT_VERSION
    if not version:
        raise RuntimeError("final response personality prompt version must not be empty")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return PersonalityPrompt(version=version, text=text, sha256=digest)
