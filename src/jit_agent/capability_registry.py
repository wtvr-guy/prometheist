"""Deterministic just-in-time discovery of currently installed capabilities.

The registry is current system configuration, not autobiographical memory. Agents
state what functionality they need through ``CapabilityNeed``; deterministic
application code returns a bounded ``CapabilityPacket`` containing only relevant
registered capabilities. No LLM is required to remember or enumerate the MAS.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import uuid

import psycopg

from jit_agent import event_store
from jit_agent.models import (
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityMatch,
    CapabilityNeed,
    CapabilityPacket,
    EventType,
)

SOURCE = "capability_registry"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class RegisteredCapability:
    """Internal registration metadata never dumped wholesale into an LLM prompt."""

    descriptor: CapabilityDescriptor
    routing_terms: tuple[str, ...]
    specialist_instruction: str
    executor: str = "memory_grounded_specialist"


class CapabilityRegistry:
    """Deterministic registry with bounded discovery and explicit extension points."""

    def __init__(
        self,
        registrations: tuple[RegisteredCapability, ...] = (),
    ) -> None:
        self._registrations: dict[str, RegisteredCapability] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: RegisteredCapability) -> None:
        """Install one capability; duplicate ids are rejected deterministically."""
        capability_id = registration.descriptor.capability_id
        if capability_id in self._registrations:
            raise ValueError(f"capability id already registered: {capability_id}")
        self._registrations[capability_id] = registration

    def unregister(self, capability_id: str) -> RegisteredCapability:
        """Remove one capability from current runtime configuration."""
        try:
            return self._registrations.pop(capability_id)
        except KeyError as exc:
            raise KeyError(f"Unknown capability_id: {capability_id}") from exc

    def get(self, capability_id: str) -> RegisteredCapability:
        try:
            return self._registrations[capability_id]
        except KeyError as exc:
            raise KeyError(f"Unknown capability_id: {capability_id}") from exc

    def descriptors(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(
            self._registrations[key].descriptor
            for key in sorted(self._registrations)
        )

    def discover(self, need: CapabilityNeed) -> list[CapabilityMatch]:
        allowed_kinds = set(need.kinds) if need.kinds else None
        query_tokens = _tokens(need.query_text)
        query_token_set = set(query_tokens)
        matches: list[CapabilityMatch] = []

        for registration in self._registrations.values():
            descriptor = registration.descriptor
            if allowed_kinds is not None and descriptor.kind not in allowed_kinds:
                continue

            score = 0.0
            matched_terms: list[str] = []

            capability_id_tokens = _tokens(descriptor.capability_id.replace("_", " "))
            if _contains_phrase(query_tokens, capability_id_tokens):
                score += 8.0
                matched_terms.append(descriptor.capability_id)

            for raw_term in registration.routing_terms:
                term_tokens = _tokens(raw_term)
                if not term_tokens:
                    continue
                if _contains_phrase(query_tokens, term_tokens):
                    score += 3.0 + (0.25 * len(term_tokens))
                    matched_terms.append(raw_term)
                elif set(term_tokens).issubset(query_token_set):
                    # Multi-token cues may still be useful when words are split by
                    # modifiers, but exact contiguous phrases rank higher.
                    score += 1.5 + (0.15 * len(term_tokens))
                    matched_terms.append(raw_term)

            if score <= 0:
                continue

            matches.append(
                CapabilityMatch(
                    descriptor=descriptor,
                    score=round(score, 6),
                    matched_terms=sorted(set(matched_terms)),
                )
            )

        matches.sort(key=lambda item: (-item.score, item.descriptor.capability_id))
        return matches[: need.limit]


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(value.casefold()))


def _contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


DEFAULT_REGISTRY = CapabilityRegistry(
    (
        RegisteredCapability(
            descriptor=CapabilityDescriptor(
                capability_id="memory_specialist",
                kind=CapabilityKind.AGENT,
                description=(
                    "Recall, summarize, and synthesize persisted internal history "
                    "with exact supporting evidence."
                ),
            ),
            routing_terms=(
                "memory",
                "remember",
                "recall",
                "history",
                "historical",
                "prior",
                "earlier",
                "original",
                "previously",
                "past",
                "codename",
                "launch code",
            ),
            specialist_instruction=(
                "Recall and synthesize persisted internal history. Preserve exact "
                "facts and distinguish unsupported claims from evidence."
            ),
        ),
        RegisteredCapability(
            descriptor=CapabilityDescriptor(
                capability_id="planning_specialist",
                kind=CapabilityKind.AGENT,
                description=(
                    "Develop plans, sequences, recommendations, and next steps "
                    "subject to persisted requirements and preferences."
                ),
            ),
            routing_terms=(
                "plan",
                "planning",
                "roadmap",
                "approach",
                "steps",
                "strategy",
                "schedule",
                "propose",
                "recommend",
                "deployment",
                "next step",
            ),
            specialist_instruction=(
                "Produce a concrete plan or recommendation constrained by the "
                "retrieved requirements, preferences, and prior decisions."
            ),
        ),
        RegisteredCapability(
            descriptor=CapabilityDescriptor(
                capability_id="analysis_specialist",
                kind=CapabilityKind.AGENT,
                description=(
                    "Compare, evaluate, reconcile, and explain changes or "
                    "relationships across persisted evidence."
                ),
            ),
            routing_terms=(
                "analyze",
                "analysis",
                "compare",
                "comparison",
                "change",
                "changed",
                "difference",
                "evaluate",
                "reconcile",
                "implication",
                "relationship",
            ),
            specialist_instruction=(
                "Analyze and compare the retrieved evidence. Explain supported "
                "differences, changes, or implications without inventing facts."
            ),
        ),
    )
)


def request_capability(
    conn: psycopg.Connection,
    *,
    conversation_id: uuid.UUID,
    correlation_id: uuid.UUID,
    requesting_agent: str,
    need: CapabilityNeed,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> CapabilityPacket:
    """Persist one deterministic capability lookup and return bounded matches."""
    capability_request_id = uuid.uuid4()
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.CAPABILITY_REQUEST,
        source=requesting_agent,
        payload={
            "capability_request_id": str(capability_request_id),
            "need": need.model_dump(mode="json"),
        },
        payload_text=need.query_text,
    )

    packet = CapabilityPacket(
        capability_request_id=capability_request_id,
        need=need,
        matches=registry.discover(need),
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.CAPABILITY_PACKET,
        source=SOURCE,
        payload={
            "requesting_agent": requesting_agent,
            "packet": packet.model_dump(mode="json"),
        },
    )
    return packet
