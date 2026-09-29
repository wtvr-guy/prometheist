import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from prometheist.environment_contracts import content_digest
from prometheist import environment_runtime, os_security
from prometheist.security_posture import enroll_security, enrollment_path, enrollment_proposal


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setenv("PROMETHEIST_SUBJECT_ID", "subject_fixture")
    monkeypatch.setattr(os_security.platform, "system", lambda: "Windows")
    monkeypatch.setattr(os_security, "runtime_programs", lambda: (r"C:\private\python.exe",))
    host_id = uuid4()
    monkeypatch.setattr(environment_runtime, "local_host_id", lambda: host_id)
    proposal = enrollment_proposal("subject_fixture", host_id)
    enroll_security("subject_fixture", host_id, accepted_digest=content_digest(proposal))
    return host_id


def test_firewall_review_is_exact_and_only_structured_json_reaches_powershell(host):
    plan = os_security.firewall_plan(host)
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert "-File" in command and "-Command" not in command and not kwargs.get("shell")
        assert json.loads(kwargs["input"])["rules"][0]["program"] == r"C:\private\python.exe"
        return SimpleNamespace(returncode=0, stdout=b'{"status":"VERIFIED_RULE_STATE"}')
    with pytest.raises(ValueError):
        os_security.execute_firewall_plan(plan, accepted_digest="yes", run=run)
    for altered in (plan.model_copy(update={"host_id": uuid4()}),
                    plan.model_copy(update={"remote_addresses": ("Any",)}),
                    plan.model_copy(update={"impact": "no impact"})):
        with pytest.raises(ValueError):
            os_security.execute_firewall_plan(altered, accepted_digest=content_digest(altered.model_dump(mode="json")), run=run)
    assert not calls
    receipt = os_security.execute_firewall_plan(plan, accepted_digest=content_digest(plan.model_dump(mode="json")), run=run)
    assert receipt["traffic_tested"] is False
    assert len(calls) == 1


def test_revocation_blocks_apply_but_permits_reviewed_undo(host):
    enrollment_path().unlink()
    plan = os_security.firewall_plan(host)
    with pytest.raises(PermissionError):
        os_security.execute_firewall_plan(plan, accepted_digest=content_digest(plan.model_dump(mode="json")))
    remove = os_security.firewall_plan(host, action="REMOVE")
    result = os_security.execute_firewall_plan(remove, accepted_digest=content_digest(remove.model_dump(mode="json")),
        run=lambda *a, **kw: SimpleNamespace(returncode=0, stdout=b'{"status":"VERIFIED_RULE_STATE"}'))
    assert result["action"] == "REMOVE"


def test_partial_failure_is_recorded_and_not_reported_as_enforcement(host, tmp_path):
    plan = os_security.firewall_plan(host)
    with pytest.raises(RuntimeError, match="denied"):
        os_security.execute_firewall_plan(plan, accepted_digest=content_digest(plan.model_dump(mode="json")),
            run=lambda *a, **kw: SimpleNamespace(returncode=1, stdout=b'{"status":"FAILED_OR_INCOMPLETE","error":"denied"}'))
    data = json.loads((tmp_path / "operator/firewall-receipt.json").read_text())
    assert data["status"] == "FAILED_OR_INCOMPLETE"
    assert not data["traffic_tested"]


def test_private_host_identity_is_stable_and_refuses_git_and_onedrive(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "private"))
    assert environment_runtime.local_host_id() == environment_runtime.local_host_id()
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError, match="Git"):
        environment_runtime.local_host_id()
    (tmp_path / ".git").rmdir()
    monkeypatch.setenv("OneDrive", str(tmp_path))
    with pytest.raises(ValueError, match="OneDrive"):
        environment_runtime.local_host_id()


def test_private_device_export_refuses_a_git_target_before_scanning(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(environment_runtime, "scan_environment", lambda *a, **kw: pytest.fail("must not scan before path validation"))
    with pytest.raises(ValueError, match="Git"):
        environment_runtime.export_device_scan(tmp_path / "inventory.json")
    assert not (tmp_path / "inventory.json").exists()
