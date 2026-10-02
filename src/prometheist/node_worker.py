"""One disposable mobile intake/cognition job. Durable result precedes exit."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from prometheist.node_store import NodeStore


def main():
    profile, vault, event_id = sys.argv[1:]
    store = NodeStore(Path(vault))
    event = store.get(event_id)
    started = False
    try:
        from prometheist.imprinting import activate_imprint
        from prometheist.node_pairing import PairingRegistry

        identity = activate_imprint(Path(profile))
        device = next(
            (
                d
                for d in PairingRegistry(Path(vault), identity.subject_id).devices()
                if d["node_id"] == str(event.node_id)
            ),
            None,
        )
        if not device or device["revoked"]:
            store.transition(event_id, "failed", {"message": "Device authorization revoked"})
            return
        from prometheist import db
        from prometheist.node_backend import import_observation, run_chat

        os.environ.pop("OPENAI_API_KEY", None)
        with db.get_connection() as conn:
            locked = conn.execute(
                "SELECT pg_try_advisory_lock(hashtext('prometheist.gui.chat'))"
            ).fetchone()[0]
            conn.commit()
            if not locked:
                return  # Remains received; no cognition or canonical mutation began.
            import psutil

            store.transition(
                event_id,
                "started",
                {"pid": os.getpid(), "process_created_at": psutil.Process().create_time()},
            )
            started = True
            if event.kind == "chat":
                result = run_chat(conn, event, Path(profile))
                store.transition(event_id, "completed", result)
            else:
                store.transition(event_id, "imported", import_observation(conn, event))
    except Exception as exc:
        if started:
            # No raw provider exception, credentials or sensor payload in logs.
            store.transition(
                event_id,
                "failed",
                {
                    "message": f"Processing stopped ({type(exc).__name__}). Evidence retained; inspect laptop artifacts before resubmitting."
                },
            )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
