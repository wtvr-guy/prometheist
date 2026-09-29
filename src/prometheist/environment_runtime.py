"""Startup inventory, durable change receipts, and a model-free local monitor."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import threading
from uuid import UUID, uuid4

from prometheist import db
from prometheist.artifact_journal import artifact_root, _atomic_write_json
from prometheist.cognitive_store import get_record, put_record, record_lock
from prometheist.environment_contracts import (
    EnvironmentMap, EnvironmentScan, ResourcePresence, content_digest, reconcile_environment,
    MONITOR_INTERVAL_SECONDS, MIN_MONITOR_INTERVAL_SECONDS, MAX_MONITOR_INTERVAL_SECONDS,
    MONITOR_STOP_TIMEOUT_SECONDS,
)
from prometheist.environment_providers import scan_environment
from prometheist.percept_context import MAX_CONTEXT_ITEMS, Observation, PerceptContext
from prometheist.percept_intake import ingest_percept, install_source_policy
from prometheist.perception import PerceptKind, PerceptModality, PerceptSource
from prometheist.percept_triage import SourcePolicy


def local_host_id() -> UUID:
    """Installation identity; never inferred from model text or sent externally."""
    from prometheist.imprinting import _outside_git
    root = _outside_git(artifact_root())
    for key in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        if os.environ.get(key) and root.is_relative_to(Path(os.environ[key]).expanduser().resolve()):
            raise ValueError("host inventory needs a private artifact root outside OneDrive")
    path = root / "operator" / "host-id"
    if path.exists():
        return UUID(path.read_text(encoding="utf-8").strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = uuid4()
    temporary = path.with_name(f"host-id-{candidate}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(str(candidate))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)
    return UUID(path.read_text(encoding="utf-8").strip())


def load_environment(conn, host_id: UUID) -> EnvironmentMap | None:
    data = get_record(conn, "environment_map", str(host_id))
    return EnvironmentMap.model_validate(data) if data else None


def _complete_transition(conn, transition):
    scan_id, host_id = transition["scan_id"], transition["host_id"]
    if transition["map"] is not None:
        put_record(conn, "environment_map", host_id, transition["map"], revision=scan_id)
    put_record(conn, "security_posture", host_id, transition["security_posture"], revision=scan_id)
    observations = transition["observations"]
    if transition["changes"] or observations:
        source_id = f"local:environment:{host_id}"
        policy = SourcePolicy(source_id=source_id, kind=PerceptKind.SYSTEM_OBSERVATION,
                              modalities=(PerceptModality.STRUCTURED,), self_model_evidence=False)
        install_source_policy(conn, policy)
        # All observations remain in canonical JSON. The situation view alone is
        # bounded; hardware telemetry is never promoted to a personality trait.
        context = PerceptContext(entity_refs=(f"host:{host_id}",),
            observations=tuple(Observation.model_validate(o) for o in observations[:MAX_CONTEXT_ITEMS]))
        ingest_percept(conn, source=PerceptSource(source_id=source_id, kind=PerceptKind.SYSTEM_OBSERVATION,
            modality=PerceptModality.STRUCTURED, interface="LOCAL_OS_APIS"),
            observation={"scan_id": scan_id, "map_sha256": transition["map_sha256"],
                         "changes": transition["changes"], "readings": observations,
                         "security_posture": transition["security_posture"],
                         "providers": transition["providers"]},
            observed_at=datetime.fromisoformat(transition["observed_at"]), delivery_id=scan_id, context=context)
    receipt = {key: value for key, value in transition.items() if key != "map"}
    put_record(conn, "environment_latest", host_id, receipt, revision=scan_id)
    put_record(conn, "environment_receipt", scan_id, receipt, revision="1")
    return receipt


def record_environment_scan(conn, scan: EnvironmentScan) -> dict:
    """Stage once, resume idempotently, then publish the latest complete receipt.

    A pending transition survives interruption between independent canonical
    writes. It is completed before a newer observation is admitted. Late scans
    cannot roll the topology back, and exact retries cannot duplicate percepts.
    """
    scan_hash = content_digest(scan.model_dump(mode="json"))
    host_id = str(scan.host_id)
    with record_lock(conn, f"environment:{host_id}"):
        completed = get_record(conn, "environment_receipt", str(scan.scan_id))
        if completed:
            if completed["scan_sha256"] != scan_hash:
                raise ValueError("conflicting environment scan retry")
            return completed
        pending = get_record(conn, "environment_transition", host_id)
        if pending and get_record(conn, "environment_receipt", pending["scan_id"]) is None:
            if pending["scan_id"] == str(scan.scan_id) and pending["scan_sha256"] != scan_hash:
                raise ValueError("conflicting environment scan retry")
            _complete_transition(conn, pending)
            if pending["scan_id"] == str(scan.scan_id):
                if pending["scan_sha256"] != scan_hash:
                    raise ValueError("conflicting environment scan retry")
                return get_record(conn, "environment_receipt", str(scan.scan_id))
        latest = get_record(conn, "environment_latest", host_id)
        if latest and scan.observed_at <= datetime.fromisoformat(latest["observed_at"]):
            raise ValueError("late environment scan cannot replace a newer observation")
        previous = load_environment(conn, scan.host_id)
        current, changes = reconcile_environment(previous, scan)
        observations = [Observation(subject=f"resource:{reading.resource_id}", property=reading.metric,
                                   value=reading.value, unit=reading.unit).model_dump(mode="json")
                        for report in scan.reports for reading in report.readings]
        # Exact provider resource arrays are content-addressed once. Heartbeats
        # reuse their hashes instead of duplicating the entire hardware inventory.
        from prometheist.blob_store import put_blob
        import json
        source_reports = []
        for report in scan.reports:
            payload = report.model_dump(mode="json")
            payload["resources_blob"] = put_blob(json.dumps(payload.pop("resources"), sort_keys=True,
                separators=(",", ":")).encode(), media_type="application/json").to_dict()
            source_reports.append(payload)
        from prometheist.security_posture import assess_security
        transition = {"scan_id": str(scan.scan_id), "host_id": host_id, "scan_sha256": scan_hash,
            "security_posture": assess_security(scan).model_dump(mode="json"),
            "observed_at": scan.observed_at.isoformat(), "reason": scan.reason, "platform": scan.platform,
            "map_sha256": content_digest(current.model_dump(mode="json")),
            "map": current.model_dump(mode="json") if previous != current else None,
            "changes": [change.model_dump(mode="json") for change in changes], "observations": observations,
            "source_reports": source_reports,
            "providers": {r.provider: {"status": r.status.value, "diagnostic": r.diagnostic,
                                      "resource_count": len(r.resources)} for r in scan.reports}}
        put_record(conn, "environment_transition", host_id, transition, revision=str(scan.scan_id))
        return _complete_transition(conn, transition)


def capture_and_record(*, reason="MANUAL"):
    scan = scan_environment(local_host_id(), reason=reason)
    with db.get_connection() as conn:
        return record_environment_scan(conn, scan)


def import_device_scan(conn, *, parent_id: UUID, scan: EnvironmentScan):
    """Explicit operator import of a cooperative device's own inventory.

    This is device-reported evidence, not host-verified CPU/RAM capacity. It
    never adds remote compute to the local scheduler or authorizes a connection.
    """
    host = local_host_id()
    if scan.host_id == host:
        raise ValueError("device report cannot replace the local host inventory")
    mapping = load_environment(conn, host)
    parent = next((entry for entry in mapping.resources if entry.resource.resource_id == parent_id), None) if mapping else None
    if parent is None or parent.presence is not ResourcePresence.PRESENT:
        raise ValueError("device report requires an observed present parent device")
    with record_lock(conn, f"device-environment:{parent_id}"):
        prior = get_record(conn, "device_environment", str(parent_id))
        if prior and prior["scan"]["host_id"] != str(scan.host_id):
            raise ValueError("parent device is already bound to another reporting host")
        if prior and scan.observed_at < datetime.fromisoformat(prior["scan"]["observed_at"]):
            raise ValueError("late device report cannot replace a newer observation")
        payload = {"authority": "OPERATOR_IMPORTED_DEVICE_REPORT", "parent_id": str(parent_id),
                   "local_host_id": str(host), "scan": scan.model_dump(mode="json")}
        put_record(conn, "device_environment", str(parent_id), payload, revision=str(scan.scan_id))
        return payload


class EnvironmentMonitor:
    def __init__(self, *, interval=MONITOR_INTERVAL_SECONDS, capture=capture_and_record):
        if not MIN_MONITOR_INTERVAL_SECONDS <= interval <= MAX_MONITOR_INTERVAL_SECONDS:
            raise ValueError("monitor interval is outside the governed range")
        self.interval, self.capture = interval, capture
        self.stop_event = threading.Event()
        self.thread = None
        self.last_findings_digest = None

    def start(self):
        # The startup scan completes before any user cognition starts.
        receipt = self.capture(reason="STARTUP")
        self._report_findings(receipt)
        self._health({"status": "RUNNING", "observed_at": receipt["observed_at"], "scan_id": receipt["scan_id"]})
        self.thread = threading.Thread(target=self._run, name="prometheist-environment", daemon=True)
        self.thread.start()
        return receipt

    def _run(self):
        while not self.stop_event.wait(self.interval):
            try:
                receipt = self.capture(reason="POLL")
                self._report_findings(receipt)
                self._health({"status": "RUNNING", "observed_at": receipt["observed_at"], "scan_id": receipt["scan_id"]})
            except Exception as exc:
                # Persist failure locally even if PostgreSQL is unavailable. Do
                # not label the stale topology current or synthesize removals.
                self._health({"status": "ERROR", "observed_at": datetime.now(timezone.utc).isoformat(),
                              "error_type": type(exc).__name__})
                print(f"PROMETHEIST_ENVIRONMENT_MONITOR_ERROR={type(exc).__name__}", file=sys.stderr)

    def _health(self, status):
        try:
            _atomic_write_json(artifact_root() / "operator" / "environment-monitor-health.json", status)
        except OSError as exc:
            print(f"PROMETHEIST_ENVIRONMENT_HEALTH_WRITE_ERROR={type(exc).__name__}", file=sys.stderr)

    def _report_findings(self, receipt):
        findings = receipt.get("security_posture", {}).get("findings", [])
        active = [f for f in findings if f["status"] != "PASS"]
        digest = content_digest(active)
        if digest != self.last_findings_digest:
            self.last_findings_digest = digest
            if active:
                failed = sum(f["status"] == "FAIL" for f in active)
                unknown = sum(f["status"] == "UNKNOWN" for f in active)
                print(f"PROMETHEIST_SECURITY_FINDINGS fail={failed} unknown={unknown}; use environment show for evidence", file=sys.stderr)

    def close(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=MONITOR_STOP_TIMEOUT_SECONDS)
            if self.thread.is_alive():
                raise RuntimeError("environment monitor did not stop within its declared bound")
        self._health({"status": "STOPPED", "observed_at": datetime.now(timezone.utc).isoformat()})


@contextmanager
def environment_session():
    monitor = EnvironmentMonitor()
    monitor.start()
    try:
        yield monitor
    finally:
        monitor.close()


def export_device_scan(path: Path):
    # This writes locally only. Moving the report to the host is an explicit
    # user action; no pairing, upload, broadcast, or account access occurs here.
    from prometheist.imprinting import _outside_git
    path = _outside_git(path)
    scan = scan_environment(local_host_id(), reason="DEVICE_EXPORT")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(scan.model_dump_json(indent=2) + "\n")
    return scan
