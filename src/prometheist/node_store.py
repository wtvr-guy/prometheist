"""Encrypted mobile inbox and immutable journal, with a rebuildable SQLite index.

Encryption protects evidence in the DB/journal; the local key still needs OS disk
encryption and account protection. SQLite contains IDs, order and status in clear.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from prometheist.node_contracts import NodeEvent, PAGE_SIZE
from prometheist.operator_state import policy_lock
from prometheist.artifact_journal import _fsync_parent

STATES = ("received", "started", "imported", "completed", "interrupted", "failed")
TERMINAL = STATES[2:]


class NodeStore:
    def __init__(self, root: Path, *, rebuild=False):
        self.root = root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock_path = root / "vault-lock"
        self.journal = root / "journal"
        self.journal.mkdir(mode=0o700, exist_ok=True)
        self.database_path = root / "inbox.sqlite3"
        key_path = root / "vault.key"
        with policy_lock(self.lock_path):
            if not key_path.exists():
                if any(self.journal.iterdir()) or (root / "inbox.sqlite3").exists():
                    raise ValueError("Vault key missing; restore the key, never replace it")
                with os.fdopen(
                    os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
                ) as f:
                    f.write(secrets.token_bytes(32))
                    f.flush()
                    os.fsync(f.fileno())
                _fsync_parent(key_path)
            self.aes = AESGCM(key_path.read_bytes())
            new_db = not (root / "inbox.sqlite3").exists()
            # Explicit recovery builds a fresh index before replacing even a
            # corrupt SQLite file. No canonical journal entry is overwritten.
            if rebuild:
                self.database_path = root / f"index-rebuild-{uuid4()}.sqlite3"
            try:
                self._initialize_index(rebuild or new_db)
                if rebuild:
                    os.replace(self.database_path, root / "inbox.sqlite3")
                    _fsync_parent(root / "inbox.sqlite3")
            finally:
                if rebuild:
                    self.database_path.unlink(missing_ok=True)
                    self.database_path = root / "inbox.sqlite3"

    def _initialize_index(self, replay):
        with self.connect() as db:
            db.executescript("""
                    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events(
                        id TEXT PRIMARY KEY,node TEXT NOT NULL,sequence INTEGER NOT NULL,
                        digest TEXT NOT NULL,record BLOB NOT NULL,state TEXT NOT NULL,
                        UNIQUE(node,sequence));
                    CREATE INDEX IF NOT EXISTS pending ON events(state,node,sequence);
                    CREATE TABLE IF NOT EXISTS feed(
                        cursor INTEGER PRIMARY KEY AUTOINCREMENT,node TEXT NOT NULL,
                        event TEXT NOT NULL,state TEXT NOT NULL,receipt BLOB NOT NULL,
                        UNIQUE(event,state));
                    CREATE INDEX IF NOT EXISTS node_feed ON feed(node,cursor);
                """)
            db.execute("INSERT OR IGNORE INTO meta VALUES('epoch',?)", (str(uuid4()),))
            self.epoch = db.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()[0]
            if replay:
                self._rebuild(db)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def seal(self, raw: bytes, identity: str):
        nonce = secrets.token_bytes(12)
        return nonce + self.aes.encrypt(nonce, raw, identity.encode())

    def unseal(self, raw: bytes, identity: str):
        return self.aes.decrypt(raw[:12], raw[12:], identity.encode())

    def _artifact(self, name: str, raw: bytes):
        path = self.journal / name
        if path.exists():
            if self.unseal(path.read_bytes(), name) != raw:
                raise ValueError("Conflicting immutable mobile evidence")
            return
        fd, tmp = tempfile.mkstemp(dir=self.journal)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(self.seal(raw, name))
                f.flush()
                os.fsync(f.fileno())
            os.link(tmp, path)  # Atomic publication; never truncate an existing record.
            _fsync_parent(path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def _insert_event(self, db, event):
        event_id = str(event.event_id)
        existing = db.execute("SELECT digest FROM events WHERE id=?", (event_id,)).fetchone()
        if existing and existing["digest"] != event.digest():
            raise ValueError("Event ID was reused with changed evidence")
        other = db.execute(
            "SELECT id FROM events WHERE node=? AND sequence=?",
            (str(event.node_id), event.sequence),
        ).fetchone()
        if other and other["id"] != event_id:
            raise ValueError("Node sequence was reused")
        db.execute(
            "INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?)",
            (
                event_id,
                str(event.node_id),
                event.sequence,
                event.digest(),
                self.seal(event.canonical(), event_id),
                "received",
            ),
        )

    def accept(self, event: NodeEvent):
        event_id = str(event.event_id)
        with policy_lock(self.lock_path), self.connect() as db:
            # Check sequence collision before publishing independent evidence.
            self._insert_event(db, event)
            self._artifact(f"{event_id}.event", event.canonical())
            self._transition(db, event_id, "received", {})
        return event_id

    def get(self, event_id):
        event_id = str(UUID(str(event_id)))
        with self.connect() as db:
            row = db.execute("SELECT record FROM events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            raise FileNotFoundError("Mobile event missing")
        return NodeEvent.model_validate_json(self.unseal(row["record"], event_id))

    def _transition(self, db, event_id, state, result):
        if state not in STATES:
            raise ValueError("Unknown mobile state")
        raw = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        name = f"{event_id}.{state}"
        self._artifact(name, raw)
        row = db.execute("SELECT node,state FROM events WHERE id=?", (event_id,)).fetchone()
        db.execute(
            "INSERT OR IGNORE INTO feed(node,event,state,receipt) VALUES(?,?,?,?)",
            (row["node"], event_id, state, self.seal(raw, name)),
        )
        # Repeated delivery cannot rewind a completed/started event to received.
        if STATES.index(state) >= STATES.index(row["state"]):
            db.execute("UPDATE events SET state=? WHERE id=?", (state, event_id))

    def transition(self, event_id, state, result=None):
        event_id = str(UUID(str(event_id)))
        with policy_lock(self.lock_path), self.connect() as db:
            self._transition(db, event_id, state, result or {})

    def pending(self):
        with self.connect() as db:
            return [
                r["id"]
                for r in db.execute(
                    "SELECT id FROM events WHERE state='received' ORDER BY node,sequence LIMIT ?",
                    (PAGE_SIZE,),
                )
            ]

    def interrupted(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM events WHERE state='started'")]
        for event_id in ids:
            started_path = self.journal / f"{event_id}.started"
            owner = json.loads(self.unseal(started_path.read_bytes(), started_path.name))
            if owner.get("pid"):
                import psutil

                try:
                    process = psutil.Process(owner["pid"])
                    if (
                        process.create_time() == owner.get("process_created_at")
                        and "prometheist.node_worker" in process.cmdline()
                        and event_id in process.cmdline()
                    ):
                        continue  # The gateway died, but its owned worker survived.
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    continue  # Unknown process authority cannot justify a retry.
            # Repair crash after journal publication but before DB commit first.
            repaired = False
            for state in TERMINAL:
                path = self.journal / f"{event_id}.{state}"
                if path.exists():
                    self.transition(
                        event_id, state, json.loads(self.unseal(path.read_bytes(), path.name))
                    )
                    repaired = True
            if not repaired:
                self.transition(
                    event_id,
                    "interrupted",
                    {
                        "message": "Laptop stopped during processing. Inspect its artifacts before submitting again."
                    },
                )

    def page(self, node, after):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM feed WHERE node=? AND cursor>? ORDER BY cursor LIMIT ?",
                (node, after, PAGE_SIZE),
            ).fetchall()
        return [
            {
                "cursor": r["cursor"],
                "event_id": r["event"],
                "state": r["state"],
                "result": json.loads(self.unseal(r["receipt"], f"{r['event']}.{r['state']}")),
            }
            for r in rows
        ]

    def _rebuild(self, db):
        # Explicit recovery/startup of a missing index; not a poll-time corpus scan.
        for path in sorted(self.journal.glob("*.event")):
            self._insert_event(
                db, NodeEvent.model_validate_json(self.unseal(path.read_bytes(), path.name))
            )
        for row in db.execute("SELECT id FROM events").fetchall():
            for state in STATES:
                name = f"{row['id']}.{state}"
                path = self.journal / name
                if path.exists():
                    self._transition(
                        db, row["id"], state, json.loads(self.unseal(path.read_bytes(), name))
                    )
            # Repair power loss between the event and its received receipt.
            self._transition(db, row["id"], "received", {})
