"""PostgreSQL integration: mobile observations use existing canonical intake."""

from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest

from prometheist import db
from prometheist.node_backend import import_observation, memory_page
from prometheist.node_contracts import NodeEvent


@pytest.mark.parametrize(
    "kind,data",
    [
        ("note", {"text": "Fictional walk after work"}),
        ("sensors", {"window_start": "2026-01-01T00:00:00Z", "sensors": [{"type": 5, "mean": 10}]}),
        ("location", {"latitude": 47.66, "longitude": -117.42, "precise": False}),
    ],
)
def test_node_intake_is_idempotent_and_keeps_provenance(kind, data):
    item = NodeEvent(
        event_id=uuid4(),
        node_id=uuid4(),
        sequence=1,
        observed_at=datetime.now(timezone.utc),
        kind=kind,
        data_json=json.dumps(data),
    )
    with db.get_connection() as conn:
        first = import_observation(conn, item)
        second = import_observation(conn, item)
        assert first == second
        row = conn.execute(
            "SELECT source,payload FROM events WHERE event_id=%s", (first["canonical_event_id"],)
        ).fetchone()
        assert str(item.node_id) in row[0]
        observation = row[1]["observation"]
        if kind == "note":
            assert observation == data["text"]
            assert memory_page(conn, 2**53 - 1)[0]["text"] == data["text"]
        else:
            assert observation["mobile_event"]["data_json"] == item.data_json
            assert observation["evidence_class"] == "device_observation_not_inferred_person_fact"
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_id=%s", (first["canonical_event_id"],)
            ).fetchone()[0]
            == 1
        )
