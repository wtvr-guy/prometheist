"""Deterministic defensive findings and explicit, revocable host enrollment."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from prometheist.artifact_journal import _atomic_write_json, artifact_root
from prometheist.environment_contracts import EnvironmentScan, ScanStatus, content_digest
from prometheist.percept_context import FrozenRecord

# This registry describes actual implemented authority, not aspirational powers.
# Future capabilities require a new reviewed enrollment, even for the same host.
SECURITY_CAPABILITIES = MappingProxyType({
    "host.observe": "Read local hardware, sensors and OS-exposed connected-device descriptors continuously while running.",
    "security.assess": "Read built-in protection status and emit deterministic local findings; no malware verdict is implied.",
    "firewall.local_only": "Apply or remove reviewed rules for the exact runtime executable paths; requires OS administrator rights.",
})
SECURITY_DISCLOSURE = (
    "You assert ownership or administration authority over this host. Prometheist prioritizes your protection "
    "within the listed implemented capabilities. Inventory and findings remain local unless a separate "
    "destination consent authorizes transmission. Firewall changes additionally use an exact reviewed plan. "
    "Enrollment does not grant OS privileges, unlock phone internals, authorize other owners' systems, "
    "enable penetration testing, or confer future capabilities. You can revoke enrollment locally. "
    "Coverage requires the process and computer to be running; there is no guarantee against all threats."
)


class SecurityEnrollment(FrozenRecord):
    schema_version: Literal["security-enrollment/v1"] = "security-enrollment/v1"
    subject_id: str
    host_id: UUID
    primary_objective: Literal["PROTECT_ENROLLED_PERSON"] = "PROTECT_ENROLLED_PERSON"
    capabilities: tuple[str, ...]
    disclosure_sha256: str
    granted_at: datetime


def enrollment_proposal(subject_id: str, host_id: UUID):
    return {"schema_version": "security-enrollment/v1", "subject_id": subject_id, "host_id": str(host_id),
            "primary_objective": "PROTECT_ENROLLED_PERSON", "capabilities": dict(SECURITY_CAPABILITIES),
            "disclosure": SECURITY_DISCLOSURE, "duration": "until explicitly revoked"}


def enrollment_path(root: Path | None = None):
    return (root or artifact_root()) / "operator" / "security-enrollment.json"


def enroll_security(subject_id, host_id, *, accepted_digest, root=None):
    proposal = enrollment_proposal(subject_id, host_id)
    if content_digest(proposal) != accepted_digest:
        raise ValueError("enrollment requires acceptance of the exact host, subject, capabilities and disclosure")
    result = SecurityEnrollment(subject_id=subject_id, host_id=host_id, capabilities=tuple(SECURITY_CAPABILITIES),
        disclosure_sha256=accepted_digest, granted_at=datetime.now(timezone.utc))
    _atomic_write_json(enrollment_path(root), result.model_dump(mode="json"))
    enrollment_path(root).chmod(0o600)
    return result


def require_security_capability(subject_id, host_id, capability, *, root=None):
    path = enrollment_path(root)
    if path.exists():
        record = SecurityEnrollment.model_validate_json(path.read_text(encoding="utf-8"))
        if (record.subject_id == subject_id and record.host_id == host_id
                and record.disclosure_sha256 == content_digest(enrollment_proposal(subject_id, host_id))
                and capability in record.capabilities and capability in SECURITY_CAPABILITIES):
            return
    raise PermissionError("host security capability requires current explicit enrollment for this subject")


class PostureFinding(FrozenRecord):
    rule_id: str
    provider: str
    resource_id: UUID | None = None
    property: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    observed: str
    meaning: str


class SecurityAssessment(FrozenRecord):
    schema_version: Literal["security-posture/v1"] = "security-posture/v1"
    host_id: UUID
    scan_id: UUID
    observed_at: datetime
    findings: tuple[PostureFinding, ...]
    coverage: Literal["OS_POSTURE_ONLY"] = "OS_POSTURE_ONLY"


POSTURE_RULES = MappingProxyType({
    "firewall.enabled": ("windows.security.firewall", "Enabled", True, "Firewall profile or managed rule should be enabled."),
    "defender.antivirus": ("windows.security.defender", "AntivirusEnabled", True, "Built-in antivirus availability; another installed product may replace Defender."),
    "defender.realtime": ("windows.security.defender", "RealTimeProtectionEnabled", True, "Defender real-time protection status; this is not a malware scan."),
    "defender.signatures": ("windows.security.defender", "DefenderSignaturesOutOfDate", False, "Defender reports whether its signatures are out of date."),
    "secure_boot.enabled": ("windows.security.secure_boot", "Enabled", True, "UEFI Secure Boot state."),
    "tpm.ready": ("windows.security.tpm", "Ready", True, "TPM readiness; no encryption keys are accessed."),
    "encryption.protected": ("windows.security.encryption", "ProtectionStatus", "On", "Volume encryption protection status; support depends on OS edition and hardware."),
})


def assess_security(scan: EnvironmentScan) -> SecurityAssessment:
    findings = []
    reports = {r.provider: r for r in scan.reports}
    if scan.platform == "Windows":
        for rule_id, (provider, prop, expected, meaning) in POSTURE_RULES.items():
            report = reports.get(provider)
            if not report or report.status is not ScanStatus.COMPLETE or not report.resources:
                findings.append(PostureFinding(rule_id=rule_id, provider=provider, property=prop, status="UNKNOWN",
                    observed=report.status.value if report else "NOT_REPORTED", meaning=meaning))
                continue
            for resource in report.resources:
                value = resource.properties.get(prop)
                normalized = str(value).casefold() if value is not None else None
                status = "UNKNOWN" if normalized is None else "PASS" if normalized == str(expected).casefold() else "FAIL"
                findings.append(PostureFinding(rule_id=rule_id, provider=provider, resource_id=resource.resource_id,
                    property=prop, status=status, observed=str(value), meaning=meaning))
    else:
        findings.append(PostureFinding(rule_id="platform.coverage", provider="platform.security", property="coverage",
            status="UNKNOWN", observed="INVENTORY_ONLY", meaning="No automated posture rules for this OS yet; inspect reported security metadata."))
    return SecurityAssessment(host_id=scan.host_id, scan_id=scan.scan_id, observed_at=scan.observed_at,
                              findings=tuple(sorted(findings, key=lambda f: (f.rule_id, str(f.resource_id)))))
