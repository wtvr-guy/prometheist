from datetime import datetime, timezone
import json
import subprocess
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from prometheist.environment_contracts import (
    DiscoveredResource, EnvironmentScan, ProviderReport, ResourceKind, ScanStatus,
    reconcile_environment, resource_id,
)
from prometheist.environment_providers import decode_windows_report, windows_inventory
from prometheist.security_posture import assess_security

HOST = UUID("d7602c30-dc16-4545-afef-3887970003e5")


def scan(*reports, **overrides):
    return EnvironmentScan(host_id=HOST, scan_id=uuid4(), observed_at=datetime.now(timezone.utc),
        reason="MANUAL", platform="Windows", reports=reports, **overrides)


def device(name, provider="usb"):
    return DiscoveredResource(resource_id=resource_id(HOST, provider, name), provider=provider,
                              kind=ResourceKind.DEVICE, name=name)


def test_reconcile_is_order_independent_and_failures_do_not_mean_unplugging():
    a, b = device("a"), device("b")
    original = scan(ProviderReport(provider="usb", status="COMPLETE", resources=(a, b)))
    mapping, changes = reconcile_environment(None, original)
    reordered = original.model_copy(update={"reports": (original.reports[0].model_copy(update={"resources": (b, a)}),)})
    assert reconcile_environment(None, reordered) == (mapping, changes)
    for status in ("PARTIAL", "UNAVAILABLE", "ERROR"):
        uncertain, changes = reconcile_environment(mapping, scan(ProviderReport(provider="usb", status=status, resources=(a,))))
        assert [c.change for c in changes] == ["UNCERTAIN"]
        assert {x.resource.name: x.presence.value for x in uncertain.resources} == {"a": "PRESENT", "b": "UNKNOWN"}
        restored, changes = reconcile_environment(uncertain, original)
        assert restored == mapping
        assert [c.change for c in changes] == ["RECOVERED"]
    removed, changes = reconcile_environment(mapping, scan(ProviderReport(provider="usb", status="COMPLETE", resources=(a,))))
    assert [c.change for c in changes] == ["REMOVED"]
    assert reconcile_environment(removed, scan(ProviderReport(provider="usb", status="ERROR")))[0].resources != mapping.resources
    _, changes = reconcile_environment(removed, original)
    assert [c.change for c in changes] == ["ADDED"]


def test_windows_phone_link_does_not_claim_phone_sensors():
    report = decode_windows_report(HOST, {"provider": "windows.phone_link", "status": "COMPLETE", "rows": [
        {"Name": "Microsoft.YourPhone", "PhoneConnection": "UNKNOWN", "SensorAccess": "NOT_ESTABLISHED"}]})
    assert report.resources[0].properties["SensorAccess"] == "NOT_ESTABLISHED"
    assert report.readings == ()


def test_windows_sensor_samples_are_separate_from_static_topology():
    report = decode_windows_report(HOST, {"provider": "windows.thermal", "status": "COMPLETE", "rows": [
        {"InstanceName": "ACPI\\thermal", "CurrentTemperature": 3000}]})
    assert report.readings[0].value == pytest.approx(26.85)
    assert "CurrentTemperature" not in report.resources[0].properties


def test_windows_timeout_retains_completed_sections_and_marks_others_unknown():
    line = json.dumps({"provider": "windows.cpu", "status": "COMPLETE", "rows": [{"DeviceID": "CPU0", "Name": "Processor"}]}).encode()
    def timeout(command, **kwargs):
        assert "-ExecutionPolicy" not in command
        assert kwargs["timeout"] > 0
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=line + b"\n{partial")
    reports = {r.provider: r for r in windows_inventory(HOST, run=timeout)}
    assert reports["windows.cpu"].status is ScanStatus.COMPLETE
    assert reports["windows.pnp"].status is ScanStatus.ERROR


@pytest.mark.parametrize("rows", [[{}], [{"DeviceID": "CPU0"}, {"DeviceID": "CPU0"}]])
def test_malformed_identity_fails_provider(rows):
    line = json.dumps({"provider": "windows.cpu", "status": "COMPLETE", "rows": rows}).encode()
    reports = windows_inventory(HOST, run=lambda *a, **kw: SimpleNamespace(stdout=line, returncode=0))
    assert next(r for r in reports if r.provider == "windows.cpu").status is ScanStatus.ERROR


def test_posture_never_converts_permission_failure_to_disabled_protection():
    report = decode_windows_report(HOST, {"provider": "windows.security.firewall", "status": "COMPLETE", "rows": [
        {"Name": "Public", "Enabled": "False"}, {"Name": "Private", "Enabled": "True"}]})
    findings = assess_security(scan(report)).findings
    assert {f.status for f in findings if f.rule_id == "firewall.enabled"} == {"PASS", "FAIL"}
    assert all(f.status == "UNKNOWN" for f in findings if f.rule_id != "firewall.enabled")
    failed = assess_security(scan(report.model_copy(update={"status": ScanStatus.ERROR})))
    assert all(f.status == "UNKNOWN" for f in failed.findings)
