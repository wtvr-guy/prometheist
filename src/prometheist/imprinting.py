"""Person-general local research deployment setup. No personal data in source code."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from prometheist.contract_registry import contract_manifest


class ImprintProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["imprint-profile/v1"] = "imprint-profile/v1"
    subject_id: str = Field(pattern=r"^subject_[a-zA-Z0-9_]+$")
    database_url_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    # Permissions are learned neither from telemetry nor from model suggestions.
    enabled_sources: tuple[Literal["manual_chat"], ...] = ("manual_chat",)


def _outside_git(path: Path) -> Path:
    path = path.expanduser().resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("private runtime state must be outside every Git checkout")
    return path


def initialize_imprint(root: Path, subject_id: str, database_url_env: str) -> Path:
    root = _outside_git(root)
    profile = ImprintProfile(subject_id=subject_id, database_url_env=database_url_env)
    # Never overwrite a previous subject's deployment or observation history.
    root.mkdir(parents=True, exist_ok=False)
    try:
        root.chmod(0o700)
        for name in ("artifacts", "objects", "evaluation", "imports"):
            (root / name).mkdir(mode=0o700)
        path = root / "profile.json"
        path.write_text(profile.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (root / "contracts.json").write_text(json.dumps(contract_manifest(), indent=2) + "\n", encoding="utf-8")
        (root / "README.txt").write_text(
            "Private runtime state. Keep outside Git and on an encrypted volume.\n"
            "This initializer does not enable encryption or create a PostgreSQL database.\n"
            "Set the profile's dedicated database URL environment variable before use.\n"
            "Manual chat and passive local environment discovery are available. No account/content adapters are connected.\n"
            "Security enrollment and outbound destination consent are separate, explicit operator actions.\n"
            "Store blinded scenarios, frozen predictions, independent answers and reviews in evaluation/.\n",
            encoding="utf-8",
        )
        return path
    except Exception:
        # Leave any partial setup available for inspection; never erase user state.
        raise


def activate_imprint(path: Path) -> ImprintProfile:
    path = _outside_git(path)
    profile = ImprintProfile.model_validate_json(path.read_text(encoding="utf-8"))
    from psycopg.conninfo import conninfo_to_dict
    url = os.environ.get(profile.database_url_env)
    if not url:
        raise ValueError(f"set {profile.database_url_env} to a dedicated private database URL")
    database = conninfo_to_dict(url).get("dbname", "")
    if not database or "test" in database.casefold() or "benchmark" in database.casefold():
        raise ValueError("an imprint requires a dedicated non-test, non-benchmark database")
    # One identity per database. Bind before any chat or sensor input is admitted.
    import psycopg
    from prometheist.network_consent import require_database_destination
    require_database_destination(url, root=path.parent / "artifacts")
    with psycopg.connect(url) as conn:
        conn.execute("LOCK TABLE imprint_identity IN EXCLUSIVE MODE")
        existing = conn.execute("SELECT subject_id FROM imprint_identity WHERE singleton").fetchone()
        if existing is None and conn.execute("SELECT EXISTS(SELECT 1 FROM events)").fetchone()[0]:
            raise ValueError("first imprint activation requires an empty database")
        conn.execute("INSERT INTO imprint_identity VALUES (true, %s) ON CONFLICT DO NOTHING", (profile.subject_id,))
        bound = conn.execute("SELECT subject_id FROM imprint_identity WHERE singleton").fetchone()[0]
        if bound != profile.subject_id:
            raise ValueError("database is already bound to a different subject")
    os.environ["DATABASE_URL"] = url
    os.environ["PROMETHEIST_ARTIFACT_ROOT"] = str(path.parent / "artifacts")
    os.environ["PROMETHEIST_SUBJECT_ID"] = profile.subject_id
    return profile


def main():
    parser = argparse.ArgumentParser(description="Prepare a private person-general imprint deployment")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--database-url-env", default="PROMETHEIST_PRIVATE_DATABASE_URL")
    args = parser.parse_args()
    print(initialize_imprint(args.root, args.subject, args.database_url_env))


if __name__ == "__main__":
    main()
