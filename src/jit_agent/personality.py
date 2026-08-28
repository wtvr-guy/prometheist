"""Application-owned personality prompt supplied to every generative final responder.

Personality is response-surface authority, not historical evidence. It therefore
must never be reconstructed from retrieved memory or capability output. A future
personalization subsystem may derive a versioned prompt from durable application
state, but the final responder must still receive one explicit, non-empty prompt
for every invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os


DEFAULT_PERSONALITY_PROMPT_VERSION = "prometheist-personality-v1"
DEFAULT_PERSONALITY_PROMPT = """\
You are Prometheist's final response voice. Express the already-finalized answer
in a precise, direct, context-appropriate conversational style. Preserve the
user's explicit tone, formatting, brevity, and wording requirements when they do
not conflict with higher-authority system constraints. Do not invent facts,
expand the evidence set, change source admissibility, initiate additional work,
or reconsider whether a response should be produced. The pre-cognitive system
has already made those decisions. Your job is language and persona realization
only.
"""


@dataclass(frozen=True, slots=True)
class PersonalityPrompt:
    version: str
    text: str
    sha256: str


def configured_personality_prompt() -> PersonalityPrompt:
    """Return the mandatory application-owned final-response personality prompt."""

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
