"""Operator-owned Windows Firewall policy. Never called by a model or worker."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Literal
from uuid import UUID

import psutil

from prometheist.artifact_journal import _atomic_write_json, artifact_root
from prometheist.environment_contracts import DISCOVERY_TIMEOUT_SECONDS, MAX_DISCOVERY_BYTES, content_digest
from prometheist.percept_context import FrozenRecord

FIREWALL_GROUP = "Prometheist local privacy v1"
# Explicit block rules override allow rules. Exclude loopback from the block
# itself; an allow-loopback exception to block-all would not work.
NON_LOOPBACK_ADDRESSES = (
    "0.0.0.0-126.255.255.255", "128.0.0.0-255.255.255.255",
    "::", "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
)
FIREWALL_IMPACT = (
    "Blocks non-loopback outbound IPv4/IPv6 for exactly the listed executable paths, on all profiles. "
    "This includes LAN services and consented remote destinations. Local PostgreSQL/Ollama remain usable. "
    "All applications sharing these Python executables are affected. Phone Link and other executables "
    "are outside these rules. Child executables, OS DNS services and local forwarding services are not "
    "contained by these rules. Removing the rules restores the previous OS policy, not permission in "
    "Prometheist's consent registry. No global firewall settings or third-party rules are changed."
)


class FirewallRule(FrozenRecord):
    name: str
    program: str


class FirewallPlan(FrozenRecord):
    schema_version: Literal["windows-firewall-plan/v1"] = "windows-firewall-plan/v1"
    host_id: UUID
    action: Literal["APPLY", "REMOVE"]
    group: Literal["Prometheist local privacy v1"] = FIREWALL_GROUP
    rules: tuple[FirewallRule, ...]
    remote_addresses: tuple[str, ...] = NON_LOOPBACK_ADDRESSES
    impact: str = FIREWALL_IMPACT


def runtime_programs() -> tuple[str, ...]:
    """Include the venv launcher and the real process image, when different."""
    return tuple(sorted({os.path.normcase(str(Path(path).resolve()))
                         for path in (sys.executable, psutil.Process().exe())}))


def firewall_plan(host_id: UUID, *, action="APPLY") -> FirewallPlan:
    if platform.system() != "Windows":
        raise RuntimeError("Windows Firewall management requires Windows")
    rules = tuple(FirewallRule(name="Prometheist-" + content_digest({"host": str(host_id), "program": path}),
                              program=path) for path in runtime_programs())
    return FirewallPlan(host_id=host_id, action=action, rules=rules)


def execute_firewall_plan(plan: FirewallPlan, *, accepted_digest: str, run=subprocess.run) -> dict:
    from prometheist.environment_runtime import local_host_id
    data = plan.model_dump(mode="json")
    if content_digest(data) != accepted_digest:
        raise ValueError("acceptance must match the exact reviewed firewall plan")
    # Independently recompute every mutable field. A tampered file cannot supply
    # arbitrary rule names, applications, PowerShell, or relaxed address scopes.
    if plan != firewall_plan(local_host_id(), action=plan.action):
        raise ValueError("firewall plan does not match this host, runtime and managed policy")
    from prometheist.security_posture import require_security_capability
    # Removal is always available with an exact reviewed plan, including after
    # enrollment revocation, so the owner cannot be locked out of undoing it.
    if plan.action == "APPLY":
        require_security_capability(os.environ.get("PROMETHEIST_SUBJECT_ID", ""), plan.host_id, "firewall.local_only")
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    command = [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
               str(Path(__file__).with_name("windows_firewall.ps1"))]
    receipt = {"plan_sha256": accepted_digest, "action": plan.action,
               "observed_at": datetime.now(timezone.utc).isoformat(), "traffic_tested": False}
    try:
        result = run(command, input=json.dumps(data).encode(), capture_output=True,
                     timeout=DISCOVERY_TIMEOUT_SECONDS, check=False)
        if len(result.stdout) > MAX_DISCOVERY_BYTES:
            raise RuntimeError("firewall response exceeded bound")
        response = json.loads(result.stdout.decode("utf-8-sig"))
        receipt["result"] = response
        if result.returncode or response.get("status") != "VERIFIED_RULE_STATE":
            raise RuntimeError(response.get("error", "Firewall change was not verified; inspect the local receipt"))
    except Exception as exc:
        receipt["status"] = "FAILED_OR_INCOMPLETE"
        receipt["error_type"] = type(exc).__name__
        _atomic_write_json(artifact_root() / "operator" / "firewall-receipt.json", receipt)
        raise
    receipt["status"] = "VERIFIED_RULE_STATE"
    _atomic_write_json(artifact_root() / "operator" / "firewall-receipt.json", receipt)
    return receipt
