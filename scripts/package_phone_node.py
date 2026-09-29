"""Package a freshly built unsigned Android release, or verify its source manifest.

Run the Gradle release build before packaging. Only public source and a release
APK go into installers/android; personal signing happens separately on Windows.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installers/android"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def source_files():
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "android"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    result = {}
    for name in sorted(set(paths)):
        if name:
            raw = (ROOT / name).read_bytes()
            if not name.endswith(".jar"):
                raw = raw.replace(b"\r\n", b"\n")
            result[name] = hashlib.sha256(raw).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    manifest_path = INSTALLER / "manifest.json"
    if args.verify:
        manifest = json.loads(manifest_path.read_text())
        if digest(INSTALLER / manifest["file"]) != manifest["sha256"]:
            raise SystemExit("APK checksum mismatch")
        if source_files() != manifest["source_files"]:
            raise SystemExit("Android sources changed; rebuild and package the release")
        print("Bundled APK checksum and Android source manifest match.")
        return
    source = ROOT / "android/app/build/outputs/apk/release/app-release-unsigned.apk"
    target = INSTALLER / "Prometheist-Node-0.1.0-unsigned.apk"
    INSTALLER.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    manifest = {
        "file": target.name,
        "sha256": digest(target),
        "bytes": target.stat().st_size,
        "application_id": "org.prometheist.node",
        "version_name": "0.1.0",
        "version_code": 1,
        "signed": False,
        "source_text_newlines": "LF",
        "source_base_commit": subprocess.check_output(["git", "merge-base", "HEAD", "origin/main"], cwd=ROOT)
        .decode()
        .strip(),
        "toolchain": {"agp": "8.9.2", "gradle": "8.11.1", "jdk": "17", "compile_sdk": 35},
        "source_files": source_files(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Packaged {target.name}: {manifest['sha256']}")


if __name__ == "__main__":
    main()
