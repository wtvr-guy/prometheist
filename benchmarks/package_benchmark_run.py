"""Make one verified person-fidelity run portable without changing source artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".tmp" / "latest-benchmark.zip"
INDEX_NAME = "bundle_index.json"
MANIFEST_NAME = "artifacts/run_manifest.json"


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid JSON in {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {label}")
    return value


def _recorded_path(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def _native_verify(result_path: Path, manifest: dict) -> None:
    kind = manifest.get("artifact_type")
    if kind == "PERSON_FIDELITY_RUN_MANIFEST":
        from run_person_fidelity_baseline import _verify_result_artifacts

        _verify_result_artifacts(result_path)
    elif kind == "PERSON_FIDELITY_MECHANISM_RUN_MANIFEST":
        from run_person_fidelity_mechanism_experiments import verify_result

        verification = verify_result(result_path)
        if not verification.get("valid"):
            raise ValueError(f"mechanism result failed verification: {verification}")
    elif kind == "SELF_MEMORY_PERSON_FIDELITY_RUN_MANIFEST":
        result = _read_object(result_path.read_bytes(), "self-memory result")
        if manifest.get("schema_version") != 1 or any(
            manifest.get(key) != result.get(key)
            for key in ("benchmark_id", "fixture_sha256", "revision")
        ):
            raise ValueError("self-memory manifest does not match the result")
        # This runner has no native interaction-chain verifier yet. The receipt,
        # exact file set, sizes and hashes are checked below and again in the ZIP.
    else:
        raise ValueError(f"unsupported benchmark manifest type: {kind!r}")


def _safe_relative(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"unsafe artifact path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in value.split("/")):
        raise ValueError(f"unsafe artifact path: {value!r}")
    if path.as_posix() != value or not path.parts:
        raise ValueError(f"noncanonical artifact path: {value!r}")
    return path


def _source_files(result_path: Path) -> dict[str, Path]:
    result_path = result_path.resolve(strict=True)
    result_raw = result_path.read_bytes()
    result = _read_object(result_raw, "result")
    receipt = result.get("artifact_evidence")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("path"), str):
        raise ValueError("result lacks an artifact manifest receipt")
    manifest_path = _recorded_path(receipt["path"])
    manifest_raw = manifest_path.read_bytes()
    if _digest(manifest_raw) != receipt.get("sha256") or len(manifest_raw) != receipt.get(
        "size_bytes"
    ):
        raise ValueError("manifest differs from the result receipt")
    manifest = _read_object(manifest_raw, "manifest")
    if _recorded_path(str(manifest.get("result_artifact", ""))) != result_path:
        raise ValueError("manifest points to another result")
    artifact_root = manifest_path.parent.resolve()
    if _recorded_path(str(manifest.get("artifact_root", ""))) != artifact_root:
        raise ValueError("manifest points to another artifact root")
    _native_verify(result_path, manifest)

    files: dict[str, Path] = {
        "result/" + result_path.name: result_path,
        MANIFEST_NAME: manifest_path,
    }
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ValueError("manifest has no file inventory")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid manifest file entry")
        relative = _safe_relative(entry.get("relative_path"))
        source = artifact_root.joinpath(*relative.parts)
        if source.is_symlink() or not source.resolve().is_relative_to(artifact_root):
            raise ValueError(f"unsafe artifact source: {relative}")
        if source.stat().st_size != entry.get("size_bytes") or _file_digest(source) != entry.get("sha256"):
            raise ValueError(f"artifact differs from manifest: {relative}")
        name = "artifacts/" + relative.as_posix()
        if name in files:
            raise ValueError(f"duplicate artifact path: {relative}")
        files[name] = source
    actual = {
        path.relative_to(artifact_root).as_posix()
        for path in artifact_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    expected = {name.removeprefix("artifacts/") for name in files if name.startswith("artifacts/") and name != MANIFEST_NAME}
    if actual != expected:
        raise ValueError("artifact root contains files absent from the manifest")
    return files


def verify_bundle(archive_path: Path) -> dict:
    """Verify the portable ZIP without relying on the original checkout paths."""

    with ZipFile(archive_path) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)) or INDEX_NAME not in names:
            raise ValueError("bundle has duplicate names or no index")
        index = _read_object(bundle.read(INDEX_NAME), INDEX_NAME)
        if index.get("format") != "prometheist-benchmark-bundle-v1":
            raise ValueError("unsupported bundle format")
        files = index.get("files")
        if not isinstance(files, list) or set(names) != {INDEX_NAME} | {
            item.get("path") for item in files if isinstance(item, dict)
        }:
            raise ValueError("bundle file set differs from index")
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("invalid bundle index entry")
            name = item.get("path")
            _safe_relative(name)
            raw = bundle.read(name)
            if len(raw) != item.get("size_bytes") or _digest(raw) != item.get("sha256"):
                raise ValueError(f"bundle file differs from index: {name}")
        result_name = index.get("result")
        if not isinstance(result_name, str) or not result_name.startswith("result/"):
            raise ValueError("bundle has no result")
        result = _read_object(bundle.read(result_name), result_name)
        manifest_raw = bundle.read(MANIFEST_NAME)
        receipt = result.get("artifact_evidence")
        if not isinstance(receipt, dict) or receipt.get("sha256") != _digest(
            manifest_raw
        ) or receipt.get("size_bytes") != len(manifest_raw):
            raise ValueError("bundle manifest differs from result receipt")
        manifest = _read_object(manifest_raw, MANIFEST_NAME)
        expected_raw = {
            "artifacts/" + _safe_relative(item["relative_path"]).as_posix(): item
            for item in manifest["files"]
        }
        if {item["path"] for item in files if item["path"].startswith("artifacts/") and item["path"] != MANIFEST_NAME} != set(expected_raw):
            raise ValueError("bundle artifacts differ from manifest inventory")
        for name, entry in expected_raw.items():
            raw = bundle.read(name)
            if _digest(raw) != entry["sha256"] or len(raw) != entry["size_bytes"]:
                raise ValueError(f"bundle artifact differs from manifest: {name}")
        return {"result": result_name, "artifact_count": len(expected_raw), "status": "VALID"}


def package_run(result_path: Path, output: Path = DEFAULT_OUTPUT) -> dict:
    files = _source_files(result_path)
    output = output.resolve()
    if output == result_path.resolve() or output.is_relative_to(
        _recorded_path(_read_object(files[MANIFEST_NAME].read_bytes(), MANIFEST_NAME)["artifact_root"])
    ):
        raise ValueError("bundle output must be outside the source run")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".benchmark-", suffix=".zip", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=6) as bundle:
                for name, path in sorted(files.items()):
                    bundle.write(path, arcname=name)
                index = {
                    "format": "prometheist-benchmark-bundle-v1",
                    "result": next(name for name in files if name.startswith("result/")),
                    "files": [
                        {"path": name, "sha256": _file_digest(path), "size_bytes": path.stat().st_size}
                        for name, path in sorted(files.items())
                    ],
                }
                bundle.writestr(INDEX_NAME, json.dumps(index, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        check = verify_bundle(Path(temporary))
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {**check, "archive": str(output), "sha256": _file_digest(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, help="verified benchmark result to package")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify-bundle", type=Path, help="check a ZIP without its original files")
    args = parser.parse_args()
    if (args.result is None) == (args.verify_bundle is None):
        parser.error("provide exactly one of --result or --verify-bundle")
    outcome = (
        package_run(args.result, args.output)
        if args.result is not None
        else verify_bundle(args.verify_bundle)
    )
    if args.result is not None and args.output.resolve() == DEFAULT_OUTPUT.resolve():
        subprocess.run(
            ["git", "add", "--", ".tmp/latest-benchmark.zip"],
            cwd=ROOT,
            check=True,
        )
        outcome["staged_for_commit"] = True
    print(json.dumps(outcome, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
