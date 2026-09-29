"""Versioned mobile evidence contracts; no model or database dependency."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROTOCOL = "prometheist-node/v1"
# Safety tunables, not measured Galaxy A16 capacity. See docs/android-node.md.
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_EVENT_BYTES = 768 * 1024
PAGE_SIZE = 32
PAIR_LIFETIME_SECONDS = 600


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeEvent(WireModel):
    protocol: Literal["prometheist-node/v1"] = PROTOCOL
    event_id: UUID
    node_id: UUID
    sequence: int = Field(ge=1, le=2**53 - 1)
    observed_at: datetime
    kind: Literal["note", "chat", "sensors", "location", "device", "photo", "audio", "control"]
    # The exact UTF-8 JSON string is canonical. Never round-trip it through a
    # language-specific floating point serializer when computing its digest.
    data_json: str = Field(min_length=2, max_length=MAX_EVENT_BYTES)

    @field_validator("observed_at")
    @classmethod
    def aware_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError("observed_at requires a timezone")
        return value

    @field_validator("data_json")
    @classmethod
    def bounded_json(cls, value):
        if len(value.encode("utf-8")) > MAX_EVENT_BYTES:
            raise ValueError("evidence exceeds the mobile bound")

        def invalid(_):
            raise ValueError("nonfinite JSON number")

        try:
            data = json.loads(value, parse_constant=invalid)
        except (RecursionError, json.JSONDecodeError) as exc:
            raise ValueError("invalid evidence JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("evidence must be a JSON object")
        return value

    def canonical(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


class PairRequest(WireModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    node_id: UUID
    credential: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    label: str = Field(min_length=1, max_length=80)


class SyncRequest(WireModel):
    protocol: Literal["prometheist-node/v1"] = PROTOCOL
    node_id: UUID
    subject_id: str
    epoch: str = ""
    after: int = Field(default=0, ge=0, le=2**53 - 1)
    events: list[NodeEvent] = Field(default_factory=list, max_length=PAGE_SIZE)


def https_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("Use an HTTPS origin without a path, query, or credentials")
    _ = parsed.port
    return value.rstrip("/")
