"""Local-only enrollment and revocation. Persist hashes, never bearer credentials."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from prometheist.node_contracts import PAIR_LIFETIME_SECONDS, PairRequest
from prometheist.operator_state import policy_lock, write_private_policy


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class PairingRegistry:
    def __init__(self, root: Path, subject: str):
        self.path = root / "devices.json"
        self.subject = subject

    def _read(self):
        value = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {"subject": self.subject, "codes": {}, "devices": {}}
        )
        if value["subject"] != self.subject:
            raise ValueError("Node store belongs to another identity")
        return value

    def issue(self, *, now=None):
        now = time.time() if now is None else now
        code = secrets.token_urlsafe(32)
        with policy_lock(self.path):
            value = self._read()
            value["codes"] = {k: v for k, v in value["codes"].items() if v["expires"] > now}
            value["codes"][secret_hash(code)] = {
                "expires": now + PAIR_LIFETIME_SECONDS,
                "node": None,
            }
            write_private_policy(self.path, value)
        return code

    def pair(self, request: PairRequest, *, now=None):
        now = time.time() if now is None else now
        with policy_lock(self.path):
            value = self._read()
            code = value["codes"].get(secret_hash(request.code))
            node = str(request.node_id)
            credential_hash = secret_hash(request.credential)
            if not code or code["expires"] <= now or code["node"] not in (None, node):
                raise PermissionError("Pairing code expired or already used")
            existing = value["devices"].get(node)
            if existing and (
                existing["revoked"] or not hmac.compare_digest(existing["hash"], credential_hash)
            ):
                raise PermissionError("Device identity cannot be replaced by pairing")
            code["node"] = node
            value["devices"][node] = {
                "hash": credential_hash,
                "label": request.label,
                "revoked": False,
            }
            write_private_policy(self.path, value)
        # A retry with the same client-generated credential repairs a lost reply.
        return {"subject_id": self.subject, "node_id": node}

    def authenticate(self, node: str, credential: str):
        if len(credential) != 43 or not credential.isascii():
            raise PermissionError("Device authentication failed")
        with policy_lock(self.path):
            record = self._read()["devices"].get(node)
        if (
            not record
            or record["revoked"]
            or not hmac.compare_digest(record["hash"], secret_hash(credential))
        ):
            raise PermissionError("Device authentication failed")

    def revoke(self, node: str):
        with policy_lock(self.path):
            value = self._read()
            value["devices"][node]["revoked"] = True
            write_private_policy(self.path, value)

    def devices(self):
        with policy_lock(self.path):
            return [
                {"node_id": k, "label": v["label"], "revoked": v["revoked"]}
                for k, v in self._read()["devices"].items()
            ]
