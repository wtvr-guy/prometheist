from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from jit_agent import db
from jit_agent.attention_store import load_scheduler
from jit_agent.interaction_store import load_interaction
from jit_agent.perception import (
    AdvisorySemanticClassification,
    PerceptKind,
    PerceptModality,
    PerceptSource,
    SalienceDisposition,
    evaluate_salience,
    normalize_percept,
    normalize_user_interaction_percept,
)
from jit_agent.percept_response_runtime import begin_percept


NOW = datetime(2026, 9, 10, 17, 0, tzinfo=timezone.utc)


class FixedProbe:
    def capture(self):
        from jit_agent.attention_observation import HostResourceMetrics

        return HostResourceMetrics(
            platform="test",
            logical_cpu_count=8,
            cpu_utilization_percent=10,
            load_1m=0,
            memory_total_mib=16_384,
            memory_available_mib=12_000,
        )


def test_normalize_percept_supports_structured_observations_deterministically() -> None:
    correlation_id = uuid.uuid4()
    source = PerceptSource(
        source_id="sensor:health",
        kind=PerceptKind.SYSTEM_OBSERVATION,
        modality=PerceptModality.STRUCTURED,
        interface="monitor",
    )

    percept = normalize_percept(
        source=source,
        observation={"status": "failed", "component": "disk", "count": 2},
        observed_at=NOW,
        correlation_id=correlation_id,
    )

    assert percept.source.modality is PerceptModality.STRUCTURED
    assert percept.normalized_text == '{"component":"disk","count":2,"status":"failed"}'
    assert percept.input_buffer.segments == (percept.normalized_text,)

    repeated = normalize_percept(
        source=source,
        observation={"component": "disk", "count": 2, "status": "failed"},
        observed_at=NOW,
        correlation_id=correlation_id,
    )
    assert repeated == percept


def test_normalize_percept_rejects_modality_mismatch() -> None:
    with pytest.raises(ValueError):
        normalize_percept(
            source=PerceptSource(
                source_id="sensor:health",
                kind=PerceptKind.SYSTEM_OBSERVATION,
                modality=PerceptModality.TEXT,
                interface="monitor",
            ),
            observation={"status": "failed"},
            observed_at=NOW,
            correlation_id=uuid.uuid4(),
        )


def test_structured_scalar_boolean_payload_is_allowed() -> None:
    percept = normalize_percept(
        source=PerceptSource(
            source_id="sensor:flag",
            kind=PerceptKind.EXTERNAL_OBSERVATION,
            modality=PerceptModality.STRUCTURED,
            interface="webhook",
        ),
        observation=True,
        observed_at=NOW,
        correlation_id=uuid.uuid4(),
    )

    assert percept.normalized_text == "true"
    assert percept.features.contains_structured_payload is True


def test_metric_scalar_uses_stable_json_normalization() -> None:
    percept = normalize_percept(
        source=PerceptSource(
            source_id="sensor:temperature",
            kind=PerceptKind.EXTERNAL_OBSERVATION,
            modality=PerceptModality.METRIC,
            interface="telemetry",
        ),
        observation=1.5,
        observed_at=NOW,
        correlation_id=uuid.uuid4(),
    )

    assert percept.normalized_text == "1.5"


def test_user_percept_builds_bounded_input_buffer() -> None:
    conversation_id = uuid.uuid4()
    correlation_id = uuid.uuid4()
    source_event_id = uuid.uuid4()
    user_text = "A" * 700

    percept = normalize_user_interaction_percept(
        user_text=user_text,
        observed_at=NOW,
        correlation_id=correlation_id,
        source_event_id=source_event_id,
        conversation_id=conversation_id,
    )

    assert percept.response_required is True
    assert percept.input_buffer.truncated is True
    assert percept.input_buffer.total_segments == 5
    assert percept.input_buffer.retained_segment_indices == (0, 1, 3, 4)
    assert len(percept.input_buffer.segments) == 4


def test_advisory_semantic_classification_has_no_policy_authority() -> None:
    percept = normalize_user_interaction_percept(
        user_text="Please review this roadmap update.",
        observed_at=NOW,
        correlation_id=uuid.uuid4(),
        source_event_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
    )

    assessment = evaluate_salience(
        percept,
        advisory_classification=AdvisorySemanticClassification(
            label="REFLEX",
            confidence=1.0,
            source_model="test-model",
        ),
    )

    assert assessment.disposition is SalienceDisposition.DELIBERATE
    assert assessment.advisory_only is True
    assert assessment.advisory_classification is not None
    assert assessment.advisory_classification.authoritative is False


def test_salience_uses_whole_term_matching() -> None:
    percept = normalize_user_interaction_percept(
        user_text="Explain how this address changed.",
        observed_at=NOW,
        correlation_id=uuid.uuid4(),
        source_event_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
    )

    assessment = evaluate_salience(percept)

    assert "plan" not in assessment.trigger_terms
    assert "add" not in assessment.trigger_terms


def test_system_integrity_observation_can_trigger_reflex() -> None:
    percept = normalize_percept(
        source=PerceptSource(
            source_id="sensor:integrity",
            kind=PerceptKind.SYSTEM_OBSERVATION,
            modality=PerceptModality.TEXT,
            interface="daemon",
        ),
        observation="error failure crash",
        observed_at=NOW,
        correlation_id=uuid.uuid4(),
    )

    assessment = evaluate_salience(percept)

    assert assessment.disposition is SalienceDisposition.REFLEX
    assert assessment.preauthorized_reflexes == ("RAISE_INTEGRITY_ALERT",)


def test_begin_percept_persists_normalized_percept_and_salience() -> None:
    connection = db.get_connection()
    try:
        conversation_id = uuid.uuid4()
        interaction = begin_percept(
            connection,
            "Please investigate this error failure crash immediately.",
            conversation_id,
            probe=FixedProbe(),
            clock=lambda: NOW,
        )

        stored = load_interaction(connection, interaction.interaction_id)
        assert stored.percept is not None
        assert stored.percept.source.kind is PerceptKind.USER_INTERACTION
        assert stored.percept.source_event_id == stored.user_prompt_event_id
        assert stored.salience_assessment is not None
        assert stored.salience_assessment.percept_id == stored.percept.percept_id
        assert stored.salience_assessment.disposition is SalienceDisposition.ORIENT

        scheduler = load_scheduler(connection)
        task = scheduler.tasks[interaction.task_id]
        assert task.resumable_state["percept_id"] == str(stored.percept.percept_id)
        assert task.resumable_state["salience_disposition"] == "ORIENT"
    finally:
        connection.close()
