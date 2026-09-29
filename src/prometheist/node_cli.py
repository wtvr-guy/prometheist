"""Private Android-node pairing, revocation and loopback gateway."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main(argv=None):
    from prometheist.imprinting import ImprintProfile, _outside_git
    from prometheist.node_pairing import PairingRegistry
    from prometheist.node_contracts import PROTOCOL, https_origin

    parser = argparse.ArgumentParser(prog="prometheist node", description=__doc__)
    parser.add_argument("command", choices=("pair", "serve", "devices", "revoke", "rebuild"))
    default = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
        / "Prometheist/subject_001/profile.json"
    )
    parser.add_argument("--profile", type=Path, default=default)
    parser.add_argument("--url", help="HTTPS URL supplied by tailscale serve")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--node-id")
    parser.add_argument(
        "--inbox-only",
        action="store_true",
        help="Encrypted sync with LLM=null; no PostgreSQL intake",
    )
    args = parser.parse_args(argv)
    profile_path = _outside_git(args.profile)
    profile = ImprintProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    root = profile_path.parent / "phone-node"
    registry = PairingRegistry(root, profile.subject_id)
    if args.command in {"pair", "serve"}:
        if not args.url:
            parser.error("--url is required (private HTTPS tunnel origin)")
        args.url = https_origin(args.url)
    if args.command == "pair":
        print(
            json.dumps(
                {
                    "protocol": PROTOCOL,
                    "url": args.url,
                    "subject_id": profile.subject_id,
                    "code": registry.issue(),
                },
                indent=2,
            )
        )
        print("Paste the JSON into the phone within 10 minutes. Keep it private.")
    elif args.command == "devices":
        print(json.dumps(registry.devices(), indent=2))
    elif args.command == "revoke":
        if not args.node_id:
            parser.error("--node-id is required")
        registry.revoke(args.node_id)
        print("Device revoked. Historical evidence retained.")
    elif args.command == "rebuild":
        from prometheist.node_store import NodeStore
        from prometheist.gui_instance import instance_lock

        with instance_lock(root):
            NodeStore(root, rebuild=True)
        print("Encrypted journal replayed into the phone inbox index.")
    else:
        if not 1024 <= args.port <= 65535:
            parser.error("port must be 1024–65535")
        from prometheist.gui_instance import instance_lock
        from prometheist.node_server import create_node_app
        import uvicorn

        os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(profile_path.parent / "artifacts")
        os.environ.setdefault("PGCONNECT_TIMEOUT", "5")
        with instance_lock(root):
            app = create_node_app(
                root,
                profile.subject_id,
                args.url,
                profile=None if args.inbox_only else profile_path,
            )
            print(
                f"Phone gateway on 127.0.0.1:{args.port}; expose only through your private tunnel."
            )
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=args.port,
                access_log=False,
                proxy_headers=False,
                limit_concurrency=8,
                timeout_keep_alive=5,
            )


if __name__ == "__main__":
    main()
