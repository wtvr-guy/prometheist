"""Mobile adapters into the existing canonical store and guarded local cognition."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid5

from prometheist.node_contracts import NodeEvent


def import_observation(conn, event: NodeEvent):
    from prometheist.percept_intake import ingest_percept, install_source_policy
    from prometheist.perception import PerceptKind, PerceptModality, PerceptSource
    from prometheist.percept_triage import SourcePolicy
    from prometheist.percept_adapters import preserve_media

    data = json.loads(event.data_json)
    source_id = f"android:{event.node_id}:{event.kind}"
    modality = PerceptModality.STRUCTURED
    observation = {
        "mobile_event": event.model_dump(mode="json"),
        "evidence_class": "device_observation_not_inferred_person_fact",
    }
    if event.kind in {"note", "chat"}:
        text = data.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 32768:
            raise ValueError("Note/chat text must contain 1–32768 characters")
        # Text remains searchable without claiming that a sensor measures intent.
        modality = PerceptModality.TEXT
        observation = text
    elif event.kind in {"photo", "audio"}:
        expected = "image/jpeg" if event.kind == "photo" else "audio/wav"
        if data.get("mime_type") != expected:
            raise ValueError("Unsupported mobile media format")
        raw = base64.b64decode(data.get("base64", ""), validate=True)
        if not raw or len(raw) > 512 * 1024:
            raise ValueError("Mobile media exceeds the intake bound")
        from prometheist.artifact_journal import artifact_root

        temporary_root = artifact_root() / "mobile-import"
        temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=temporary_root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
            observation = preserve_media(
                Path(name),
                mime_type=expected,
                description=f"Deliberate Android capture; source mobile event {event.event_id}",
            ).model_dump(mode="json")
        finally:
            Path(name).unlink(missing_ok=True)
        modality = PerceptModality.IMAGE if event.kind == "photo" else PerceptModality.AUDIO
    policy = SourcePolicy(
        source_id=source_id,
        kind=PerceptKind.EXTERNAL_OBSERVATION,
        modalities=(modality,),
        self_model_evidence=True,
    )
    install_source_policy(conn, policy)
    percept = ingest_percept(
        conn,
        source=PerceptSource(
            source_id=source_id, kind=policy.kind, modality=modality, interface="android-node"
        ),
        observation=observation,
        observed_at=event.observed_at,
        delivery_id=str(event.event_id),
        correlation_id=event.event_id,
        conversation_id=uuid5(event.node_id, "mobile-observations"),
    )
    return {
        "canonical_event_id": str(percept.source_event_id),
        "message": "Admitted to laptop memory; observation is evidence, not an inferred identity claim.",
    }


def run_chat(conn, event: NodeEvent, profile: Path):
    """Use the same model selection, resource admission and worker stages as desktop.

    Mobile evidence cannot authorize a cloud provider, arbitrary endpoint, shell,
    settings edit or device enrollment. Existing laptop API keys are not inherited.
    """
    from prometheist.gui_config import AppSettings, load_settings, local_ollama
    from prometheist.model_admission import prepare_task
    from prometheist.operator_state import write_private_policy
    from prometheist.chat_startup import reset_chat_execution_state
    from prometheist.percept_response_runtime import handle_percept_in_worker_processes

    root = profile.parent / "artifacts"
    settings = load_settings(root)
    if not local_ollama(settings) or any(
        s.provider != "ollama" for s in [settings.selection, *settings.routes.values()]
    ):
        raise PermissionError(
            "Phone cognition requires local Ollama routes; cloud routes are disabled for mobile evidence"
        )
    data = json.loads(event.data_json)
    text = data.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 32768:
        raise ValueError("Chat text must contain 1–32768 characters")
    plan = prepare_task(settings, text, "auto", fallback="default")
    if plan.status != "eligible":
        raise RuntimeError("Local model unavailable or resource admission denied")
    settings = AppSettings.model_validate(
        {**settings.model_dump(), "routes": {**settings.routes, **plan.stages}}
    )
    if any(s.provider != "ollama" for s in settings.routes.values()):
        raise PermissionError("Remote models are disabled for the phone node")
    path = root / "operator" / "node-settings" / f"{event.event_id}.json"
    write_private_policy(path, settings.model_dump(mode="json"))
    os.environ.update(settings.worker_environment(path))
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ["PROMETHEIST_GUI_MODEL_MEMORY_FLOOR_MIB"] = str(plan.required_memory_mib)
    os.environ["PROMETHEIST_GUI_MODEL_CPU_UNITS"] = str(plan.required_cpu_units)
    scheduler_key = "android-chat"
    reset_chat_execution_state(conn, scheduler_key=scheduler_key)
    response = handle_percept_in_worker_processes(
        conn,
        text,
        uuid5(event.node_id, "mobile-chat"),
        correlation_id=event.event_id,
        scheduler_key=scheduler_key,
    )
    return {
        "text": response,
        "source_event_id": str(event.event_id),
        "model": plan.stages["V2_RESPOND"].model,
    }


def memory_page(conn, before: int, limit=25):
    from psycopg.rows import dict_row

    # Device is provenance, not a semantic wall: desktop and mobile text appear.
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """SELECT event_id,global_seq,event_type,source,created_at,payload_text,payload
            FROM events WHERE global_seq < %s
              AND event_type IN ('USER_PROMPT','INTERACTION_RESPONSE','PERCEPT_OBSERVATION')
            ORDER BY global_seq DESC LIMIT %s""",
            (before, limit),
        )
        rows = cursor.fetchall()
    result = []
    for row in rows:
        text = (
            row["payload_text"] or row["payload"].get("text") or row["payload"].get("response_text")
        )
        if not isinstance(text, str):
            text = "Structured observation (inspect canonical evidence on laptop)"
        result.append(
            {
                "event_id": str(row["event_id"]),
                "sequence": row["global_seq"],
                "observed_at": row["created_at"].isoformat(),
                "kind": row["event_type"],
                "text": text[:16384],
                "truncated": len(text) > 16384,
                "source": row["source"],
            }
        )
    return result
