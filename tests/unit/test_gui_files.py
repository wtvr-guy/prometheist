import base64

import pytest

from prometheist.environment_contracts import content_digest
from prometheist.gui_files import FileManager, revision, scope_proposal


@pytest.fixture
def files(tmp_path):
    private = tmp_path / "private"
    (private / "artifacts").mkdir(parents=True)
    return FileManager(private / "artifacts")


def test_create_edit_conflict_versions_trash_restore_and_copy(files):
    files.mkdir("files", "notes")
    files.write_text("files", "notes/day.md", "first")
    preview = files.preview("files", "notes/day.md")
    assert preview["text"] == "first" and preview["editable"]
    receipt = files.write_text("files", "notes/day.md", "second", preview["revision"])
    assert (files.receipts / receipt["id"] / "previous-content").read_text() == "first"
    with pytest.raises(ValueError, match="changed"):
        files.write_text("files", "notes/day.md", "lost update", preview["revision"])
    current = files.preview("files", "notes/day.md")
    files.relocate("files", "notes/day.md", "files", "copy.md", current["revision"], copy=True)
    assert files.preview("files", "copy.md")["text"] == "second"
    trashed = files.trash("files", "notes/day.md", current["revision"])
    assert not (files.workspace / "notes/day.md").exists()
    files.restore(trashed["id"])
    assert files.preview("files", "notes/day.md")["text"] == "second"
    with pytest.raises(ValueError, match="already exists|now exists"):
        files.restore(trashed["id"])


@pytest.mark.parametrize("path", ["../escape", "/etc/passwd", "C:/Windows", "foo\\bar", "a:stream", "NUL.txt", ".prometheist-trash/anything", "a."])
def test_rejects_ambiguous_or_escaping_paths(files, path):
    with pytest.raises((ValueError, PermissionError)):
        files.resolve("files", path, write=True)


def test_runtime_records_are_immutable_even_through_an_added_parent_scope(files, tmp_path):
    record = files.root / "canonical.json"
    record.write_text('{"canonical":true}')
    assert not files.preview("runtime", "artifacts/canonical.json")["editable"]
    proposal = scope_proposal(tmp_path, "Parent", True)
    scope = files.add_root(tmp_path, "Parent", True, content_digest(proposal))
    for path in ("private/artifacts/canonical.json", "private", "private/profile.json"):
        with pytest.raises(PermissionError, match="System-owned"):
            files.resolve(scope.id, path, write=True)
    with pytest.raises(PermissionError):
        files.write_text("runtime", "new-record", "unauthorized")
    files.remove_root(scope.id)
    with pytest.raises(PermissionError, match="authorized"):
        files.resolve(scope.id, "")


def test_symlinks_and_replaced_folder_identity_fail_closed(files, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (files.workspace / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not allow unprivileged symlink creation")
    with pytest.raises(PermissionError, match="Symlinks"):
        files.resolve("files", "linked/secret", write=True)
    proposal = scope_proposal(outside, "Outside", True)
    root = files.add_root(outside, "Outside", True, content_digest(proposal))
    outside.rename(tmp_path / "previous-outside")
    outside.mkdir()
    with pytest.raises(PermissionError, match="identity"):
        files.resolve(root.id)


def test_chunked_upload_checks_offsets_and_never_overwrites(files):
    manifest = files.upload_start("files", "upload.bin", 5)
    assert files.upload_chunk(manifest["id"], 0, base64.b64encode(b"hello").decode()) == {"received": 5}
    with pytest.raises(ValueError, match="offset"):
        files.upload_chunk(manifest["id"], 0, "")
    files.upload_chunk(manifest["id"], 5, "", finish=True)
    assert (files.workspace / "upload.bin").read_bytes() == b"hello"
    with pytest.raises(ValueError, match="exists"):
        files.upload_start("files", "upload.bin", 4)
    abort = files.upload_start("files", "cancel.bin", 10)
    files.upload_chunk(abort["id"], 0, "", abort=True)
    assert not (files.workspace / "cancel.bin").exists()
    assert not list(files.workspace.glob(".prometheist-upload-*"))


def test_search_only_walks_the_selected_root_and_copy_refuses_links(files, tmp_path):
    files.mkdir("files", "notes")
    files.write_text("files", "notes/unique.md", "note")
    assert [item["path"] for item in files.list("files", query="unique")["items"]] == ["notes/unique.md"]
    try:
        (files.workspace / "notes/escape").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not allow unprivileged symlinks")
    assert len(files.list("files", query="unique")["items"]) == 1
    with pytest.raises(PermissionError):
        files.relocate("files", "notes", "files", "copy-notes", revision(files.workspace / "notes"), copy=True)
    assert not (files.workspace / "copy-notes").exists()


def test_new_scope_requires_an_absolute_path_and_exact_review(files, tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        scope_proposal("../relative", "Relative", True)
    with pytest.raises(ValueError, match="acceptance"):
        files.add_root(tmp_path, "Unreviewed", True, "not-the-proposal-digest")


def test_edit_preserves_existing_access_permissions(files):
    import os
    import stat
    files.write_text("files", "permissions.txt", "before")
    path = files.workspace / "permissions.txt"
    if os.name == "nt":
        import ctypes
        import subprocess
        from ctypes import wintypes
        # Turn inherited entries into explicit entries: a new temp file differs.
        subprocess.run(["icacls", str(path), "/inheritance:d"], check=True, capture_output=True)
        api = ctypes.WinDLL("advapi32", use_last_error=True).GetFileSecurityW
        api.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        api.restype = wintypes.BOOL
        def permissions():
            size = wintypes.DWORD()
            api(str(path), 4, None, 0, ctypes.byref(size))
            buf = ctypes.create_string_buffer(size.value)
            assert api(str(path), 4, buf, size, ctypes.byref(size)), ctypes.WinError(ctypes.get_last_error())
            return buf.raw
    else:
        path.chmod(0o640)
        def permissions():
            return stat.S_IMODE(path.stat().st_mode), path.stat().st_uid, path.stat().st_gid
    before = permissions()
    files.write_text("files", "permissions.txt", "after", revision(path))
    assert path.read_text() == "after"
    assert permissions() == before


@pytest.mark.parametrize("path", [r"\\server\share\private", "//server/share/private", r"\\?\UNC\server\share", r"\\.\PhysicalDrive0"])
def test_network_scope_rejected_before_any_path_resolution(path, monkeypatch):
    from pathlib import Path
    def forbidden(*args, **kwargs):
        raise AssertionError("Network path must be refused before resolve/stat")
    monkeypatch.setattr(Path, "resolve", forbidden)
    with pytest.raises(ValueError, match="Network"):
        scope_proposal(path, "Remote", True)


def test_scope_does_not_follow_a_linked_root(files, tmp_path):
    linked = tmp_path / "linked-root"
    try:
        linked.symlink_to(files.workspace, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable for this Windows account")
    with pytest.raises(ValueError, match="linked roots"):
        scope_proposal(linked, "Link", True)
