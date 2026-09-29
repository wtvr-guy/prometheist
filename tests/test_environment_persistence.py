from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from prometheist import db, environment_runtime as runtime
from prometheist.cognitive_store import get_record, record_history, rebuild_heads
from prometheist.environment_contracts import DiscoveredResource, EnvironmentScan, ProviderReport, SensorReading


def fixture_scan(host_id, *, moment=None, scan_id=None):
    resource = DiscoveredResource(resource_id=uuid4(), provider="fixture", kind="DEVICE", name="USB sensor")
    return EnvironmentScan(host_id=host_id, scan_id=scan_id or uuid4(), reason="MANUAL", platform="Fixture",
        observed_at=moment or datetime.now(timezone.utc), reports=(ProviderReport(provider="fixture", status="COMPLETE",
        resources=(resource,), readings=(SensorReading(resource_id=resource.resource_id, metric="temperature", value=21, unit="celsius"),)),))


def test_replay_persists_exact_evidence_and_noop_map_deduplicates():
    scan = fixture_scan(runtime.local_host_id())
    with db.get_connection() as conn:
        receipt = runtime.record_environment_scan(conn, scan)
        count = conn.execute("SELECT count(*) FROM events").fetchone()[0]
        assert runtime.record_environment_scan(conn, scan) == receipt
        assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == count
        later = scan.model_copy(update={"scan_id": uuid4(), "observed_at": scan.observed_at + timedelta(seconds=1)})
        second = runtime.record_environment_scan(conn, later)
        assert not second["changes"]
        assert len(record_history(conn, "environment_map", str(scan.host_id))) == 1
        assert second["source_reports"][0]["resources_blob"] == receipt["source_reports"][0]["resources_blob"]
        with pytest.raises(ValueError, match="conflicting"):
            runtime.record_environment_scan(conn, scan.model_copy(update={"platform": "Different"}))
        rebuild_heads(conn)
        assert get_record(conn, "environment_latest", str(scan.host_id))["scan_id"] == str(later.scan_id)


@pytest.mark.parametrize("crash_kind", ["security_posture", "environment_latest", "environment_receipt"])
def test_interrupted_transition_resumes_before_next_observation(monkeypatch, crash_kind):
    scan = fixture_scan(runtime.local_host_id())
    original = runtime.put_record
    def fail(conn, kind, *args, **kwargs):
        if kind == crash_kind:
            raise RuntimeError("simulated power loss")
        return original(conn, kind, *args, **kwargs)
    with db.get_connection() as conn:
        monkeypatch.setattr(runtime, "put_record", fail)
        with pytest.raises(RuntimeError, match="power loss"):
            runtime.record_environment_scan(conn, scan)
        monkeypatch.setattr(runtime, "put_record", original)
        later = scan.model_copy(update={"scan_id": uuid4(), "observed_at": scan.observed_at + timedelta(seconds=1)})
        runtime.record_environment_scan(conn, later)
        assert get_record(conn, "environment_receipt", str(scan.scan_id))
        assert get_record(conn, "environment_latest", str(scan.host_id))["scan_id"] == str(later.scan_id)
        assert len(record_history(conn, "environment_map", str(scan.host_id))) == 1
        with pytest.raises(ValueError, match="late"):
            runtime.record_environment_scan(conn, scan.model_copy(update={"scan_id": uuid4()}))


def test_device_report_remains_separate_and_requires_observed_parent():
    scan = fixture_scan(runtime.local_host_id())
    parent_id = scan.reports[0].resources[0].resource_id
    foreign = fixture_scan(uuid4())
    with db.get_connection() as conn:
        with pytest.raises(ValueError, match="present parent"):
            runtime.import_device_scan(conn, parent_id=parent_id, scan=foreign)
        runtime.record_environment_scan(conn, scan)
        before = runtime.load_environment(conn, scan.host_id)
        attached = runtime.import_device_scan(conn, parent_id=parent_id, scan=foreign)
        assert attached["authority"] == "OPERATOR_IMPORTED_DEVICE_REPORT"
        assert runtime.load_environment(conn, scan.host_id) == before
        with pytest.raises(ValueError, match="another reporting host"):
            runtime.import_device_scan(conn, parent_id=parent_id, scan=fixture_scan(uuid4()))
