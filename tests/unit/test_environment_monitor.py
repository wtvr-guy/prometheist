import json

import pytest

from prometheist.environment_runtime import EnvironmentMonitor


def test_startup_finishes_before_monitor_thread_and_close_records_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path))
    calls = []
    receipt = {"observed_at": "2026-09-29T00:00:00+00:00", "scan_id": "fixture"}
    monitor = EnvironmentMonitor(capture=lambda **kw: calls.append(kw["reason"]) or receipt)
    assert monitor.start() == receipt
    assert calls == ["STARTUP"]
    monitor.close()
    assert not monitor.thread.is_alive()
    assert json.loads((tmp_path / "operator/environment-monitor-health.json").read_text())["status"] == "STOPPED"


def test_monitor_failure_is_visible_and_subsequent_poll_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path))
    health = tmp_path / "operator/environment-monitor-health.json"
    class PollSequence:
        remaining = 2
        def wait(self, _interval):
            self.remaining -= 1
            return self.remaining < 0
    calls = []
    def capture(**kwargs):
        calls.append(kwargs["reason"])
        if len(calls) == 1:
            raise ConnectionError("database unavailable")
        assert json.loads(health.read_text())["status"] == "ERROR"
        return {"observed_at": "2026-09-29T00:01:00+00:00", "scan_id": "fixture"}
    monitor = EnvironmentMonitor(capture=capture)
    monitor.stop_event = PollSequence()
    monitor._run()
    assert calls == ["POLL", "POLL"]
    assert json.loads(health.read_text())["status"] == "RUNNING"


@pytest.mark.parametrize("interval", [0, -1, 9, 3601, float("inf"), float("nan")])
def test_monitor_rejects_unbounded_or_busy_polling(interval):
    with pytest.raises(ValueError):
        EnvironmentMonitor(interval=interval)
