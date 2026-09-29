"""Authenticated loopback control plane. No model-generated command execution."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from prometheist.gui_config import AppSettings, ModelSelection, load_settings, save_settings, settings_revision
from prometheist.gui_jobs import JobBusy, JobManager
from prometheist import gui_models
from prometheist.environment_contracts import content_digest
from prometheist.network_consent import NetworkPurpose, consent_proposal, grant_consent, load_consent, revoke_consent
from prometheist.operator_state import write_private_policy

MAX_REQUEST_BYTES = 2097152
SESSION_COOKIE = "prometheist_session"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Handshake(Input):
    token: str = Field(max_length=200)


class SettingsUpdate(Input):
    settings: AppSettings
    revision: str


class ChatInput(Input):
    text: str = Field(min_length=1, max_length=32768)
    conversation_id: UUID
    selection: ModelSelection | None = None


class ModelInput(Input):
    model: str


class DeleteInput(ModelInput):
    confirmation: str


class KeyInput(Input):
    key: str = Field(min_length=1, max_length=512)


class ConsentInput(Input):
    purpose: NetworkPurpose
    destination: str
    accepted_digest: str | None = None


class Acceptance(Input):
    accepted_digest: str


class FirewallInput(Input):
    plan: dict
    accepted_digest: str


class AppState:
    def __init__(self, root: Path, profile: Path, *, token=None):
        from prometheist.imprinting import ImprintProfile
        self.root, self.profile_path = root, profile
        self.profile = ImprintProfile.model_validate_json(profile.read_text(encoding="utf-8"))
        self.settings = load_settings(root)
        self.jobs = JobManager(root, profile=profile)
        self.token = token or secrets.token_urlsafe(32)
        self.session = secrets.token_urlsafe(32)
        self.token_used = False
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        self.ready = False
        self.health = {"status": "starting", "message": "Checking the private runtime"}

    def start(self):
        self.thread = threading.Thread(target=self._monitor, name="prometheist-app-monitor", daemon=True)
        self.thread.start()

    def _monitor(self):
        from prometheist.imprinting import activate_imprint
        from prometheist.environment_runtime import local_host_id, record_environment_scan
        from prometheist.environment_providers import scan_environment
        from prometheist.security_posture import assess_security
        from prometheist import db
        first = True
        while not self.stop.is_set():
            try:
                database_active = self.ready
                if not database_active:
                    try:
                        activate_imprint(self.profile_path)
                        database_active = True
                    except Exception as exc:
                        self.health = {"status": "setup", "message": f"Private database unavailable ({type(exc).__name__}). Set {self.profile.database_url_env} and apply the database migrations.", "database_env": self.profile.database_url_env}
                scan = scan_environment(local_host_id(), reason="STARTUP" if first else "POLL")
                result = {"scan": scan.model_dump(mode="json"),
                          "security_posture": assess_security(scan).model_dump(mode="json"),
                          "persisted_to_database": False}
                if database_active:
                    try:
                        with db.get_connection() as conn:
                            result["receipt"] = record_environment_scan(conn, scan)
                        result["persisted_to_database"] = True
                        self.ready = True
                        self.health = {"status": "ready", "message": "Private runtime ready"}
                    except Exception as exc:
                        self.ready = False
                        self.health = {"status": "error", "message": f"Inventory could not be recorded in PostgreSQL ({type(exc).__name__}); local observation retained"}
                write_private_policy(self.root / "operator" / "app-environment.json", result)
            except Exception as exc:
                self.health = {"status": "error", "message": f"Host scan failed ({type(exc).__name__}); previous observations may be stale"}
            first = False
            self.wake.wait(self.settings.monitor_interval_seconds)
            self.wake.clear()
        self.health = {"status": "stopped", "message": "Monitoring stopped"}

    def close(self):
        self.stop.set()
        self.wake.set()
        self.jobs.close()
        if self.thread:
            self.thread.join(timeout=5)
        self.api_key = ""


def create_app(root: Path, profile: Path, *, port: int, token=None, start_monitor=True):
    state = AppState(root, profile, token=token)
    origin = f"http://127.0.0.1:{port}"

    @asynccontextmanager
    async def lifespan(app):
        if start_monitor:
            state.start()
        try:
            yield
        finally:
            state.close()

    app = FastAPI(title="Prometheist", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.control = state

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.headers.get("host") != f"127.0.0.1:{port}":
            return JSONResponse({"detail": "Unrecognized local host"}, status_code=403)
        supplied_origin = request.headers.get("origin")
        if supplied_origin and supplied_origin != origin:
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
        if request.method not in ("GET", "HEAD"):
            if supplied_origin != origin:
                return JSONResponse({"detail": "An exact local Origin is required"}, status_code=403)
            try:
                length = int(request.headers.get("content-length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_REQUEST_BYTES:
                return JSONResponse({"detail": "Missing or oversized request length"}, status_code=413)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "JSON requests are required"}, status_code=415)
        if request.url.path.startswith("/api/"):
            candidate = request.cookies.get(SESSION_COOKIE, "")
            if not hmac.compare_digest(candidate, state.session):
                return JSONResponse({"detail": "Open the app using its launch link"}, status_code=401)
        response = await call_next(request)
        response.headers.update({
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        })
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409 if isinstance(exc, JobBusy) else 400)

    @app.exception_handler(PermissionError)
    async def denied(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(FileExistsError)
    async def exists(request, exc):
        return JSONResponse({"detail": "The destination already exists; choose a different name"}, status_code=409)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Requested local record was not found"}, status_code=404)

    import httpx

    @app.exception_handler(httpx.HTTPError)
    async def unavailable(request, exc):
        return JSONResponse({"detail": "Model service is unavailable or rejected the request. Check the endpoint, model and service status."}, status_code=502)

    @app.post("/auth/handshake")
    def handshake(body: Handshake):
        with state.lock:
            if state.token_used or not hmac.compare_digest(body.token, state.token):
                raise HTTPException(401, "Launch token is invalid or already used; reopen from the running app")
            state.token_used = True
            response = JSONResponse({"authenticated": True})
            response.set_cookie(SESSION_COOKIE, state.session, httponly=True, samesite="strict", path="/")
            return response

    @app.get("/api/bootstrap")
    def bootstrap():
        from prometheist.contract_registry import STAGE_CONTRACTS
        return {"subject": state.profile.subject_id, "health": state.health,
                "settings": state.settings.model_dump(mode="json"), "revision": settings_revision(state.settings),
                "openai_connected": bool(state.api_key), "private_root": str(root.parent),
                "routes": {name: contract.role for name, contract in STAGE_CONTRACTS.items() if contract.kinds},
                "active_job": state.jobs.active}

    @app.put("/api/settings")
    def update_settings(body: SettingsUpdate):
        with state.lock:
            if body.revision != settings_revision(state.settings):
                raise HTTPException(409, "Settings changed in another window. Reload before saving.")
            save_settings(root, body.settings)
            state.settings = body.settings
            state.wake.set()
        return {"settings": body.settings.model_dump(mode="json"), "revision": settings_revision(body.settings)}

    @app.get("/api/settings/schema")
    def settings_schema():
        return AppSettings.model_json_schema()

    @app.get("/api/models")
    def models():
        return {"models": gui_models.installed_models(state.settings.ollama_url)}

    @app.get("/api/models/details")
    def details(model: str):
        return gui_models.model_details(state.settings.ollama_url, model)

    @app.get("/api/models/parameters")
    def parameters(provider: Literal["ollama", "openai"], model: str):
        from prometheist.model_parameters import parameter_catalog
        return parameter_catalog(provider, model)

    @app.get("/api/models/search")
    def search(q: str = ""):
        if len(q) > 200:
            raise ValueError("Search query is too long")
        return {"models": gui_models.search_catalog(q)}

    @app.post("/api/models/pull")
    def pull(body: ModelInput):
        ModelSelection(model=body.model)
        from prometheist.network_consent import require_destination
        require_destination(gui_models.DOWNLOAD_ORIGIN, NetworkPurpose.MODEL_DOWNLOAD)
        return state.jobs.submit("pull", body.model_dump(), state.settings)

    @app.delete("/api/models")
    def delete(body: DeleteInput):
        with state.jobs.lock:
            if state.jobs.active:
                raise JobBusy("Wait for the current job before deleting model weights")
            if body.confirmation != body.model:
                raise ValueError("Deletion confirmation must match the model name")
            gui_models.delete_model(state.settings.ollama_url, body.model)
        return {"deleted": body.model}

    @app.post("/api/openai/key")
    def connect(body: KeyInput):
        key = body.key.strip()
        if not key or any(ch.isspace() for ch in key):
            raise ValueError("API key must not contain whitespace")
        state.api_key = key
        return {"connected": True, "storage": "server memory until the app exits"}

    @app.delete("/api/openai/key")
    def disconnect():
        state.api_key = ""
        return {"connected": False, "effect": "Future jobs cannot use this key. Cancel an active job to stop its future requests."}

    @app.get("/api/openai/models")
    def cloud_models():
        return {"models": gui_models.openai_models(state.api_key)}

    @app.get("/api/consents")
    def consents():
        return load_consent(root).model_dump(mode="json")

    @app.post("/api/consents/proposal")
    def proposal(body: ConsentInput):
        value = consent_proposal(body.destination, body.purpose)
        return {"proposal": value, "accepted_digest": content_digest(value)}

    @app.post("/api/consents")
    def consent(body: ConsentInput):
        return grant_consent(body.destination, body.purpose, accepted_digest=body.accepted_digest, root=root).model_dump(mode="json")

    @app.delete("/api/consents")
    def revoke(body: ConsentInput):
        revoke_consent(body.destination, body.purpose, root=root)
        return {"revoked": True}

    @app.post("/api/chat")
    def chat(body: ChatInput):
        if not state.ready:
            raise ValueError(state.health["message"])
        if not body.text.strip():
            raise ValueError("Message is empty")
        settings = state.settings
        if body.selection:
            settings = AppSettings.model_validate({**settings.model_dump(), "selection": body.selection.model_dump()})
        return state.jobs.submit("chat", {"text": body.text, "conversation_id": str(body.conversation_id)},
                                 settings, api_key=state.api_key)

    @app.get("/api/jobs")
    def jobs():
        return {"jobs": state.jobs.list(), "active": state.jobs.active, "limit": 200}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: UUID):
        return state.jobs.get(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: UUID):
        return state.jobs.cancel(str(job_id))

    @app.get("/api/jobs/{job_id}/log")
    def job_log(job_id: UUID):
        # Bounded local diagnostic read, never an arbitrary path from the browser.
        path = state.jobs.directory / str(job_id) / "worker.log"
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 65536))
            value = stream.read(65536).decode("utf-8", errors="replace")
        for secret in (state.api_key, os.environ.get("DATABASE_URL", ""), os.environ.get("OPENAI_API_KEY", "")):
            if secret:
                value = value.replace(secret, "[redacted]")
        return {"text": value, "tail_bytes": 65536}

    @app.get("/api/environment")
    def environment():
        path = root / "operator" / "app-environment.json"
        return {"health": state.health, "observation": json.loads(path.read_text(encoding="utf-8")) if path.exists() else None}

    @app.post("/api/environment/scan")
    def scan():
        state.wake.set()
        return {"requested": True}

    @app.get("/api/registries")
    def registries():
        from prometheist.contract_registry import contract_manifest
        return contract_manifest()

    @app.get("/api/security/enrollment")
    def security():
        from prometheist.environment_runtime import local_host_id
        from prometheist.security_posture import enrollment_proposal, enrollment_path
        value = enrollment_proposal(state.profile.subject_id, local_host_id())
        path = enrollment_path(root)
        return {"proposal": value, "accepted_digest": content_digest(value),
                "enrollment": json.loads(path.read_text(encoding="utf-8")) if path.exists() else None}

    @app.post("/api/security/enrollment")
    def enroll(body: Acceptance):
        from prometheist.environment_runtime import local_host_id
        from prometheist.security_posture import enroll_security
        return enroll_security(state.profile.subject_id, local_host_id(), accepted_digest=body.accepted_digest, root=root).model_dump(mode="json")

    @app.delete("/api/security/enrollment")
    def unenroll():
        from prometheist.security_posture import revoke_security
        revoke_security(root=root)
        return {"revoked": True}

    @app.get("/api/security/firewall")
    def firewall(action: Literal["APPLY", "REMOVE"] = "APPLY"):
        from prometheist.environment_runtime import local_host_id
        from prometheist.os_security import firewall_plan
        plan = firewall_plan(local_host_id(), action=action).model_dump(mode="json")
        return {"plan": plan, "accepted_digest": content_digest(plan)}

    @app.post("/api/security/firewall")
    def apply_firewall(body: FirewallInput):
        from prometheist.os_security import FirewallPlan
        plan = FirewallPlan.model_validate(body.plan)
        if content_digest(plan.model_dump(mode="json")) != body.accepted_digest:
            raise ValueError("Firewall acceptance does not match the plan")
        return state.jobs.submit("firewall", body.model_dump(), state.settings)

    from prometheist.gui_file_api import file_router
    app.include_router(file_router(state))

    assets = Path(__file__).with_name("web")
    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    return app
