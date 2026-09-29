"""Disposable GUI job process; personal cognition uses the guarded worker pipeline."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from uuid import UUID

from prometheist.gui_config import job_settings
from prometheist.operator_state import write_private_policy


def run(directory, profile):
    from prometheist import db
    from prometheist.imprinting import activate_imprint
    from prometheist.gui_models import pull_model, validate_local_selection
    job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
    action, payload = job["action"], job["payload"]
    settings = job_settings()

    def report(value):
        write_private_policy(directory / "progress.json", value)

    if action == "file_copy":
        from prometheist.artifact_journal import artifact_root
        from prometheist.gui_files import FileManager
        return FileManager(artifact_root()).relocate(payload["root"], payload["path"],
            payload["destination_root"], payload["destination"], payload["revision"], copy=True, progress=report)
    if action == "pull":
        return pull_model(settings.ollama_url, payload["model"], report)
    if action == "firewall":
        from prometheist.os_security import FirewallPlan, execute_firewall_plan
        return execute_firewall_plan(FirewallPlan.model_validate(payload["plan"]),
                                     accepted_digest=payload["accepted_digest"])
    if action != "chat":
        raise ValueError("Unregistered job action")
    report({"status": "Checking the private profile"})
    activate_imprint(profile)
    from prometheist.contract_registry import STAGE_CONTRACTS
    selections = {settings.selection_for(stage).model_dump_json(): settings.selection_for(stage)
                  for stage, contract in STAGE_CONTRACTS.items() if contract.kinds and stage.startswith("V2_")}
    for selection in selections.values():
        if selection.provider == "ollama":
            report({"status": "Checking " + selection.model})
            validate_local_selection(settings.ollama_url, selection)
        else:
            from prometheist.network_consent import NetworkPurpose, require_destination
            from prometheist.openai_transport import OPENAI_ORIGIN
            require_destination(OPENAI_ORIGIN, NetworkPurpose.MODEL)
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("Connect your OpenAI API key before starting this task")
    from prometheist.chat_startup import reset_chat_execution_state
    from prometheist.percept_response_runtime import handle_percept_in_worker_processes
    with db.get_connection() as conn:
        acquired = conn.execute("SELECT pg_try_advisory_lock(hashtext('prometheist.gui.chat'))").fetchone()[0]
        conn.commit()
        if not acquired:
            raise ValueError("Another Prometheist GUI is already running a chat task")
        scheduler_key = "gui-chat"
        reset_chat_execution_state(conn, scheduler_key=scheduler_key)
        text = handle_percept_in_worker_processes(conn, payload["text"], UUID(payload["conversation_id"]),
            scheduler_key=scheduler_key, progress=lambda stage: report({"status": "Cognitive worker", "stage": stage}))
    return {"text": text, "conversation_id": payload["conversation_id"]}


def main():
    from prometheist.cli import _configure_utf8_streams
    _configure_utf8_streams()
    directory, profile = map(Path, sys.argv[1:])
    try:
        result = run(directory, profile)
        write_private_policy(directory / "result.json", {"result": result})
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        for name in ("OPENAI_API_KEY", "DATABASE_URL"):
            secret = os.environ.get(name)
            if secret:
                message = message.replace(secret, "[redacted]")
        write_private_policy(directory / "result.json", {"error": message[:2000]})
        print(message, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
