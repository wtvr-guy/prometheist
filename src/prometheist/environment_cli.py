"""Inspect the local embodiment and explicitly administer outbound consent."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from prometheist import db
from prometheist.artifact_journal import artifact_root
from prometheist.cognitive_store import get_record, put_record
from prometheist.environment_contracts import EnvironmentScan, MAX_DISCOVERY_BYTES, MONITOR_INTERVAL_SECONDS, content_digest
from prometheist.environment_runtime import (
    EnvironmentMonitor, capture_and_record, export_device_scan, import_device_scan,
    load_environment, local_host_id,
)
from prometheist.network_consent import (
    NetworkPurpose, check_connectivity, consent_proposal, grant_consent,
    load_consent, revoke_consent,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, prog="prometheist environment")
    parser.add_argument("--profile", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan", help="Persist one complete local inventory attempt and sensor sample")
    commands.add_parser("show", help="Read the persisted map, latest scan receipt and monitor status")
    watch = commands.add_parser("watch", help="Startup scan, then monitor until Ctrl+C; no LLM")
    watch.add_argument("--interval", type=float, default=MONITOR_INTERVAL_SECONDS)
    export = commands.add_parser("export-device", help="Create a local report on a cooperating device; never uploads")
    export.add_argument("output", type=Path)
    ingest = commands.add_parser("import-device", help="Explicitly attach a cooperating device's report")
    ingest.add_argument("report", type=Path)
    ingest.add_argument("--parent-id", type=UUID, required=True)
    for name in ("consent", "revoke"):
        command = commands.add_parser(name)
        command.add_argument("purpose", choices=[p.value for p in NetworkPurpose])
        command.add_argument("destination")
        if name == "consent":
            command.add_argument("--accept", help="Exact disclosure SHA-256 printed by a previous consent command")
    commands.add_parser("consents")
    probe = commands.add_parser("check-internet", help="Explicit HTTPS HEAD check requiring destination consent")
    probe.add_argument("destination")
    enroll = commands.add_parser("security-enroll", help="Review or accept the full implemented host-security capability set")
    enroll.add_argument("--accept")
    commands.add_parser("security-revoke", help="Revoke authority for future privileged security actions")
    firewall = commands.add_parser("firewall-plan", help="Write an exact, local-only egress rule plan; no changes applied")
    firewall.add_argument("output", type=Path)
    firewall.add_argument("--action", choices=["APPLY", "REMOVE"], default="APPLY")
    execute = commands.add_parser("firewall-execute", help="Apply a reviewed plan; requires Windows administrator rights")
    execute.add_argument("plan", type=Path)
    execute.add_argument("--accept", required=True)
    args = parser.parse_args(argv)
    if args.command == "security-enroll" and not args.profile:
        parser.error("security enrollment requires the single person's --profile")
    if args.profile:
        if args.command in {"consent", "revoke", "consents", "export-device", "security-enroll", "security-revoke", "firewall-plan", "firewall-execute"}:
            # Consent administration must work before a remote DB is authorized.
            from prometheist.imprinting import ImprintProfile, _outside_git
            import os
            path = _outside_git(args.profile)
            profile = ImprintProfile.model_validate_json(path.read_text(encoding="utf-8"))
            os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(path.parent / "artifacts")
            os.environ["PROMETHEIST_SUBJECT_ID"] = profile.subject_id
        else:
            from prometheist.imprinting import activate_imprint
            activate_imprint(args.profile)
    if args.command == "scan":
        result = capture_and_record()
    elif args.command == "show":
        with db.get_connection() as conn:
            host_id = local_host_id()
            mapping = load_environment(conn, host_id)
            attachments = []
            if mapping:
                for item in mapping.resources:
                    report = get_record(conn, "device_environment", str(item.resource.resource_id))
                    if report:
                        attachments.append({"parent_presence": item.presence.value, "report": report,
                                            "freshness": "DEVICE_REPORTED_SNAPSHOT"})
            result = {"map": mapping.model_dump(mode="json") if mapping else None,
                      "latest_scan": get_record(conn, "environment_latest", str(host_id)), "device_reports": attachments}
        health = artifact_root() / "operator" / "environment-monitor-health.json"
        result["monitor_health"] = json.loads(health.read_text()) if health.exists() else None
        with db.get_connection() as conn:
            result["security_posture"] = get_record(conn, "security_posture", str(host_id))
    elif args.command == "watch":
        monitor = EnvironmentMonitor(interval=args.interval)
        print(json.dumps(monitor.start(), indent=2))
        try:
            while not monitor.stop_event.wait(args.interval):
                pass
        except KeyboardInterrupt:
            pass
        finally:
            monitor.close()
        return
    elif args.command == "export-device":
        scan = export_device_scan(args.output)
        result = {"output": str(args.output), "scan_id": str(scan.scan_id), "transmitted": False}
    elif args.command == "import-device":
        if args.report.stat().st_size > MAX_DISCOVERY_BYTES:
            parser.error("device report exceeds the bounded import size")
        scan = EnvironmentScan.model_validate_json(args.report.read_bytes())
        with db.get_connection() as conn:
            result = import_device_scan(conn, parent_id=args.parent_id, scan=scan)
    elif args.command == "consent":
        purpose = NetworkPurpose(args.purpose)
        proposal = consent_proposal(args.destination, purpose)
        digest = content_digest(proposal)
        if args.accept is None:
            result = {"proposal": proposal, "accept_sha256": digest,
                      "next": "Review the destination and disclosure, then repeat this command with --accept and this SHA-256."}
        else:
            result = grant_consent(args.destination, purpose, accepted_digest=args.accept).model_dump(mode="json")
    elif args.command == "revoke":
        revoke_consent(args.destination, NetworkPurpose(args.purpose))
        result = {"revoked": True}
    elif args.command == "consents":
        result = load_consent().model_dump(mode="json")
    elif args.command == "security-enroll":
        from prometheist.security_posture import enroll_security, enrollment_proposal
        host_id = local_host_id()
        proposal = enrollment_proposal(profile.subject_id, host_id)
        result = ({"proposal": proposal, "accept_sha256": content_digest(proposal)} if args.accept is None else
                  enroll_security(profile.subject_id, host_id, accepted_digest=args.accept).model_dump(mode="json"))
    elif args.command == "security-revoke":
        from prometheist.security_posture import enrollment_path
        enrollment_path().unlink(missing_ok=True)
        result = {"revoked": True, "effect": "Future privileged security actions denied; existing firewall rules remain until a reviewed REMOVE plan. Stop the process to stop passive monitoring."}
    elif args.command == "firewall-plan":
        from prometheist.os_security import firewall_plan
        plan = firewall_plan(local_host_id(), action=args.action)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(plan.model_dump_json(indent=2) + "\n")
        result = {"plan": plan.model_dump(mode="json"), "accept_sha256": content_digest(plan.model_dump(mode="json")),
                  "saved_to": str(args.output)}
    elif args.command == "firewall-execute":
        from prometheist.os_security import FirewallPlan, execute_firewall_plan
        if args.plan.stat().st_size > MAX_DISCOVERY_BYTES:
            parser.error("firewall plan exceeds input bound")
        plan = FirewallPlan.model_validate_json(args.plan.read_bytes())
        result = execute_firewall_plan(plan, accepted_digest=args.accept)
    else:
        result = check_connectivity(args.destination)
        from uuid import uuid4
        with db.get_connection() as conn:
            put_record(conn, "connectivity_check", str(local_host_id()), result, revision=str(uuid4()))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
