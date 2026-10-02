"""Narrow authenticated phone gateway. Desktop administration is never exposed."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from prometheist.node_contracts import (
    MAX_BODY_BYTES,
    PROTOCOL,
    PairRequest,
    SyncRequest,
    https_origin,
)
from prometheist.node_pairing import PairingRegistry
from prometheist.node_store import NodeStore


class IntakeRunner:
    def __init__(self, store, profile):
        self.store, self.profile = store, profile
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.process = None
        self.thread = threading.Thread(target=self.run, daemon=True, name="mobile-intake")

    def run(self):
        self.store.interrupted()
        while not self.stop.is_set():
            for event_id in self.store.pending():
                if self.stop.is_set():
                    break
                env = dict(os.environ)
                env.pop("OPENAI_API_KEY", None)
                self.process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "prometheist.node_worker",
                        str(self.profile),
                        str(self.store.root),
                        event_id,
                    ],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                while self.process.poll() is None and not self.stop.wait(0.5):
                    pass
                if self.stop.is_set() and self.process.poll() is None:
                    import psutil

                    try:
                        parent = psutil.Process(self.process.pid)
                        parent.suspend()
                        children = parent.children(recursive=True)
                        for child in children:
                            try:
                                child.kill()
                            except psutil.NoSuchProcess:
                                pass
                        parent.kill()
                    except psutil.NoSuchProcess:
                        pass
                    self.process.wait(timeout=5)
                self.process = None
                # Reconcile a killed worker without repeating ambiguous model effects.
                self.store.interrupted()
            # Safety tunable: unavailable laptop DB does not create a tight loop.
            self.wake.wait(10)
            self.wake.clear()

    def close(self):
        self.stop.set()
        self.wake.set()
        self.thread.join(timeout=10)


def create_node_app(root: Path, subject: str, public_url: str, *, profile=None):
    public_url = https_origin(public_url)
    host = urlsplit(public_url).netloc.lower()
    store, registry = NodeStore(root), PairingRegistry(root, subject)
    runner = IntakeRunner(store, profile) if profile else None

    @asynccontextmanager
    async def lifespan(app):
        if runner:
            runner.thread.start()
        try:
            yield
        finally:
            if runner:
                runner.close()

    app = FastAPI(
        title="Prometheist phone gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.store, app.state.registry = store, registry

    @app.middleware("http")
    async def boundary(request, call_next):
        # Reject browser origins, DNS rebinding and a public proxy accidentally
        # forwarding a different Host. Native app has no Origin/cookie authority.
        if request.headers.get("host", "").lower() != host or request.headers.get("origin"):
            return JSONResponse({"detail": "Wrong gateway origin"}, status_code=403)
        if request.url.path != "/v1/pair":
            try:
                node = str(UUID(request.headers.get("x-node-id", "")))
                header = request.headers.get("authorization", "")
                if not header.startswith("Bearer "):
                    raise PermissionError()
                registry.authenticate(node, header[7:])
                request.state.node_id = node
            except ValueError, PermissionError:
                return JSONResponse({"detail": "Device authentication failed"}, status_code=401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    async def body(request, cls):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "JSON is required")
        raw = bytearray()
        async for part in request.stream():
            if len(raw) + len(part) > MAX_BODY_BYTES:
                raise HTTPException(413, "Request too large")
            raw.extend(part)
        try:
            return cls.model_validate_json(bytes(raw))
        except ValidationError, ValueError, RecursionError:
            raise HTTPException(422, "Invalid mobile contract") from None

    @app.post("/v1/pair")
    async def pair(request: Request):
        payload = await body(request, PairRequest)
        try:
            result = registry.pair(payload)
        except PermissionError:
            raise HTTPException(401, "Pairing code expired, revoked or already used") from None
        return {**result, "protocol": PROTOCOL, "public_url": public_url}

    @app.post("/v1/sync")
    async def sync(request: Request):
        payload = await body(request, SyncRequest)
        if str(payload.node_id) != request.state.node_id or payload.subject_id != subject:
            raise HTTPException(403, "Identity mismatch")
        if any(event.node_id != payload.node_id for event in payload.events):
            raise HTTPException(403, "Cannot submit another node's evidence")
        try:
            accepted = [store.accept(event) for event in payload.events]
        except ValueError:
            raise HTTPException(
                409, "Conflicting mobile evidence; nothing was overwritten"
            ) from None
        after = payload.after if payload.epoch == store.epoch else 0
        changes = store.page(request.state.node_id, after)
        if runner:
            runner.wake.set()
        return {
            "protocol": PROTOCOL,
            "subject_id": subject,
            "epoch": store.epoch,
            "accepted": accepted,
            "changes": changes,
            "cursor": changes[-1]["cursor"] if changes else after,
            "backend_enabled": runner is not None,
        }

    @app.get("/v1/memory")
    def memory(before: int = 2**53 - 1):
        if not profile:
            raise HTTPException(503, "Laptop memory unavailable")
        if before < 1 or before > 2**53 - 1:
            raise HTTPException(422, "Invalid memory cursor")
        try:
            from prometheist.imprinting import activate_imprint
            from prometheist.node_backend import memory_page
            from prometheist import db

            activate_imprint(profile)
            with db.get_connection() as conn:
                items = memory_page(conn, before)
        except Exception:
            raise HTTPException(
                503, "Laptop memory unavailable; local phone history is retained"
            ) from None
        return {
            "subject_id": subject,
            "items": items,
            "before": items[-1]["sequence"] if items else before,
        }

    return app
