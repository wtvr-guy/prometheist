import json
import pytest
from prometheist.imprinting import ImprintProfile, initialize_imprint, activate_imprint


def test_setup_is_generic_private_and_non_destructive(tmp_path):
    for subject in ("subject_001", "subject_opposite"):
        profile = initialize_imprint(tmp_path / subject, subject, "PRIVATE_DATABASE_URL")
        data = json.loads(profile.read_text())
        assert data["subject_id"] == subject
        assert data["enabled_sources"] == ["manual_chat"]
        assert "Mike" not in profile.read_text()
        assert (profile.parent / "artifacts").is_dir()
        with pytest.raises(FileExistsError):
            initialize_imprint(profile.parent, subject, "PRIVATE_DATABASE_URL")


def test_private_setup_rejects_git_checkouts_and_unknown_sensors(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(ValueError, match="outside every Git"):
        initialize_imprint(tmp_path / "private", "subject_001", "PRIVATE_DATABASE_URL")
    with pytest.raises(ValueError):
        ImprintProfile(subject_id="subject_001", database_url_env="PRIVATE_DATABASE_URL", enabled_sources=["microphone"])


def test_profile_requires_explicit_dedicated_database(tmp_path, monkeypatch):
    path = initialize_imprint(tmp_path / "vault", "subject_001", "PRIVATE_DATABASE_URL")
    monkeypatch.delenv("PRIVATE_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="set PRIVATE_DATABASE_URL"):
        activate_imprint(path)
    monkeypatch.setenv("PRIVATE_DATABASE_URL", "postgresql://localhost/prometheist_test")
    with pytest.raises(ValueError, match="dedicated"):
        activate_imprint(path)
