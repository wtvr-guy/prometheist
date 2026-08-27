from __future__ import annotations

import inspect
import json
import uuid

import psycopg
import pytest

from jit_agent import admin, db, event_store
from jit_agent.models import EventType


@pytest.fixture
def conn():
    connection = db.get_connection()
    yield connection
    connection.close()


def _record_fact(conn, text: str = "constitutional admin fact"):
    conversation_id = event_store.start_conversation(conn)
    recorded = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test-admin",
        payload={"text": text},
        payload_text=text,
    )
    return conversation_id, recorded


def test_admin_control_plane_has_no_llm_dependency():
    source = inspect.getsource(admin)
    assert "jit_agent.llm" not in source
    assert "OllamaClient" not in source


def test_llm_free_inspection_reads_canonical_history(conn):
    conversation_id, recorded = _record_fact(conn)
    summary = admin.inspect_state(conn)
    history = admin.inspect_history(conn, rows=10, conversation_id=conversation_id)
    assert summary["llm_required"] is False
    assert summary["conversations"] == 1
    assert summary["events"] == 1
    assert summary["max_global_seq"] == recorded.global_seq
    assert [row["event_id"] for row in history] == [str(recorded.event_id)]
    assert history[0]["payload"]["text"] == "constitutional admin fact"


def test_canonical_events_reject_update_delete_and_truncate_without_erasure_authority(conn):
    _, recorded = _record_fact(conn)
    with pytest.raises(psycopg.errors.RaiseException):
        with conn.cursor() as cur:
            cur.execute("UPDATE events SET source = 'mutated' WHERE event_id = %s", (recorded.event_id,))
    conn.rollback()
    with pytest.raises(psycopg.errors.RaiseException):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE event_id = %s", (recorded.event_id,))
    conn.rollback()
    with pytest.raises(psycopg.errors.RaiseException):
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE events CASCADE")
    conn.rollback()
    assert event_store.get_event_by_id(conn, recorded.event_id) is not None


def test_export_erasure_restore_round_trip_preserves_canonical_identity(conn, tmp_path):
    conversation_id, recorded = _record_fact(conn, "portable sovereign fact")
    output = tmp_path / "prometheist-export.json"
    exported = admin.export_bundle(conn, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exported["row_count"] >= 2
    assert payload["digest"] == exported["digest"]
    assert payload["tables"]["events"][0]["event_id"] == str(recorded.event_id)

    with pytest.raises(ValueError):
        admin.erase_all_user_data(conn, confirmation="yes")
    erased = admin.erase_all_user_data(conn, confirmation=admin.ERASE_ALL_CONFIRMATION)
    assert erased["previous_events"] == 1
    assert admin.inspect_state(conn)["events"] == 0

    restored = admin.restore_bundle(conn, output, confirmation=admin.RESTORE_CONFIRMATION)
    assert restored["digest"] == exported["digest"]
    history = admin.inspect_history(conn, rows=10, conversation_id=conversation_id)
    assert history[0]["event_id"] == str(recorded.event_id)
    assert history[0]["payload"]["text"] == "portable sovereign fact"

    next_event = event_store.record_event(
        conn,
        conversation_id=conversation_id,
        correlation_id=uuid.uuid4(),
        event_type=EventType.USER_PROMPT,
        source="test-admin",
        payload={"text": "after restore"},
        payload_text="after restore",
    )
    assert next_event.conversation_seq == recorded.conversation_seq + 1
    assert next_event.global_seq > recorded.global_seq


def test_restore_rejects_tampered_export(conn, tmp_path):
    _record_fact(conn)
    output = tmp_path / "prometheist-export.json"
    admin.export_bundle(conn, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["tables"]["events"][0]["source"] = "tampered"
    output.write_text(json.dumps(payload), encoding="utf-8")
    admin.erase_all_user_data(conn, confirmation=admin.ERASE_ALL_CONFIRMATION)
    with pytest.raises(ValueError, match="digest mismatch"):
        admin.restore_bundle(conn, output, confirmation=admin.RESTORE_CONFIRMATION)
