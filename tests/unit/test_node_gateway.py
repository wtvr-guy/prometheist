"""Mobile privacy, retries, identity isolation, durable recovery, LLM=null."""

from datetime import datetime, timezone
import json
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from fastapi.testclient import TestClient
import pytest

from prometheist.node_contracts import NodeEvent, PairRequest, https_origin
from prometheist.node_pairing import PairingRegistry
from prometheist.node_server import create_node_app
from prometheist.node_store import NodeStore

URL = "https://laptop.example.ts.net"


def event(node=None, sequence=1, **changes):
    return NodeEvent(
        event_id=uuid4(),
        node_id=node or uuid4(),
        sequence=sequence,
        observed_at=datetime.now(timezone.utc),
        kind="note",
        data_json='{"text":"PRIVATE MEMORY moon"}',
        **changes,
    )


def paired(tmp_path):
    app = create_node_app(tmp_path, "subject_001", URL)
    client = TestClient(app, base_url=URL)
    node, credential = uuid4(), "z" * 43
    code = app.state.registry.issue()
    request = dict(code=code, node_id=str(node), credential=credential, label="test phone")
    assert client.post("/v1/pair", json=request).status_code == 200
    client.headers.update({"X-Node-ID": str(node), "Authorization": f"Bearer {credential}"})
    return app, client, node, request


def sync(client, node, events=(), **values):
    return client.post(
        "/v1/sync",
        json={
            "node_id": str(node),
            "subject_id": "subject_001",
            "events": [e.model_dump(mode="json") for e in events],
            **values,
        },
    )


def test_expiring_single_use_pairing_retry_and_revocation(tmp_path):
    registry = PairingRegistry(tmp_path, "subject_001")
    code = registry.issue(now=1000)
    request = PairRequest(code=code, node_id=uuid4(), credential="x" * 43, label="Phone")
    assert registry.pair(request, now=1100) == registry.pair(request, now=1101)
    with pytest.raises(PermissionError):
        registry.pair(request.model_copy(update={"node_id": uuid4()}), now=1102)
    with pytest.raises(PermissionError):
        registry.pair(request, now=1600)
    registry.authenticate(str(request.node_id), request.credential)
    registry.revoke(str(request.node_id))
    with pytest.raises(PermissionError):
        registry.authenticate(str(request.node_id), request.credential)
    with pytest.raises(PermissionError):
        registry.pair(request, now=1103)
    raw = registry.path.read_text()
    assert request.code not in raw and request.credential not in raw


def test_duplicate_delivery_conflicts_and_cursor_replay(tmp_path):
    app, client, node, _ = paired(tmp_path)
    item = event(node)
    first = sync(client, node, [item]).json()
    assert first["accepted"] == [str(item.event_id)]
    assert not first["backend_enabled"]
    second = sync(client, node, [item], epoch=first["epoch"], after=first["cursor"]).json()
    assert second["changes"] == []
    assert app.state.store.get(item.event_id).data_json == item.data_json
    conflict = item.model_copy(update={"data_json": '{"text":"rewritten"}'})
    assert sync(client, node, [conflict]).status_code == 409
    assert sync(client, node, [event(node)]).status_code == 409  # same sequence
    app.state.store.transition(str(item.event_id), "completed", {"text": "reply"})
    assert sync(client, node, epoch="lost-index", after=9999).json()["changes"]
    retry = sync(client, node, [item]).json()
    assert retry["changes"][-1]["state"] == "completed"
    assert not app.state.store.pending()


def test_gateway_never_exposes_admin_or_other_nodes(tmp_path):
    app, client, node, _ = paired(tmp_path)
    assert client.get("/api/settings").status_code == 404
    assert client.get("/v1/memory").status_code == 503  # no database, LLM=null
    assert sync(client, node, [event()]).status_code == 403
    assert sync(client, node, subject_id="subject_other").status_code == 403
    assert client.post("/v1/sync", json={}, headers={"Origin": URL}).status_code == 403
    assert client.get("/v1/memory", headers={"Host": "evil.example"}).status_code == 403
    app.state.registry.revoke(str(node))
    assert sync(client, node).status_code == 401


def test_encrypted_database_journal_and_rebuild(tmp_path):
    store = NodeStore(tmp_path)
    item = event()
    store.accept(item)
    store.transition(str(item.event_id), "started")
    store.transition(str(item.event_id), "completed", {"text": "PRIVATE RESPONSE"})
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"PRIVATE MEMORY" not in path.read_bytes()
            assert b"PRIVATE RESPONSE" not in path.read_bytes()
    old_epoch = store.epoch
    (tmp_path / "inbox.sqlite3").unlink()
    restored = NodeStore(tmp_path)
    assert restored.epoch != old_epoch
    assert restored.get(item.event_id) == item
    assert restored.page(str(item.node_id), 0)[-1]["result"]["text"] == "PRIVATE RESPONSE"
    assert restored.pending() == []


def test_tamper_key_loss_and_interrupted_work_fail_closed(tmp_path):
    store = NodeStore(tmp_path)
    item = event()
    store.accept(item)
    store.transition(str(item.event_id), "started")
    store.interrupted()
    assert store.page(str(item.node_id), 0)[-1]["state"] == "interrupted"
    assert store.pending() == []
    path = store.journal / f"{item.event_id}.event"
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    with pytest.raises(InvalidTag):
        NodeStore(tmp_path, rebuild=True)
    (tmp_path / "vault.key").unlink()
    with pytest.raises(ValueError, match="key missing"):
        NodeStore(tmp_path)


def test_rebuild_recovers_corrupt_index_without_touching_evidence(tmp_path):
    store = NodeStore(tmp_path)
    item = event()
    store.accept(item)
    files = {p.name: p.read_bytes() for p in store.journal.iterdir()}
    (tmp_path / "inbox.sqlite3").write_bytes(b"corrupt sqlite projection")
    recovered = NodeStore(tmp_path, rebuild=True)
    assert recovered.get(item.event_id) == item
    assert files == {p.name: p.read_bytes() for p in store.journal.iterdir()}


def test_pending_order_survives_index_rebuild(tmp_path):
    store = NodeStore(tmp_path)
    first = event(sequence=1)
    second = event(node=first.node_id, sequence=2)
    store.accept(second)
    store.accept(first)
    expected = [str(first.event_id), str(second.event_id)]
    assert store.pending() == expected
    assert NodeStore(tmp_path, rebuild=True).pending() == expected


def test_partial_status_publication_repaired_before_interruption(tmp_path, monkeypatch):
    store = NodeStore(tmp_path)
    item = event()
    store.accept(item)
    store.transition(str(item.event_id), "started")
    # Simulate fsynced result followed by a crash before the SQLite commit.
    store._artifact(f"{item.event_id}.completed", b'{"text":"durable reply"}')
    store.interrupted()
    assert store.page(str(item.node_id), 0)[-1]["state"] == "completed"


def test_all_published_terminal_receipts_replay_in_order(tmp_path):
    store = NodeStore(tmp_path)
    item = event()
    store.accept(item)
    store.transition(str(item.event_id), "started")
    store._artifact(f"{item.event_id}.completed", b'{"text":"durable reply"}')
    store._artifact(f"{item.event_id}.failed", b'{"message":"later commit failure"}')
    store.interrupted()
    before = store.page(str(item.node_id), 0)
    rebuilt = NodeStore(tmp_path, rebuild=True).page(str(item.node_id), 0)
    assert [r["state"] for r in before] == [r["state"] for r in rebuilt]
    assert [r["state"] for r in before][-2:] == ["completed", "failed"]


def test_payload_validation_and_bounded_stream_body(tmp_path):
    _, client, node, _ = paired(tmp_path)
    assert (
        client.post(
            "/v1/sync",
            content=b"x" * (2 * 1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert client.post("/v1/sync", json={"unexpected": "must be rejected"}).status_code == 422
    with pytest.raises(ValueError):
        event().model_copy(update={}).model_validate(
            {**event().model_dump(), "data_json": '{"number":NaN}'}
        )
    with pytest.raises(ValueError):
        NodeEvent.model_validate({**event().model_dump(), "observed_at": "2026-01-01T00:00:00"})
    for url in (
        "http://laptop",
        "https://a:pass@host",
        "https://host/path",
        "https://host?token=1",
    ):
        with pytest.raises(ValueError):
            https_origin(url)


def test_node_isolation_in_feed(tmp_path):
    store = NodeStore(tmp_path)
    a, b = event(), event()
    store.accept(a)
    store.accept(b)
    assert {r["event_id"] for r in store.page(str(a.node_id), 0)} == {str(a.event_id)}
    assert {r["event_id"] for r in store.page(str(b.node_id), 0)} == {str(b.event_id)}


def test_exact_data_string_survives_cross_language_numbers(tmp_path):
    store = NodeStore(tmp_path)
    item = event().model_copy(
        update={"data_json": '{ "reading":1.0000000000000002, "text":"α\\nβ" }'}
    )
    store.accept(item)
    assert store.get(item.event_id).data_json == item.data_json
    assert json.loads(store.get(item.event_id).data_json)["text"] == "α\nβ"
