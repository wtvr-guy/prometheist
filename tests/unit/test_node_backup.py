import io
import json
import os
import zipfile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag
import pytest

from prometheist.node_backup import MAGIC, recover


def backup(path, names=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("identity.json", json.dumps({"protocol": "prometheist-node/v1"}))
        for name in names or ["evidence/" + "a" * 64 + ".enc.json"]:
            archive.writestr(name, '{"exact_evidence":"test"}')
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000).derive(
        b"a long test password"
    )
    path.write_bytes(MAGIC + salt + iv + AESGCM(key).encrypt(iv, stream.getvalue(), MAGIC))


def test_backup_authentication_and_roundtrip(tmp_path):
    path = tmp_path / "test.pnode"
    backup(path)
    destination = tmp_path / "restored"
    with pytest.raises(InvalidTag):
        recover(path, destination, "wrong password")
    assert not destination.exists()
    recover(path, destination, "a long test password")
    assert len(list((destination / "evidence").iterdir())) == 1
    with pytest.raises(FileExistsError):
        recover(path, destination, "a long test password")


def test_backup_rejects_path_escape_before_writing(tmp_path):
    path = tmp_path / "test.pnode"
    backup(path, ["../../escape"])
    with pytest.raises(ValueError, match="Unexpected"):
        recover(path, tmp_path / "restored", "a long test password")
    assert not (tmp_path / "restored").exists()
