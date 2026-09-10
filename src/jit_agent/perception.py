"""Deterministic percept normalization and salience assessment for v0.8."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

PERCEPTION_POLICY_VERSION = "v0.8-perception-v1"
SALIENCE_POLICY_VERSION = "v0.8-salience-v1"
_INPUT_BUFFER_SEGMENT_CHARS = 160
_INPUT_BUFFER_MAX_SEGMENTS = 4
_PERCEPT_NAMESPACE = UUID("d0b7d62c-47d4-5a0f-99d2-0cc58d7357d3")
_THREAT_TERMS = (
    "danger",
    "emergency",
    "immediately",
    "urgent",
    "attack",
    "breach",
    "unsafe",
)
_OPPORTUNITY_TERMS = (
    "improve",
    "opportunity",
    "optimize",
    "implement",
    "add",
    "plan",
    "upgrade",
)
_GOAL_TERMS = (
    "need",
    "please",
    "should",
    "want",
    "goal",
    "must",
)
_UNCERTAINTY_TERMS = (
    "maybe",
    "perhaps",
    "not sure",
    "unclear",
    "unknown",
    "guess",
    "uncertain",
)
_INTEGRITY_TERMS = (
    "error",
    "failed",
    "failure",
    "exception",
    "traceback",
    "crash",
    "corrupt",
    "broken",
    "timeout",
)
_NOVELTY_TERMS = (
    "new",
    "different",
    "changed",
    "novel",
    "unexpected",
)


class PerceptKind(str, Enum):
    USER_INTERACTION = "USER_INTERACTION"
    SCHEDULED_EVENT = "SCHEDULED_EVENT"
    ANOMALY_ALERT = "ANOMALY_ALERT"
    EXTERNAL_OBSERVATION = "EXTERNAL_OBSERVATION"
    SYSTEM_OBSERVATION = "SYSTEM_OBSERVATION"


class PerceptModality(str, Enum):
    TEXT = "TEXT"
    STRUCTURED = "STRUCTURED"
    METRIC = "METRIC"


class SalienceDisposition(str, Enum):
    REFLEX = "REFLEX"
    ORIENT = "ORIENT"
    DELIBERATE = "DELIBERATE"
    IGNORE = "IGNORE"


class PerceptSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    kind: PerceptKind
    modality: PerceptModality
    interface: str | None = None

    @field_validator("source_id")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_id must not be blank")
        return normalized

    @field_validator("interface")
    @classmethod
    def normalize_interface(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PerceptBuffer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_char_limit: int = Field(default=_INPUT_BUFFER_SEGMENT_CHARS, ge=1)
    max_segments: int = Field(default=_INPUT_BUFFER_MAX_SEGMENTS, ge=1)
    retained_segment_indices: tuple[int, ...] = Field(default_factory=tuple)
    segments: tuple[str, ...] = Field(default_factory=tuple)
    total_segments: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    truncated: bool = False

    @field_validator("segments")
    @classmethod
    def validate_segments(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value for value in values if value)
        if len(normalized) != len(values):
            raise ValueError("buffer segments must not be blank")
        return normalized


class PerceptFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    normalized_characters: int = Field(ge=0)
    token_count: int = Field(ge=0)
    line_count: int = Field(ge=0)
    contains_question: bool = False
    contains_url: bool = False
    contains_code_block: bool = False
    contains_structured_payload: bool = False
    uppercase_ratio: float = Field(ge=0.0, le=1.0)


class Percept(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    policy_version: str = PERCEPTION_POLICY_VERSION
    percept_id: UUID
    source: PerceptSource
    observed_at: datetime
    source_event_id: UUID | None = None
    conversation_id: UUID | None = None
    correlation_id: UUID
    raw_value_sha256: str = Field(min_length=64, max_length=64)
    normalized_text: str = Field(min_length=1)
    input_buffer: PerceptBuffer
    features: PerceptFeatures
    response_required: bool = False

    @field_validator("normalized_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("normalized_text must not be blank")
        return normalized


class AdvisorySemanticClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0.0, le=1.0)
    source_model: str = Field(min_length=1)
    authoritative: Literal[False] = False

    @field_validator("label", "source_model")
    @classmethod
    def normalize_text_field(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("classification fields must not be blank")
        return normalized


class SalienceSignals(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anomaly_score: int = Field(ge=0, le=3)
    threat_score: int = Field(ge=0, le=3)
    opportunity_score: int = Field(ge=0, le=3)
    goal_relevance_score: int = Field(ge=0, le=3)
    novelty_score: int = Field(ge=0, le=3)
    uncertainty_score: int = Field(ge=0, le=3)
    system_integrity_score: int = Field(ge=0, le=3)


class SalienceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    policy_version: str = SALIENCE_POLICY_VERSION
    percept_id: UUID
    disposition: SalienceDisposition
    signals: SalienceSignals
    trigger_terms: tuple[str, ...] = Field(default_factory=tuple)
    preauthorized_reflexes: tuple[str, ...] = Field(default_factory=tuple)
    advisory_classification: AdvisorySemanticClassification | None = None
    advisory_only: Literal[True] = True


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _observation_text(value: Any, modality: PerceptModality) -> str:
    if modality is PerceptModality.TEXT:
        if not isinstance(value, str):
            raise ValueError("text percepts require a string observation")
        return value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if modality is PerceptModality.METRIC:
        if isinstance(value, bool) or (
            not isinstance(value, (int, float)) and value is not None
        ):
            raise ValueError("metric percepts require a scalar numeric observation")
        return _stable_json(value)
    return _stable_json(value)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_buffer(text: str) -> PerceptBuffer:
    segments = [
        text[index : index + _INPUT_BUFFER_SEGMENT_CHARS]
        for index in range(0, len(text), _INPUT_BUFFER_SEGMENT_CHARS)
    ] or [text]
    total_segments = len(segments)
    if total_segments <= _INPUT_BUFFER_MAX_SEGMENTS:
        retained = segments
        retained_indices = tuple(range(total_segments))
    else:
        head_count = _INPUT_BUFFER_MAX_SEGMENTS // 2
        tail_count = _INPUT_BUFFER_MAX_SEGMENTS - head_count
        retained = segments[:head_count] + segments[-tail_count:]
        retained_indices = tuple(range(head_count)) + tuple(
            range(total_segments - tail_count, total_segments)
        )
    return PerceptBuffer(
        retained_segment_indices=retained_indices,
        segments=tuple(retained),
        total_segments=total_segments,
        total_characters=len(text),
        truncated=total_segments > _INPUT_BUFFER_MAX_SEGMENTS,
    )


def _uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    uppercase = sum(1 for char in letters if char.isupper())
    return uppercase / len(letters)


def _feature_flags(text: str, modality: PerceptModality) -> PerceptFeatures:
    stripped = text.strip()
    return PerceptFeatures(
        normalized_characters=len(text),
        token_count=sum(1 for _ in re.finditer(r"\S+", text)),
        line_count=(text.count("\n") + 1) if text else 0,
        contains_question="?" in text,
        contains_url=("://" in text) or ("www." in text.casefold()),
        contains_code_block="```" in text,
        contains_structured_payload=modality is not PerceptModality.TEXT
        or stripped.startswith("{")
        or stripped.startswith("["),
        uppercase_ratio=_uppercase_ratio(text),
    )


def deterministic_percept_id(
    source_event_id: UUID | None,
    correlation_id: UUID,
    source: PerceptSource,
    *,
    observed_at: datetime,
    normalized_text: str,
) -> UUID:
    seed = (
        str(source_event_id)
        if source_event_id is not None
        else (
            f"{correlation_id}:{source.source_id}:{observed_at.isoformat()}:"
            f"{_sha256_text(normalized_text)}"
        )
    )
    return uuid5(_PERCEPT_NAMESPACE, seed)


def normalize_percept(
    *,
    source: PerceptSource,
    observation: Any,
    observed_at: datetime,
    correlation_id: UUID,
    source_event_id: UUID | None = None,
    conversation_id: UUID | None = None,
    response_required: bool = False,
) -> Percept:
    raw_text = _observation_text(observation, source.modality)
    if not raw_text.strip():
        raise ValueError("percept observation must not be empty")
    normalized_text = raw_text.strip()
    return Percept(
        percept_id=deterministic_percept_id(
            source_event_id,
            correlation_id,
            source,
            observed_at=observed_at,
            normalized_text=normalized_text,
        ),
        source=source,
        observed_at=observed_at,
        source_event_id=source_event_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        raw_value_sha256=_sha256_text(raw_text),
        normalized_text=normalized_text,
        input_buffer=_build_buffer(normalized_text),
        features=_feature_flags(normalized_text, source.modality),
        response_required=response_required,
    )


def normalize_user_interaction_percept(
    *,
    user_text: str,
    observed_at: datetime,
    correlation_id: UUID,
    source_event_id: UUID,
    conversation_id: UUID,
) -> Percept:
    return normalize_percept(
        source=PerceptSource(
            source_id="user",
            kind=PerceptKind.USER_INTERACTION,
            modality=PerceptModality.TEXT,
            interface="chat",
        ),
        observation=user_text,
        observed_at=observed_at,
        source_event_id=source_event_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        response_required=True,
    )


def normalize_scheduled_percept(
    *,
    source_id: str,
    observation: Any,
    observed_at: datetime,
    correlation_id: UUID,
    source_event_id: UUID | None = None,
) -> Percept:
    return normalize_percept(
        source=PerceptSource(
            source_id=source_id,
            kind=PerceptKind.SCHEDULED_EVENT,
            modality=PerceptModality.STRUCTURED,
            interface="scheduler",
        ),
        observation=observation,
        observed_at=observed_at,
        source_event_id=source_event_id,
        correlation_id=correlation_id,
        response_required=False,
    )


def normalize_anomaly_percept(
    *,
    source_id: str,
    observation: Any,
    observed_at: datetime,
    correlation_id: UUID,
    source_event_id: UUID | None = None,
) -> Percept:
    return normalize_percept(
        source=PerceptSource(
            source_id=source_id,
            kind=PerceptKind.ANOMALY_ALERT,
            modality=PerceptModality.STRUCTURED,
            interface="anomaly-detector",
        ),
        observation=observation,
        observed_at=observed_at,
        source_event_id=source_event_id,
        correlation_id=correlation_id,
        response_required=False,
    )


def _term_matched(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _score_matches(text: str, terms: tuple[str, ...], *, cap: int = 3) -> tuple[int, tuple[str, ...]]:
    matched = tuple(sorted(term for term in terms if _term_matched(text, term)))
    return min(cap, len(matched)), matched


def evaluate_salience(
    percept: Percept,
    *,
    advisory_classification: AdvisorySemanticClassification | None = None,
) -> SalienceAssessment:
    lowered = percept.normalized_text.casefold()
    threat_score, threat_terms = _score_matches(lowered, _THREAT_TERMS)
    opportunity_score, opportunity_terms = _score_matches(lowered, _OPPORTUNITY_TERMS)
    goal_score, goal_terms = _score_matches(lowered, _GOAL_TERMS)
    uncertainty_score, uncertainty_terms = _score_matches(lowered, _UNCERTAINTY_TERMS)
    integrity_score, integrity_terms = _score_matches(lowered, _INTEGRITY_TERMS)
    novelty_score, novelty_terms = _score_matches(lowered, _NOVELTY_TERMS)
    novelty_score = min(
        3,
        novelty_score
        + int(percept.features.contains_url),
    )
    anomaly_score = min(
        3,
        int(percept.input_buffer.truncated)
        + int("!!!" in percept.normalized_text or "???" in percept.normalized_text)
        + int(percept.features.uppercase_ratio >= 0.35),
    )
    if percept.response_required:
        goal_score = max(goal_score, 2)
        novelty_score = max(novelty_score, 1)
    signals = SalienceSignals(
        anomaly_score=anomaly_score,
        threat_score=threat_score,
        opportunity_score=opportunity_score,
        goal_relevance_score=goal_score,
        novelty_score=novelty_score,
        uncertainty_score=min(3, uncertainty_score + int(percept.features.contains_question)),
        system_integrity_score=integrity_score,
    )
    if signals.system_integrity_score >= 3 and not percept.response_required:
        disposition = SalienceDisposition.REFLEX
    elif (
        signals.system_integrity_score >= 2
        or signals.threat_score >= 2
        or signals.anomaly_score >= 2
        or signals.uncertainty_score >= 2
    ):
        disposition = SalienceDisposition.ORIENT
    elif (
        percept.response_required
        or signals.goal_relevance_score >= 1
        or signals.opportunity_score >= 1
        or signals.novelty_score >= 1
    ):
        disposition = SalienceDisposition.DELIBERATE
    else:
        disposition = SalienceDisposition.IGNORE
    preauthorized_reflexes = (
        ("RAISE_INTEGRITY_ALERT",)
        if disposition is SalienceDisposition.REFLEX
        else ()
    )
    matched_terms = (
        *threat_terms,
        *opportunity_terms,
        *goal_terms,
        *uncertainty_terms,
        *integrity_terms,
        *novelty_terms,
    )
    return SalienceAssessment(
        percept_id=percept.percept_id,
        disposition=disposition,
        signals=signals,
        trigger_terms=tuple(dict.fromkeys(matched_terms)),
        preauthorized_reflexes=preauthorized_reflexes,
        advisory_classification=advisory_classification,
    )


def format_salience_context(assessment: SalienceAssessment) -> str:
    signals = assessment.signals
    advisory = "none"
    if assessment.advisory_classification is not None:
        advisory = (
            f"{assessment.advisory_classification.label} "
            f"(confidence={assessment.advisory_classification.confidence:.2f}, "
            f"authoritative=false)"
        )
    trigger_terms = ", ".join(assessment.trigger_terms) or "none"
    reflexes = ", ".join(assessment.preauthorized_reflexes) or "none"
    return (
        f"disposition={assessment.disposition.value}\n"
        f"anomaly_score={signals.anomaly_score}\n"
        f"threat_score={signals.threat_score}\n"
        f"opportunity_score={signals.opportunity_score}\n"
        f"goal_relevance_score={signals.goal_relevance_score}\n"
        f"novelty_score={signals.novelty_score}\n"
        f"uncertainty_score={signals.uncertainty_score}\n"
        f"system_integrity_score={signals.system_integrity_score}\n"
        f"trigger_terms={trigger_terms}\n"
        f"preauthorized_reflexes={reflexes}\n"
        f"advisory_semantic_classification={advisory}"
    )
