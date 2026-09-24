from __future__ import annotations

import sys
from uuid import uuid4

import pytest

from jit_agent import artifact_journal, blob_store, cli


@pytest.fixture(autouse=True)
def _no_stream_reconfiguration(monkeypatch):
    """Isolate CLI dispatch tests from terminal-encoding side effects.

    UTF-8 stream reconfiguration is exercised separately in test_cli.py; these
    tests focus on argument dispatch and command behavior under capsys.
    """

    monkeypatch.setattr(cli, "_configure_utf8_streams", lambda: None)


def _write_percept(tmp_path, monkeypatch) -> tuple:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    interaction_id = uuid4()
    artifact_journal.write_percept_artifact(
        interaction_id=interaction_id,
        conversation_id=uuid4(),
        correlation_id=uuid4(),
        task_id=interaction_id,
        user_text="hello from the cli audit test",
        user_prompt_event_id=uuid4(),
    )
    return interaction_id


def test_audit_command_prints_rendered_report_for_interaction_id(
    tmp_path, monkeypatch, capsys
) -> None:
    interaction_id = _write_percept(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["prometheist", "audit", "--interaction-id", str(interaction_id)])

    cli.main()

    out = capsys.readouterr().out
    assert "# Percept Audit" in out
    assert f"Interaction: {interaction_id}" in out
    assert "Disposition: INCOMPLETE" in out


def test_audit_command_supports_latest(tmp_path, monkeypatch, capsys) -> None:
    interaction_id = _write_percept(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["prometheist", "audit", "--latest"])

    cli.main()

    out = capsys.readouterr().out
    assert f"Interaction: {interaction_id}" in out


def test_audit_command_rejects_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        sys, "argv", ["prometheist", "audit", "--latest", "--once", "hi"]
    )

    with pytest.raises(SystemExit):
        cli.main()


def test_blob_verify_command_reports_valid_blob(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    descriptor = blob_store.put_blob(b"exact bytes", media_type="text/plain")
    monkeypatch.setattr(sys, "argv", ["prometheist", "blob-verify", "--digest", descriptor.digest])

    cli.main()

    out = capsys.readouterr().out
    assert '"digest"' in out
    assert '"valid": true' in out


def test_blob_verify_command_fails_closed_for_missing_blob(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    missing_digest = "sha256:" + "ee" * 32
    monkeypatch.setattr(sys, "argv", ["prometheist", "blob-verify", "--digest", missing_digest])

    with pytest.raises(RuntimeError):
        cli.main()

    out = capsys.readouterr().out
    assert '"valid": false' in out


def test_blob_verify_requires_digest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(sys, "argv", ["prometheist", "blob-verify"])

    with pytest.raises(SystemExit):
        cli.main()


def test_blob_verify_rejects_interaction_selector(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        sys, "argv", ["prometheist", "blob-verify", "--interaction-id", str(uuid4())]
    )

    with pytest.raises(SystemExit):
        cli.main()


def test_digest_rejected_with_verify_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        sys, "argv", ["prometheist", "verify", "--latest", "--digest", "sha256:" + "aa" * 32]
    )

    with pytest.raises(SystemExit):
        cli.main()


def test_digest_rejected_with_chat_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        sys, "argv", ["prometheist", "chat", "--digest", "sha256:" + "aa" * 32]
    )

    with pytest.raises(SystemExit):
        cli.main()
