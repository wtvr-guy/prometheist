"""Recover a passphrase-encrypted Android export without the phone's Keystore."""

from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
import tempfile
import zipfile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"PNODE01\n"
MAX_BACKUP_BYTES = 600 * 1024 * 1024


def recover(source: Path, destination: Path, password: str):
    """Authenticate the entire archive before releasing any recovered evidence."""
    from prometheist.imprinting import _outside_git

    destination = _outside_git(destination)
    if destination.exists():
        raise FileExistsError("Choose a new recovery directory")
    if not 52 <= source.stat().st_size <= MAX_BACKUP_BYTES:
        raise ValueError("Invalid or oversized backup")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, tempfile.TemporaryFile(dir=destination.parent) as verified:
        if incoming.read(8) != MAGIC:
            raise ValueError("Unsupported backup format")
        salt, iv = incoming.read(16), incoming.read(12)
        incoming.seek(-16, 2)
        tag = incoming.read(16)
        key = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000
        ).derive(password.encode("utf-8"))
        decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
        decryptor.authenticate_additional_data(MAGIC)
        incoming.seek(36)
        remaining = source.stat().st_size - 52
        while remaining:
            chunk = incoming.read(min(65536, remaining))
            if not chunk:
                raise ValueError("Truncated backup")
            remaining -= len(chunk)
            verified.write(decryptor.update(chunk))
        verified.write(decryptor.finalize())
        verified.seek(0)
        with zipfile.ZipFile(verified) as archive:
            entries = archive.infolist()
            if sum(i.file_size for i in entries) > MAX_BACKUP_BYTES:
                raise ValueError("Oversized backup contents")
            if len({i.filename for i in entries}) != len(entries):
                raise ValueError("Duplicate backup names")
            import re

            for item in entries:
                if item.filename != "identity.json" and not re.fullmatch(
                    r"evidence/[0-9a-f]{64}\.enc\.json", item.filename
                ):
                    raise ValueError("Unexpected backup member")
            identity = json.loads(archive.read("identity.json"))
            if identity.get("protocol") != "prometheist-node/v1":
                raise ValueError("Unknown evidence protocol")
            destination.mkdir(mode=0o700)
            for item in entries:
                target = destination / item.filename
                target.parent.mkdir(mode=0o700, exist_ok=True)
                import os

                with os.fdopen(
                    os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
                ) as out:
                    with archive.open(item) as contents:
                        import shutil

                        shutil.copyfileobj(contents, out, 65536)
    return identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    recover(args.backup, args.destination, getpass.getpass("Backup passphrase: "))
    print("Recovered authenticated evidence. Keep this directory on encrypted storage.")


if __name__ == "__main__":
    main()
