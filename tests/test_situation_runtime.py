from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from jit_agent import db, event_store
from jit_agent.action_outcomes import issue_action, observe_action_outcome
from jit_agent.attention_observation import HostResourceMetrics
from jit_agent.attention_store import load_scheduler
from jit_agent.cognitive_store import get_record, list_records, put_record, rebuild_heads
from jit_agent.consolidation import ConsolidationSchedule, emit_due_consolidations, schedule_consolidation
from jit_agent.expectations import Expectation
from jit_agent.models import EventType
from jit_agent.percept_context import Observation, PerceptContext
from jit_agent.percept_intake import ingest_percept, install_source_policy
from jit_agent.perception import PerceptKind, PerceptModality, PerceptSource
from jit_agent.percept_triage import SourcePolicy
from jit_agent.situation_runtime import drain_situations, submit_situation_page, run_situation_task
from jit_agent.situations import register_expectation


class FixedProbe:
    def __init__(self, available=12000):
        self.available = available

    def capture(self):
        return HostResourceMetrics(platform="test", logical_cpu_count=8, cpu_utilization_percent=10,
                                   load_1m=0, memory_total_mib=16384, memory_available_mib=self.available)


@pytest.fixture
def conn():
    with db.get_connection() as connection:
        yield connection


def source_setup(conn):
    source = PerceptSource(source_id="test:monitor", kind=PerceptKind.SYSTEM_OBSERVATION, modality=PerceptModality.STRUCTURED)
    install_source_policy(conn, SourcePolicy(source_id=source.source_id, kind=source.kind, modalities=(source.modality,)))
    return source


def add_observation(conn, source, property_name="memory", value=300, expected=None, delivery_id=None):
    return ingest_percept(conn, source=source, observation={property_name: value}, observed_at=datetime.now(timezone.utc),
                          delivery_id=delivery_id or str(uuid4()), context=PerceptContext(
                              entity_refs=("worker:1",), expectation_refs=(expected,) if expected else (),
                              observations=(Observation(subject="worker:1", property=property_name, value=value),)))


def register_memory_expectation(conn):
    now = datetime.now(timezone.utc)
    expectation = Expectation(expectation_id=uuid4(), subject="worker:1", property="memory",
                              expected_range=(500, 16000), normalization_scale=200, source="test-policy",
                              provenance=(uuid4(),), confidence=1.0, valid_from=now - timedelta(minutes=1),
                              valid_until=now + timedelta(hours=1))
    register_expectation(conn, expectation)
    return expectation.expectation_id


def test_heads_rebuild_exactly_without_mutating_events(conn):
    put_record(conn, "test", "a", {"value": 1}, revision="first")
    put_record(conn, "test", "a", {"value": 2}, revision="second")
    original = conn.execute("SELECT event_id, payload FROM events ORDER BY global_seq").fetchall()
    rebuild_heads(conn)
    assert get_record(conn, "test", "a") == {"value": 2}
    assert conn.execute("SELECT event_id, payload FROM events ORDER BY global_seq").fetchall() == original


def test_intake_replay_and_conflicting_delivery(conn):
    source = source_setup(conn)
    args = dict(source=source, observation={"value": 1}, observed_at=datetime.now(timezone.utc), delivery_id="delivery:1")
    first = ingest_percept(conn, **args)
    before = conn.execute("SELECT count(*) FROM events").fetchone()[0]
    assert ingest_percept(conn, **args) == first
    assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == before
    with pytest.raises(ValueError, match="conflicting deterministic event retry"):
        ingest_percept(conn, **{**args, "observation": {"value": 2}})


def test_intake_crash_recovers_post_snapshot_receipt(conn, monkeypatch):
    from jit_agent import percept_intake
    source = source_setup(conn)
    args = dict(source=source, observation={"value": 1}, observed_at=datetime.now(timezone.utc), delivery_id="interrupted")
    original = percept_intake.put_record
    def interrupted(connection, kind, *positional, **kwargs):
        if kind == "intake_receipt":
            raise RuntimeError("simulated process loss")
        return original(connection, kind, *positional, **kwargs)
    monkeypatch.setattr(percept_intake, "put_record", interrupted)
    with pytest.raises(RuntimeError):
        ingest_percept(conn, **args)
    monkeypatch.setattr(percept_intake, "put_record", original)
    ingest_percept(conn, **args)
    assert len(list_records(conn, "situation")) == 1
    assert len(list_records(conn, "situation")[0][1]["percept_ids"]) == 1


def test_source_configuration_can_revert_without_reusing_old_head(conn):
    a = SourcePolicy(source_id="test", kind=PerceptKind.SYSTEM_OBSERVATION, modalities=(PerceptModality.STRUCTURED,))
    b = a.model_copy(update={"response_required": True})
    for value in (a, b, a):
        install_source_policy(conn, value)
        assert get_record(conn, "source_policy", "test") == value.model_dump(mode="json")


def test_four_percepts_one_guarded_task_and_finite_action_feedback(conn, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    source = source_setup(conn)
    expected = register_memory_expectation(conn)
    for property_name, value in (("cpu", 98), ("memory", 300), ("heartbeat", False), ("lease", "expired")):
        add_observation(conn, source, property_name, value, expected if property_name == "memory" else None)
    candidates = list_records(conn, "situation_candidate")
    assert len(candidates) == 1
    assert len(candidates[0][1]["situation"]["percept_ids"]) == 4
    ids = submit_situation_page(conn, probe=FixedProbe())
    assert len(ids) == 1
    result = run_situation_task(conn, ids[0], probe=FixedProbe())
    assert result == {"response_required": False, "response_text": None}
    assert len(list_records(conn, "action_execution")) == 1
    outcomes = conn.execute("SELECT payload FROM events WHERE event_type = %s", (EventType.PERCEPT_OBSERVATION.value,)).fetchall()
    assert any(row[0]["percept"]["source"]["kind"] == "ACTION_OUTCOME" for row in outcomes)
    # Subsequent scheduler pages may process bookkeeping for the matched outcome,
    # but must never manufacture more actions for an unchanged old discrepancy.
    for _ in range(4):
        drain_situations(conn, probe=FixedProbe())
    assert len(list_records(conn, "action_execution")) == 1
    from jit_agent import artifact_journal
    artifacts = artifact_journal.interaction_artifacts(ids[0])
    assert not any(value["artifact_type"] == "LLM_INVOCATION" for value in artifacts)
    assert len([value for value in artifacts if value["artifact_type"] == "STAGE_RESULT"]) == 6


def test_situation_priority_cannot_override_memory_admission(conn):
    source = source_setup(conn)
    add_observation(conn, source, expected=register_memory_expectation(conn))
    ids = submit_situation_page(conn, probe=FixedProbe(10))
    assert len(ids) == 1
    assert not load_scheduler(conn).worker_visible_assignments()
    assert run_situation_task(conn, ids[0], probe=FixedProbe(10)) is None


def test_scheduled_consolidation_executes_separately_and_preserves_sources(conn):
    source = source_setup(conn)
    add_observation(conn, source, value=500)
    original = conn.execute("SELECT event_id, payload FROM events ORDER BY global_seq").fetchall()
    now = datetime.now(timezone.utc)
    schedule = ConsolidationSchedule(schedule_id=uuid4(), due_at=now)
    schedule_consolidation(conn, schedule)
    assert not list_records(conn, "consolidation")
    emit_due_consolidations(conn, now=now)
    emit_due_consolidations(conn, now=now)
    for _ in range(4):
        drain_situations(conn, probe=FixedProbe())
    projections = list_records(conn, "consolidation")
    assert len(projections) == 1
    assert projections[0][1]["canonical_records_modified"] is False
    assert projections[0][1]["projections"][0]["observed_values"][0]["support_percept_ids"]
    for event_id, payload in original:
        assert event_store.get_event_by_id(conn, event_id).payload == payload


def test_forged_action_success_receipt_fails_closed(conn):
    now = datetime.now(timezone.utc)
    action_id = uuid4()
    issue_action(conn, action_id=action_id, task_id=uuid4(), at=now)
    unrelated = put_record(conn, "test", "unrelated", {"observed_status": "SUCCEEDED"}, revision="1")
    with pytest.raises(ValueError, match="matching registered executor receipt"):
        observe_action_outcome(conn, action_id=action_id, receipt_event_id=unrelated, status="SUCCEEDED", observed_at=now)


def test_media_quarantine_revalidates_content_not_supplied_metadata(conn, tmp_path):
    from jit_agent.percept_adapters import preserve_media, verify_media
    from jit_agent.reflexes import quarantine_corrupt_media
    original = tmp_path / "input.bin"
    original.write_bytes(b"valid content")
    reference = preserve_media(original, mime_type="application/octet-stream")
    path = verify_media(reference)
    wrong_metadata = reference.model_copy(update={"byte_length": 1})
    assert not quarantine_corrupt_media(conn, wrong_metadata)
    assert verify_media(reference) == path
    path.write_bytes(b"corrupt content")
    assert quarantine_corrupt_media(conn, reference)
    assert path.exists()
    with pytest.raises(ValueError, match="quarantined"):
        verify_media(reference)
