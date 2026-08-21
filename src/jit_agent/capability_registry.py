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
    """Small deterministic registry with bounded lexical capability discovery."""

    def __init__(self, registrations: tuple[RegisteredCapability, ...]) -> None:
        ids = [item.descriptor.capability_id for item in registrations]
        if len(ids) != len(set(ids)):
            raise ValueError("capability ids must be unique")
        self._registrations = {
            item.descriptor.capability_id: item for item in registrations
        }

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
        query_norm = _normalize(need.query_text)
        query_tokens = set(_tokens(need.query_text))
        matches: list[CapabilityMatch] = []

        for registration in self._registrations.values():
            descriptor = registration.descriptor
            if allowed_kinds is not None and descriptor.kind not in allowed_kinds:
                continue

            score = 0.0
            matched_terms: list[str] = []

            capability_id_text = descriptor.capability_id.replace("_", " ")
            if _normalize(capability_id_text) in query_norm:
                score += 8.0
                matched_terms.append(descriptor.capability_id)

            for raw_term in registration.routing_terms:
                term_norm = _normalize(raw_term)
                term_tokens = set(_tokens(raw_term))
                if not term_tokens:
                    continue
                if term_norm and term_norm in query_norm:
                    score += 3.0 + (0.25 * len(term_tokens))
                    matched_terms.append(raw_term)
                elif term_tokens.issubset(query_tokens):
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


def _normalize(value: str) -> str:
    return " ".join(_tokens(value))


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(value.casefold()))


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
