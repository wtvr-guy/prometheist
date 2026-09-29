import json
import os
import subprocess
import sys
import threading
import time
from uuid import uuid4

import psutil
import pytest

from prometheist.gui_config import AppSettings, GUI_CONFIG_FILE_ENV
from prometheist.gui_jobs import JobBusy, JobManager
from prometheist.imprinting import ImprintProfile
from prometheist.operator_state import write_private_policy


def profile(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(ImprintProfile(subject_id="subject_test", database_url_env="PRIVATE_GUI_DB").model_dump_json())
    return path


def test_real_file_copy_job_snapshots_settings_and_finishes(tmp_path, monkeypatch):
    from prometheist.gui_files import FileManager, revision
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(root))
    files = FileManager(root)
    files.write_text("files", "original.txt", "independent persistent file")
    manager = JobManager(root, profile=profile(tmp_path))
    settings = AppSettings()
    result = manager.submit("file_copy", {"root": "files", "path": "original.txt", "destination_root": "files",
                                          "destination": "copied.txt", "revision": revision(files.workspace / "original.txt"), "copy": True}, settings)
    manager.thread.join(timeout=15)
    assert not manager.thread.is_alive()
    final = manager.get(result["id"])
    assert final["status"] == "completed", final
    assert (files.workspace / "copied.txt").read_text() == "independent persistent file"
    assert AppSettings.model_validate_json((manager.directory / result["id"] / "settings.json").read_text()) == settings
    assert not manager.active


def test_owned_process_cancellation_terminates_parent_and_child(tmp_path, monkeypatch):
    try:
        psutil.Process(os.getpid()).create_time()
    except psutil.NoSuchProcess:
        pytest.skip("Execution sandbox exposes host /proc to a different PID namespace; native process test runs in CI")
    manager = JobManager(tmp_path / "artifacts", profile=profile(tmp_path))
    real_popen = subprocess.Popen
    child_file = tmp_path / "child.json"
    script = (
        "import subprocess,sys,time,json; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); "
        f"ready=Path({str(child_file.with_suffix('.tmp'))!r}); ready.write_text(json.dumps({{'pid':p.pid}})); ready.replace(Path({str(child_file)!r})); "
        "time.sleep(120)"
    )
    seen = {}
    def launch(command, **kwargs):
        seen.update(kwargs["env"])
        return real_popen([sys.executable, "-c", script], **kwargs)
    monkeypatch.setattr(subprocess, "Popen", launch)
    result = manager.submit("pull", {"model": "test-model"}, AppSettings())
    deadline = time.monotonic() + 10
    while not child_file.exists() and time.monotonic() < deadline:
        time.sleep(.02)
    try:
        assert child_file.exists()
        assert seen[GUI_CONFIG_FILE_ENV].endswith("settings.json")
        child = psutil.Process(json.loads(child_file.read_text())["pid"])
        with pytest.raises(JobBusy):
            manager.submit("pull", {"model": "other"}, AppSettings())
        manager.cancel(result["id"])
        manager.thread.join(timeout=10)
        assert manager.get(result["id"])["status"] == "cancelled"
        assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
        assert manager.active is None
    finally:
        manager.close()


def test_restart_never_replays_an_interrupted_job(tmp_path):
    root = tmp_path / "artifacts"
    job_id = str(uuid4())
    path = root / "operator/app-jobs" / job_id / "job.json"
    write_private_policy(path, {"id": job_id, "status": "running", "pid": os.getpid(), "process_created_at": -1})
    manager = JobManager(root, profile=profile(tmp_path))
    assert manager.get(job_id)["status"] == "interrupted"
    assert manager.active is None and manager.process is None


def test_key_is_passed_only_in_child_environment(tmp_path, monkeypatch):
    manager = JobManager(tmp_path / "artifacts", profile=profile(tmp_path))
    complete = threading.Event()
    captured = {}
    class WaitingProcess:
        pid = os.getpid()
        def wait(self):
            complete.wait(timeout=10)
            return 0
    def launch(command, **kwargs):
        captured.update(command=command, env=kwargs["env"])
        return WaitingProcess()
    monkeypatch.setattr(subprocess, "Popen", launch)
    result = manager.submit("pull", {"model": "test-model"}, AppSettings(), api_key="test-memory-key")
    assert captured["env"]["OPENAI_API_KEY"] == "test-memory-key"
    assert "test-memory-key" not in " ".join(captured["command"])
    for path in (manager.directory / result["id"]).glob("*.json"):
        assert "test-memory-key" not in path.read_text()
    complete.set()
    manager.thread.join(timeout=5)


def test_history_poll_uses_bounded_startup_index(tmp_path, monkeypatch):
    from pathlib import Path
    from prometheist.gui_jobs import JOB_HISTORY_LIMIT
    root = tmp_path / "artifacts"
    for _ in range(JOB_HISTORY_LIMIT + 5):
        job_id = str(uuid4())
        write_private_policy(root / "operator/app-jobs" / job_id / "job.json", {"id":job_id, "status":"completed"})
    manager = JobManager(root, profile=profile(tmp_path))
    def no_scan(*args, **kwargs):
        raise AssertionError("Polling must not enumerate lifetime history")
    monkeypatch.setattr(Path, "glob", no_scan)
    assert len(manager.list()) == JOB_HISTORY_LIMIT
    assert manager.list() == manager.list()
