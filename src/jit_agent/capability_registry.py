"""Deterministic, task-neutral discovery of installed executable capabilities.

The registry is runtime configuration, not autobiographical memory. Durable
tasks ask what functionality is available; application policy returns only a
bounded set of relevant public descriptors. Private routing terms and executor
bindings never enter model context or the persisted public packet.

The v0.7 live model path resolves a constrained capability enum to an exact
capability id before calling this registry. Lexical discovery remains available
for generic non-model callers, but default registrations intentionally avoid an
ever-growing natural-language continuity phrase catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Literal
from uuid import UUID, uuid5

import psycopg
from pydantic import BaseModel, Field, field_validator, model_validator

from jit_agent import event_store
from jit_agent.models import EventType


CAPABILITY_REGISTRY_VERSION = "v0.7-capability-registry-v1"
SOURCE = "capability_registry"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class CapabilityKind(str, Enum):
    """Agent-neutral kinds exposed by the installed capability surface."""

    SERVICE = "SERVICE"
    TOOL = "TOOL"
    MODEL = "MODEL"
    WORKFLOW = "WORKFLOW"


class CapabilityDescriptor(BaseModel):
    """Small public descriptor safe to reveal after a relevant match."""

    capability_id: str = Field(min_length=1)
    kind: CapabilityKind
    description: str = Field(min_length=1)

    @field_validator("capability_id", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("capability descriptor text must not be empty")
        return normalized


class CapabilityNeed(BaseModel):
    """Functionality requested by a durable task/step.

    ``query_text`` is application-owned. The live model path supplies an exact
    capability id; generic callers may still use lexical discovery and bounded
    supplemental queries.
    """

    query_text: str = Field(min_length=1)
    supplemental_query_texts: list[str] = Field(default_factory=list, max_length=3)
    kinds: list[CapabilityKind] | None = None
    exclude_capability_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=3, ge=1, le=10)

    @field_validator("query_text")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("capability query_text must not be empty")
        return normalized

    @field_validator("supplemental_query_texts", "exclude_capability_ids")
    @classmethod
    def normalize_lists(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("capability need lists must not contain empty values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("capability need lists must not contain duplicates")
        return normalized


class CapabilityMatch(BaseModel):
    descriptor: CapabilityDescriptor
    score: float = Field(gt=0)


class CapabilityPacket(BaseModel):
    """Bounded, auditable capability-discovery result for one worker step."""

    registry_version: str = CAPABILITY_REGISTRY_VERSION
    capability_request_id: UUID
    requester_task_id: UUID
    requester_step_id: UUID
    need: CapabilityNeed
    matches: list[CapabilityMatch]
    selected_query_role: Literal["canonical", "supplemental"] | None = None
    selected_query_text: str | None = None

    @model_validator(mode="after")
    def validate_packet(self) -> "CapabilityPacket":
        if self.registry_version != CAPABILITY_REGISTRY_VERSION:
            raise ValueError("capability registry version is unsupported")
        expected = deterministic_capability_request_id(self.requester_step_id)
        if self.capability_request_id != expected:
            raise ValueError("capability request id is not deterministic")
        if bool(self.matches) != (self.selected_query_role is not None):
            raise ValueError("capability selection metadata does not match the result")
        if (self.selected_query_role is None) != (self.selected_query_text is None):
            raise ValueError("capability selection role and text must appear together")
        if len(self.matches) > self.need.limit:
            raise ValueError("capability packet exceeds the requested bound")
        return self


@dataclass(frozen=True)
class RegisteredCapability:
    """Private application-owned registration and executable binding."""

    descriptor: CapabilityDescriptor
    routing_terms: tuple[str, ...]
    executor: str

    def __post_init__(self) -> None:
        normalized_executor = self.executor.strip()
        normalized_terms = tuple(term.strip() for term in self.routing_terms)
        if not normalized_executor:
            raise ValueError("capability executor must not be empty")
        if not normalized_terms or any(not term for term in normalized_terms):
            raise ValueError("capability routing terms must not be empty")
        if len(normalized_terms) != len(set(normalized_terms)):
            raise ValueError("capability routing terms must not contain duplicates")
        object.__setattr__(self, "executor", normalized_executor)
        object.__setattr__(self, "routing_terms", normalized_terms)


class CapabilityRegistry:
    """Deterministic registry with progressive disclosure and abstention."""

    def __init__(self, registrations: tuple[RegisteredCapability, ...] = ()) -> None:
        self._registrations: dict[str, RegisteredCapability] = {}
        for registration in registrations:
            self.register(registration)

    def register(self, registration: RegisteredCapability) -> None:
        capability_id = registration.descriptor.capability_id
        if capability_id in self._registrations:
            raise ValueError(f"capability id already registered: {capability_id}")
        self._registrations[capability_id] = registration

    def unregister(self, capability_id: str) -> RegisteredCapability:
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
            self._registrations[key].descriptor.model_copy(deep=True)
            for key in sorted(self._registrations)
        )

    def discover(self, need: CapabilityNeed) -> list[CapabilityMatch]:
        matches, _role, _text = self.discover_with_trace(need)
        return matches

    def discover_with_trace(
        self,
        need: CapabilityNeed,
    ) -> tuple[list[CapabilityMatch], Literal["canonical", "supplemental"] | None, str | None]:
        matches = self._discover_query(need, need.query_text)
        if matches:
            return matches, "canonical", need.query_text
        for supplemental in need.supplemental_query_texts:
            matches = self._discover_query(need, supplemental)
            if matches:
                return matches, "supplemental", supplemental
        return [], None, None

    def _discover_query(
        self,
        need: CapabilityNeed,
        query_text: str,
    ) -> list[CapabilityMatch]:
        allowed_kinds = set(need.kinds) if need.kinds else None
        excluded = set(need.exclude_capability_ids)
        query_tokens = _tokens(query_text)
        query_token_set = set(query_tokens)
        matches: list[CapabilityMatch] = []

        for capability_id in sorted(self._registrations):
            registration = self._registrations[capability_id]
            descriptor = registration.descriptor
            if capability_id in excluded:
                continue
            if allowed_kinds is not None and descriptor.kind not in allowed_kinds:
                continue

            score = 0.0
            id_tokens = _tokens(capability_id.replace("_", " "))
            if _contains_phrase(query_tokens, id_tokens):
                score += 8.0

            for raw_term in registration.routing_terms:
                term_tokens = _tokens(raw_term)
                if _contains_phrase(query_tokens, term_tokens):
                    score += 3.0 + (0.25 * len(term_tokens))
                elif len(term_tokens) > 1 and set(term_tokens).issubset(query_token_set):
                    score += 1.5 + (0.15 * len(term_tokens))

            if score > 0:
                matches.append(
                    CapabilityMatch(
                        descriptor=descriptor.model_copy(deep=True),
                        score=round(score, 6),
                    )
                )

        matches.sort(key=lambda item: (-item.score, item.descriptor.capability_id))
        return matches[: need.limit]


DEFAULT_REGISTRY = CapabilityRegistry(
    (
        RegisteredCapability(
            descriptor=CapabilityDescriptor(
                capability_id="internal_memory",
                kind=CapabilityKind.SERVICE,
                description="Retrieve bounded persisted internal evidence with exact provenance.",
            ),
            routing_terms=("internal memory",),
            executor="jit_memory",
        ),
        RegisteredCapability(
            descriptor=CapabilityDescriptor(
                capability_id="memory_analysis",
                kind=CapabilityKind.WORKFLOW,
                description=(
                    "Analyze, compare, or reconcile bounded persisted evidence in a fresh model call."
                ),
            ),
            routing_terms=("memory analysis",),
            executor="memory_analysis",
        ),
    )
)


def deterministic_capability_request_id(requester_step_id: UUID) -> UUID:
    return uuid5(requester_step_id, "capability-request")


def deterministic_capability_event_id(request_id: UUID, role: str) -> UUID:
    return uuid5(request_id, f"event:{role}")


def request_capability(
    conn: psycopg.Connection,
    *,
    conversation_id: UUID,
    correlation_id: UUID,
    requester_task_id: UUID,
    requester_step_id: UUID,
    need: CapabilityNeed,
    registry: CapabilityRegistry = DEFAULT_REGISTRY,
) -> CapabilityPacket:
    """Persist one deterministic lookup and return its bounded public packet."""

    request_id = deterministic_capability_request_id(requester_step_id)
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.CAPABILITY_REQUEST,
        source=SOURCE,
        payload={
            "registry_version": CAPABILITY_REGISTRY_VERSION,
            "capability_request_id": str(request_id),
            "requester_task_id": str(requester_task_id),
            "requester_step_id": str(requester_step_id),
            "need": need.model_dump(mode="json"),
        },
        payload_text=need.query_text,
        event_id=deterministic_capability_event_id(request_id, "request"),
    )
    matches, role, selected_text = registry.discover_with_trace(need)
    packet = CapabilityPacket(
        capability_request_id=request_id,
        requester_task_id=requester_task_id,
        requester_step_id=requester_step_id,
        need=need,
        matches=matches,
        selected_query_role=role,
        selected_query_text=selected_text,
    )
    event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        event_type=EventType.CAPABILITY_PACKET,
        source=SOURCE,
        payload={"packet": packet.model_dump(mode="json")},
        event_id=deterministic_capability_event_id(request_id, "packet"),
    )
    return packet


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(value.casefold()))


def _contains_phrase(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    width = len(needle)
    return any(
        haystack[index : index + width] == needle
        for index in range(len(haystack) - width + 1)
    )