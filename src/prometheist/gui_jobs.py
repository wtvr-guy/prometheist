"""One owned foreground job at a time, with durable receipts and cancellation."""
from __future__ import annotations

from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from uuid import UUID, uuid4

import psutil

from prometheist.operator_state import write_private_policy

JOB_HISTORY_LIMIT = 200
PROCESS_STOP_TIMEOUT_SECONDS = 5
ACTIVE_STATES = frozenset({"running", "cancelling"})


def now():
    return datetime.now(timezone.utc).isoformat()


class JobBusy(ValueError):
    pass


class JobManager:
    def __init__(self, root: Path, *, profile: Path):
        self.directory = root / "operator" / "app-jobs"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.profile = profile
        self.lock = threading.RLock()
        self.process = None
        self.active = None
        self.thread = None
        # One startup scan; polling never enumerates lifetime history.
        paths = list(self.directory.glob("*/job.json"))
        self.recent_ids = [path.parent.name for path in heapq.nlargest(
            JOB_HISTORY_LIMIT, paths, key=lambda path: (path.stat().st_mtime_ns, path.parent.name))]
        # A receipt is never replayed on restart; canonical events may already exist.
        for path in paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["status"] in ACTIVE_STATES:
                owned = self._owned_process(record)
                if owned is not None and self.active is None:
                    self.process, self.active = owned, record["id"]
                    self.thread = threading.Thread(target=self._wait, args=(owned, record, path.parent), daemon=True)
                    self.thread.start()
                    continue
                record.update(status="interrupted", finished_at=now(),
                              error="App stopped before completion. Inspect artifacts before retrying; input may already be recorded.")
                write_private_policy(path, record)

    @staticmethod
    def _owned_process(record):
        try:
            process = psutil.Process(record["pid"])
            if process.create_time() != record["process_created_at"]:
                return None
            command = process.cmdline()
            if "prometheist.gui_worker" not in command or not any(record["id"] in arg for arg in command):
                return None
            return process
        except (KeyError, psutil.Error):
            return None

    def get(self, job_id):
        job_id = str(UUID(str(job_id)))
        path = self.directory / job_id / "job.json"
        if not path.exists():
            raise FileNotFoundError("Job not found")
        record = json.loads(path.read_text(encoding="utf-8"))
        progress = path.with_name("progress.json")
        if progress.exists():
            record["progress"] = json.loads(progress.read_text(encoding="utf-8"))
        admission = path.with_name("admission.json")
        if admission.exists():
            plan = json.loads(admission.read_text(encoding="utf-8"))
            record["admission"] = {key: plan.get(key) for key in ("task", "route_reason", "status", "reasons", "stages", "specialist_offer", "openai_offer", "routing_exclusions")}
        return record

    def list(self):
        with self.lock:
            return [self.get(job_id) for job_id in self.recent_ids]

    def submit(self, action, payload, settings, *, api_key=""):
        with self.lock:
            if self.active is not None:
                raise JobBusy("Finish or cancel the current job before starting another")
            job_id = str(uuid4())
            directory = self.directory / job_id
            directory.mkdir(mode=0o700)
            record = {"id": job_id, "action": action, "status": "running", "created_at": now(),
                      "finished_at": None, "payload": payload,
                      "selection": settings.selection.model_dump(mode="json"),
                      "settings": settings.model_dump(mode="json"), "result": None, "error": None}
            write_private_policy(directory / "job.json", record)
            self.recent_ids = [job_id, *self.recent_ids][:JOB_HISTORY_LIMIT]
            config_path = directory / "settings.json"
            write_private_policy(config_path, settings.model_dump(mode="json"))
            environment = {**os.environ, **settings.worker_environment(config_path), "PYTHONIOENCODING": "utf-8"}
            if api_key:
                environment["OPENAI_API_KEY"] = api_key
            else:
                environment.pop("OPENAI_API_KEY", None)
            # Secrets are inherited by the owned worker, never command-line arguments/files.
            descriptor = os.open(directory / "worker.log", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as log:
                    process = subprocess.Popen([sys.executable, "-m", "prometheist.gui_worker",
                                                str(directory), str(self.profile)], env=environment,
                                               stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                               start_new_session=os.name != "nt")
            except Exception:
                record.update(status="failed", error="Could not launch job process", finished_at=now())
                write_private_policy(directory / "job.json", record)
                raise
            record["pid"] = process.pid
            try:
                record["process_created_at"] = psutil.Process(process.pid).create_time()
            except psutil.NoSuchProcess:
                record["process_created_at"] = None
            write_private_policy(directory / "job.json", record)
            self.process, self.active = process, job_id
            self.thread = threading.Thread(target=self._wait, args=(process, record, directory), daemon=True)
            self.thread.start()
            return record

    def _wait(self, process, record, directory):
        code = process.wait()
        with self.lock:
            current = self.get(record["id"])
            result_path = directory / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
            if code is None and isinstance(process, psutil.Process):
                code = 0 if "result" in result and "error" not in result else 1
            cancelled = current["status"] == "cancelling"
            current.update(status="cancelled" if cancelled else "completed" if code == 0 else "failed",
                           finished_at=now(), result=result.get("result"),
                           error=("Cancelled. Any canonical input already recorded is retained; no automatic retry."
                                  if cancelled else result.get("error") or
                                  (f"Worker exited with code {code}; inspect its local log" if code else None)))
            write_private_policy(directory / "job.json", current)
            self.process = self.active = None

    def cancel(self, job_id):
        with self.lock:
            if str(job_id) != self.active or self.process is None:
                raise ValueError("This job is no longer running")
            record = self.get(job_id)
            record["status"] = "cancelling"
            write_private_policy(self.directory / str(job_id) / "job.json", record)
            process = self.process
            # Capture identities before signalling; psutil guards against PID reuse.
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                parent.suspend()  # prevent the orchestrator from launching another stage
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
                _, alive = psutil.wait_procs(children, timeout=PROCESS_STOP_TIMEOUT_SECONDS)
                for child in alive:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass
            return record

    def close(self):
        if self.active:
            self.cancel(self.active)
        if self.thread:
            self.thread.join(timeout=PROCESS_STOP_TIMEOUT_SECONDS)
