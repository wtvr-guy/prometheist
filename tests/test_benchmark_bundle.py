"""Standalone ZIP handoff tests; run without the PostgreSQL pytest fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import package_benchmark_run as packaging  # noqa: E402
import run_person_fidelity_baseline as baseline  # noqa: E402
import run_person_fidelity_mechanism_experiments as mechanism  # noqa: E402
import run_self_memory_person_fidelity as self_memory  # noqa: E402


class BenchmarkBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        root = Path(self.workspace.name)
        self.result = root / "results" / "run.json"
        self.raw_root = root / "generated" / "run"
        self.artifact = self.raw_root / "probe" / "events" / "one.json"
        self.artifact.parent.mkdir(parents=True)
        self.result.parent.mkdir(parents=True)
        self.artifact.write_text('{"event_id":"test"}\n', encoding="utf-8")
        artifact_raw = self.artifact.read_bytes()
        manifest = {
            "artifact_type": "PERSON_FIDELITY_RUN_MANIFEST",
            "result_artifact": str(self.result),
            "artifact_root": str(self.raw_root),
            "files": [{
                "relative_path": "probe/events/one.json",
                "sha256": hashlib.sha256(artifact_raw).hexdigest(),
                "size_bytes": len(artifact_raw),
            }],
        }
        self.manifest = self.raw_root / "run_manifest.json"
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        raw = self.manifest.read_bytes()
        self.result.write_text(json.dumps({"artifact_evidence": {
            "path": str(self.manifest),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }}), encoding="utf-8")
        self.output = root / ".tmp" / "latest-benchmark.zip"

    def _package(self) -> dict:
        with patch.object(packaging, "_native_verify") as native:
            result = packaging.package_run(self.result, self.output)
            native.assert_called_once()
            return result

    def test_zip_contains_original_bytes_and_is_verifiable_without_source(self) -> None:
        result = self._package()
        self.assertEqual(result["artifact_count"], 1)
        with ZipFile(self.output) as bundle:
            self.assertEqual(bundle.read("result/run.json"), self.result.read_bytes())
            self.assertEqual(bundle.read("artifacts/run_manifest.json"), self.manifest.read_bytes())
            self.assertEqual(bundle.read("artifacts/probe/events/one.json"), self.artifact.read_bytes())
        self.artifact.unlink()
        self.manifest.unlink()
        self.result.unlink()
        self.assertEqual(packaging.verify_bundle(self.output)["status"], "VALID")

    def test_failed_packaging_does_not_replace_latest_zip(self) -> None:
        self._package()
        original = self.output.read_bytes()
        self.artifact.write_text('{"event_id":"changed"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs from manifest"):
            self._package()
        self.assertEqual(self.output.read_bytes(), original)

    def test_archive_tampering_is_detected(self) -> None:
        self._package()
        with ZipFile(self.output, "a") as bundle:
            bundle.writestr("extra.json", "{}")
        with self.assertRaisesRegex(ValueError, "file set differs"):
            packaging.verify_bundle(self.output)

    def test_self_memory_run_uses_its_receipt_and_manifest(self) -> None:
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        manifest.update({
            "artifact_type": "SELF_MEMORY_PERSON_FIDELITY_RUN_MANIFEST",
            "schema_version": 1,
            "benchmark_id": "SELF-MEMORY-001",
            "fixture_sha256": "fixture-hash",
            "revision": "tested-revision",
        })
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        result = json.loads(self.result.read_text(encoding="utf-8"))
        result.update({key: manifest[key] for key in ("benchmark_id", "fixture_sha256", "revision")})
        raw = self.manifest.read_bytes()
        result["artifact_evidence"].update({
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        })
        self.result.write_text(json.dumps(result), encoding="utf-8")

        self.assertEqual(packaging.package_run(self.result, self.output)["artifact_count"], 1)
        self.assertEqual(packaging.verify_bundle(self.output)["status"], "VALID")

    def test_all_runners_treat_only_latest_zip_as_output(self) -> None:
        repo = Path(self.workspace.name) / "repo"
        repo.mkdir()

        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

        git("init", "--quiet")
        (repo / ".gitignore").write_text(
            ".tmp/*\n!.tmp/latest-benchmark.zip\n", encoding="utf-8"
        )
        source = repo / "source.txt"
        source.write_text("unchanged", encoding="utf-8")
        git("add", ".gitignore", "source.txt")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "start")

        bundle = repo / ".tmp" / "latest-benchmark.zip"
        bundle.parent.mkdir()

        with (
            patch.object(baseline, "ROOT", repo),
            patch.object(mechanism, "ROOT", repo),
            patch.object(self_memory, "ROOT", repo),
        ):
            for contents in (b"untracked", b"changed"):
                bundle.write_bytes(contents)
                baseline._require_clean_revision()
                mechanism._git_revision(require_clean=True)
                self_memory._require_clean_revision()
                if contents == b"untracked":
                    git("add", ".tmp/latest-benchmark.zip")
                    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "bundle")

            source.write_text("changed source", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "clean"):
                baseline._require_clean_revision()
            with self.assertRaisesRegex(RuntimeError, "clean"):
                mechanism._git_revision(require_clean=True)
            with self.assertRaisesRegex(RuntimeError, "clean"):
                self_memory._require_clean_revision()


if __name__ == "__main__":
    unittest.main()
