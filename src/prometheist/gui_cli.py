"""Launch the local control app with a single-use browser authentication link."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import threading
import webbrowser

import uvicorn


def main(argv=None):
    parser = argparse.ArgumentParser(prog="prometheist gui", description=__doc__)
    parser.add_argument("--profile", type=Path, help="Private imprint profile.json; a new subject_001 profile is prepared in local app data by default")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    from prometheist.imprinting import ImprintProfile, _outside_git, initialize_imprint
    profile_path = args.profile
    if profile_path is None:
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
        root = base / "Prometheist" / "subject_001"
        profile_path = root / "profile.json"
        if not profile_path.exists():
            initialize_imprint(root, "subject_001", "PROMETHEIST_PRIVATE_DATABASE_URL")
    profile_path = _outside_git(profile_path)
    profile = ImprintProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(profile_path.parent / "artifacts")
    os.environ["PROMETHEIST_SUBJECT_ID"] = profile.subject_id
    os.environ.setdefault("PGCONNECT_TIMEOUT", "5")
    from prometheist.environment_runtime import local_host_id
    local_host_id()  # Validate private storage before starting any scan/server.
    from prometheist.gui_server import create_app
    from prometheist.gui_instance import instance_lock
    with instance_lock(profile_path.parent / "artifacts"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind(("127.0.0.1", args.port))
            server_socket.listen()
            app = create_app(profile_path.parent / "artifacts", profile_path, port=args.port)
            url = f"http://127.0.0.1:{args.port}/#token={app.state.control.token}"
            print("Prometheist is local to this computer. Keep this one-use launch link private:\n" + url, flush=True)
            if not args.no_browser:
                threading.Timer(1, lambda: webbrowser.open(url)).start()
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False))
            server.run(sockets=[server_socket])


if __name__ == "__main__":
    main()
