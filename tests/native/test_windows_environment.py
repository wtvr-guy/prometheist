"""Read-only native Windows contract checks; no database or personal output."""
import json
import os
from pathlib import Path
import platform
import subprocess
from uuid import uuid4

import pytest

from prometheist.environment_contracts import ScanStatus
from prometheist.environment_providers import PROVIDER_REGISTRY, windows_inventory

pytestmark = pytest.mark.skipif(platform.system() != "Windows", reason="native Windows API contract")


def test_bundled_powershell_scripts_parse():
    import prometheist.environment_providers as providers
    executable = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    # Application-owned constant command; script paths are supplied as JSON data.
    command = "$paths = [Console]::In.ReadToEnd() | ConvertFrom-Json; foreach ($p in $paths) { $errors=$null; $tokens=$null; [System.Management.Automation.Language.Parser]::ParseFile($p,[ref]$tokens,[ref]$errors) | Out-Null; if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 } }"
    paths = [str(Path(providers.__file__).with_name(name)) for name in ("windows_environment.ps1", "windows_firewall.ps1")]
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", command],
                            input=json.dumps(paths).encode(), capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout.decode(errors="replace")


def test_native_inventory_has_real_core_windows_evidence():
    reports = {r.provider: r for r in windows_inventory(uuid4())}
    assert reports.keys() == {key for key, c in PROVIDER_REGISTRY.items() if c.platform == "Windows"}
    # Sensors, TPM, Secure Boot, Defender and encryption may be unavailable on a
    # hosted VM. Core device/CPU queries must actually execute, not just parse.
    for name in ("windows.system", "windows.cpu", "windows.memory", "windows.pnp", "windows.network", "windows.security.privileges"):
        assert reports[name].status in {ScanStatus.COMPLETE, ScanStatus.PARTIAL}, (name, reports[name].diagnostic)
        assert reports[name].resources, name


def test_native_managed_firewall_roundtrip(tmp_path, monkeypatch):
    """Only GitHub's disposable Windows runner opts in to rule mutations."""
    if os.environ.get("PROMETHEIST_TEST_FIREWALL") != "1":
        pytest.skip("set PROMETHEIST_TEST_FIREWALL=1 only on an authorized disposable Windows host")
    from prometheist.environment_contracts import content_digest
    from prometheist.environment_runtime import local_host_id
    from prometheist.os_security import execute_firewall_plan, firewall_plan
    from prometheist.security_posture import enroll_security, enrollment_proposal
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path))
    monkeypatch.setenv("PROMETHEIST_SUBJECT_ID", "subject_ci")
    host_id = local_host_id()
    enroll_security("subject_ci", host_id, accepted_digest=content_digest(enrollment_proposal("subject_ci", host_id)))
    apply = firewall_plan(host_id)
    remove = firewall_plan(host_id, action="REMOVE")
    try:
        receipt = execute_firewall_plan(apply, accepted_digest=content_digest(apply.model_dump(mode="json")))
        assert receipt["status"] == "VERIFIED_RULE_STATE"
    finally:
        execute_firewall_plan(remove, accepted_digest=content_digest(remove.model_dump(mode="json")))
