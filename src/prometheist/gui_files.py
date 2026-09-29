"""Operator file workspace: explicit roots, conflict checks, versions and recoverable trash.

This is a local UI capability, never a model tool. Canonical/system-owned runtime
files are inspectable but cannot be mutated through this general file interface.
"""
from __future__ import annotations

import base64
import errno
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import tempfile
import threading
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from prometheist.environment_contracts import content_digest
from prometheist.operator_state import policy_lock, write_private_policy

FILE_PAGE_SIZE = 250
MAX_DIRECTORY_ENTRIES = 20000
MAX_SEARCH_ENTRIES = 20000
MAX_TEXT_BYTES = 524288
UPLOAD_CHUNK_BYTES = 1048576
MAX_COPY_ENTRIES = 20000
FILE_SCOPE_VERSION = "file-scopes/v1"
INTERNAL_PREFIX = ".prometheist-"


def replace_preserving_permissions(temporary: Path, destination: Path):
    """Existing-file edits preserve access; a failed merge never ignores ACLs."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        replace = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
        replace.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                            wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
        replace.restype = wintypes.BOOL
        # Same-volume backup also preserves recovery if Windows reports a partial move.
        backup = temporary.with_name(temporary.name + "-previous")
        if not replace(str(destination), str(temporary), str(backup), 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        backup.unlink(missing_ok=True)
    else:
        original, staged = destination.stat(), temporary.stat()
        if (original.st_uid, original.st_gid) != (staged.st_uid, staged.st_gid):
            os.chown(temporary, original.st_uid, original.st_gid)
        os.chmod(temporary, stat.S_IMODE(original.st_mode))
        if hasattr(os, "listxattr"):
            # Preserve POSIX access ACLs where exposed. Failure prevents replacement.
            for name in os.listxattr(destination):
                if name == "system.posix_acl_access":
                    os.setxattr(temporary, name, os.getxattr(destination, name))
        os.replace(temporary, destination)


class FileRoot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    label: str = Field(min_length=1, max_length=80)
    path: str
    writable: bool = False
    device: int
    inode: int
    accepted_digest: str | None = None


class FileScopes(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["file-scopes/v1"] = FILE_SCOPE_VERSION
    roots: tuple[FileRoot, ...] = ()


def root_record(path: Path, *, root_id: str, label: str, writable: bool, digest=None):
    path = path.expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("Choose an existing local folder")
    info = path.stat()
    return FileRoot(id=root_id, label=label, path=str(path), writable=writable,
                    device=info.st_dev, inode=info.st_ino, accepted_digest=digest)


def scope_proposal(path, label, writable):
    # Intentional operator scope selection, not a path beneath a preexisting grant.
    # Only authenticated same-origin UI requests reach this boundary. A separate
    # accepted digest is required before this path can become a browsing root.
    selected = local_scope_path(path)
    if not selected.is_absolute():
        raise ValueError("Choose an absolute local folder path")
    resolved = selected.resolve(strict=True)
    if resolved == Path(resolved.anchor):
        raise ValueError("Choose a specific folder rather than an entire filesystem root")
    record = root_record(resolved, root_id="review", label=label, writable=writable)
    return {"schema_version": FILE_SCOPE_VERSION, "path": record.path, "label": label,
            "writable": writable, "device": record.device, "inode": record.inode,
            "disclosure": "Lets the authenticated local app browse, search, preview and download files in this folder. "
                + ("It can also create, edit, upload, copy, move and trash files, within your OS permissions. " if writable else "This folder is read-only. ")
                + "Symlinks/junctions are not followed. System-owned Prometheist records remain read-only. "
                + "No file is sent to a model, indexed into memory, or transmitted to a remote service by granting this scope.",
            "duration": "until you remove this folder from Files"}


def local_scope_path(path):
    """Reject network destinations before path resolution can contact a server."""
    raw = str(path)
    if raw.startswith(("\\\\", "//")) or PureWindowsPath(raw).drive.startswith("\\\\"):
        raise ValueError("Network and device namespace paths need a separate network-filesystem integration")
    selected = Path(raw).expanduser()
    if not selected.is_absolute() or ".." in selected.parts:
        raise ValueError("Choose an absolute local folder path without parent traversal")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        drive_type = ctypes.WinDLL("kernel32", use_last_error=True).GetDriveTypeW
        drive_type.argtypes = [wintypes.LPCWSTR]
        drive_type.restype = wintypes.UINT
        if drive_type(selected.anchor) == 4:  # DRIVE_REMOTE, Win32 API constant
            raise ValueError("Mapped network drives require a separate network-filesystem integration")
    else:
        import psutil
        mounts = [entry for entry in psutil.disk_partitions(all=True)
                  if selected.is_relative_to(Path(entry.mountpoint))]
        if mounts:
            mount = max(mounts, key=lambda entry: len(Path(entry.mountpoint).parts))
            if mount.fstype.casefold() in {"nfs", "nfs4", "cifs", "smbfs", "smb3", "fuse.sshfs", "davfs", "davfs2", "afpfs"}:
                raise ValueError("Network mounts require a separate network-filesystem integration")
    cursor = Path(selected.anchor)
    for part in selected.parts[1:]:
        cursor /= part
        if cursor.is_symlink() or cursor.is_junction():
            raise ValueError("Choose the actual local folder; linked roots are not followed")
    return selected


def path_parts(relative):
    if not isinstance(relative, str) or "\\" in relative or "\x00" in relative or ":" in relative:
        raise ValueError("Use a relative folder path without drive names or alternate streams")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Path escapes the selected folder")
    for part in path.parts:
        if part.startswith(INTERNAL_PREFIX) or part.endswith((" ", ".")):
            raise ValueError("This name is reserved for file-manager state or is ambiguous on Windows")
        stem = part.split(".", 1)[0].upper()
        if stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("Reserved Windows device name")
        if any(ord(char) < 32 or char in '<>"|?*' for char in part):
            raise ValueError("Unsupported filename characters")
    return path.parts


def revision(path):
    info = path.stat()
    return content_digest({"device": info.st_dev, "inode": info.st_ino, "size": info.st_size,
                           "modified": info.st_mtime_ns, "changed": info.st_ctime_ns})


class FileManager:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.profile_root = root.parent.resolve()
        self.workspace = self.profile_root / "files"
        if self.workspace.is_symlink() or self.workspace.is_junction():
            raise PermissionError("The built-in file workspace cannot be a link")
        self.workspace.mkdir(mode=0o700, exist_ok=True)
        self.defaults = [root_record(self.workspace, root_id="files", label="My files", writable=True),
                         root_record(self.profile_root, root_id="runtime", label="Runtime records", writable=False)]
        self.policy = self.root / "operator" / "file-scopes.json"
        self.receipts = self.root / "operator" / "file-operations"
        self.uploads = self.root / "operator" / "file-uploads"
        self.lock = threading.RLock()

    def configured_roots(self):
        return FileScopes.model_validate_json(self.policy.read_text(encoding="utf-8")) if self.policy.exists() else FileScopes()

    def roots(self):
        return self.defaults + list(self.configured_roots().roots)

    def add_root(self, path, label, writable, accepted_digest):
        proposal = scope_proposal(path, label, writable)
        if content_digest(proposal) != accepted_digest:
            raise ValueError("Folder acceptance must match the exact path, permissions and disclosure")
        record = root_record(Path(proposal["path"]), root_id=str(uuid4()), label=label,
                             writable=writable, digest=accepted_digest)
        with policy_lock(self.policy):
            prior = self.configured_roots()
            if any(item.path == record.path for item in self.roots()):
                raise ValueError("This folder is already available")
            write_private_policy(self.policy, FileScopes(roots=(*prior.roots, record)).model_dump(mode="json"))
        return record

    def remove_root(self, root_id):
        if root_id in ("files", "runtime"):
            raise ValueError("Built-in folders cannot be removed")
        with policy_lock(self.policy):
            prior = self.configured_roots()
            write_private_policy(self.policy, FileScopes(roots=tuple(r for r in prior.roots if r.id != root_id)).model_dump(mode="json"))

    def resolve(self, root_id, relative="", *, write=False, allow_root=True):
        roots = {item.id: item for item in self.roots()}
        if root_id not in roots:
            raise PermissionError("This folder is no longer authorized")
        record = roots[root_id]
        base = Path(record.path)
        info = base.stat()
        if (info.st_dev, info.st_ino) != (record.device, record.inode) or base.is_symlink() or base.is_junction():
            raise PermissionError("The configured folder identity has changed; review it again")
        parts = path_parts(relative)
        target = base
        for part in parts:
            target = target / part
            if target.is_symlink() or target.is_junction():
                raise PermissionError("Symlinks and junctions cannot be followed by Files")
        if not target.resolve().is_relative_to(base):
            raise PermissionError("Path escapes the selected folder")
        if not allow_root and not parts:
            raise PermissionError("The selected root folder cannot be modified")
        if target.exists() and not target.is_file() and not target.is_dir():
            raise PermissionError("Only ordinary files and directories are supported")
        if write:
            if not record.writable:
                raise PermissionError("This folder is read-only")
            protected = target.resolve().is_relative_to(self.profile_root) and not target.resolve().is_relative_to(self.workspace)
            contains_protected = self.profile_root.is_relative_to(target.resolve())
            if protected or contains_protected:
                raise PermissionError("System-owned records are read-only in Files; use their dedicated controls")
            if target.is_file() and target.stat().st_nlink != 1:
                raise PermissionError("Editing or moving hard-linked files is not supported")
        return target, record

    def info(self, path, base):
        info = path.lstat()
        link = path.is_symlink() or path.is_junction()
        return {"name": path.name, "path": path.relative_to(base).as_posix(),
                "kind": "link" if link else "folder" if stat.S_ISDIR(info.st_mode) else "file" if stat.S_ISREG(info.st_mode) else "special",
                "size": info.st_size, "modified": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                "revision": revision(path) if not link and (path.is_file() or path.is_dir()) else None}

    def list(self, root_id, relative="", *, offset=0, query=""):
        directory, record = self.resolve(root_id, relative)
        if not directory.is_dir():
            raise ValueError("Choose a folder to browse")
        items = []
        scanned, truncated = 0, False
        if query:
            walker = os.walk(directory, followlinks=False)
            for parent, directories, files in walker:
                directories[:] = sorted(name for name in directories if not name.startswith(INTERNAL_PREFIX)
                    and not (Path(parent)/name).is_symlink() and not (Path(parent)/name).is_junction())
                for name in sorted([*directories, *files]):
                    scanned += 1
                    if scanned > MAX_SEARCH_ENTRIES:
                        truncated = True
                        break
                    if not name.startswith(INTERNAL_PREFIX) and query.casefold() in name.casefold():
                        try:
                            items.append(self.info(Path(parent)/name, Path(record.path)))
                        except OSError:
                            continue
                if truncated:
                    break
        else:
            with os.scandir(directory) as entries:
                for entry in entries:
                    scanned += 1
                    if scanned > MAX_DIRECTORY_ENTRIES:
                        truncated = True
                        break
                    if not entry.name.startswith(INTERNAL_PREFIX):
                        try:
                            items.append(self.info(Path(entry.path), Path(record.path)))
                        except OSError:
                            continue
        items.sort(key=lambda item: (item["kind"] != "folder", item["name"].casefold(), item["name"]))
        return {"root": record.model_dump(mode="json"), "path": relative, "items": items[offset:offset+FILE_PAGE_SIZE],
                "total": len(items), "next_offset": offset+FILE_PAGE_SIZE if offset+FILE_PAGE_SIZE < len(items) else None,
                "truncated": truncated, "scanned": min(scanned, MAX_SEARCH_ENTRIES), "free_bytes": shutil.disk_usage(directory).free}

    def preview(self, root_id, relative):
        path, record = self.resolve(root_id, relative)
        if not path.is_file():
            raise ValueError("Choose an ordinary file")
        version = revision(path)
        info = self.info(path, Path(record.path))
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if info["size"] > MAX_TEXT_BYTES:
            return {**info, "mime": mime, "text": None, "editable": False, "reason": "Larger than the text-preview limit; download to open with a local application"}
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8") if b"\0" not in raw else None
        except UnicodeDecodeError:
            text = None
        if revision(path) != version:
            raise ValueError("File changed while reading; refresh the preview")
        writable = True
        try:
            self.resolve(root_id, relative, write=True, allow_root=False)
        except PermissionError:
            writable = False
        return {**info, "mime": mime, "text": text, "editable": writable and text is not None,
                "sha256": hashlib.sha256(raw).hexdigest()}

    def _begin(self, action, **details):
        operation = str(uuid4())
        receipt = {"id": operation, "action": action, "created_at": datetime.now(timezone.utc).isoformat(),
                   "details": details, "status": "intent"}
        write_private_policy(self.receipts / operation / "intent.json", receipt)
        return operation, receipt

    def _finish(self, operation, receipt, result):
        receipt = {**receipt, "status": "completed", "result": result}
        write_private_policy(self.receipts / operation / "completed.json", receipt)
        return receipt

    def mkdir(self, root_id, relative):
        with self.lock:
            path, _ = self.resolve(root_id, relative, write=True, allow_root=False)
            operation, receipt = self._begin("mkdir", root=root_id, path=relative)
            path.mkdir(mode=0o700)
            return self._finish(operation, receipt, {"path": relative})

    def write_text(self, root_id, relative, text, expected_revision=None):
        data = text.encode("utf-8")
        if len(data) > MAX_TEXT_BYTES:
            raise ValueError("Text editor size limit exceeded; use an upload")
        with self.lock:
            path, _ = self.resolve(root_id, relative, write=True, allow_root=False)
            if path.exists():
                if not expected_revision or revision(path) != expected_revision:
                    raise ValueError("File changed since it was opened; refresh instead of overwriting")
            elif expected_revision:
                raise ValueError("The original file no longer exists")
            operation, receipt = self._begin("write", root=root_id, path=relative, previous_revision=expected_revision)
            if path.exists():
                backup = self.receipts / operation / "previous-content"
                shutil.copy2(path, backup)
                backup.chmod(0o600)
            descriptor, temporary_name = tempfile.mkstemp(prefix=INTERNAL_PREFIX+"edit-", dir=path.parent)
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                self.resolve(root_id, relative, write=True, allow_root=False)
                if expected_revision:
                    if revision(path) != expected_revision:
                        raise ValueError("File changed during save; previous content was retained")
                    replace_preserving_permissions(temporary, path)
                else:
                    os.link(temporary, path)  # atomic create-if-absent, never overwrite
                    temporary.unlink()
            finally:
                temporary.unlink(missing_ok=True)
            return self._finish(operation, receipt, {"path": relative, "revision": revision(path)})

    def relocate(self, root_id, relative, destination_root, destination, expected_revision, *, copy=False, progress=None):
        with self.lock:
            source, _ = self.resolve(root_id, relative, write=not copy, allow_root=False)
            target, _ = self.resolve(destination_root, destination, write=True, allow_root=False)
            if revision(source) != expected_revision:
                raise ValueError("Source changed since selection; refresh before copying or moving")
            if target.exists() or target.is_relative_to(source):
                raise ValueError("Destination exists or is inside the source")
            if not target.parent.is_dir():
                raise ValueError("Destination parent does not exist")
            operation, receipt = self._begin("copy" if copy else "move", root=root_id, path=relative,
                                             destination_root=destination_root, destination=destination)
            if copy:
                count = 0
                def copy_file(src, dst):
                    nonlocal count
                    count += 1
                    if count > MAX_COPY_ENTRIES:
                        raise ValueError("Copy entry budget exceeded; partial destination retained for inspection")
                    self.resolve(root_id, Path(src).relative_to(Path(self._root_path(root_id))).as_posix())
                    if not Path(src).is_file():
                        raise ValueError("Copy encountered a special file")
                    if progress:
                        progress({"status": "Copying files", "files": count, "name": Path(src).name})
                    source_version = revision(Path(src))
                    with Path(src).open("rb") as reader, Path(dst).open("xb") as writer:
                        shutil.copyfileobj(reader, writer, length=UPLOAD_CHUNK_BYTES)
                        writer.flush()
                        os.fsync(writer.fileno())
                    if revision(Path(src)) != source_version:
                        raise ValueError("Source changed during copy; partial destination retained for inspection")
                    return str(dst)
                if source.is_dir():
                    # Reject links before tree traversal, including junctions on Windows.
                    examined = 0
                    for parent, directories, files in os.walk(source, followlinks=False):
                        for name in [*directories, *files]:
                            examined += 1
                            if examined > MAX_COPY_ENTRIES:
                                raise ValueError("Copy entry budget exceeded; narrow the selected folder")
                            entry = Path(parent)/name
                            self.resolve(root_id, entry.relative_to(Path(self._root_path(root_id))).as_posix())
                    shutil.copytree(source, target, copy_function=copy_file)
                else:
                    copy_file(source, target)
            else:
                try:
                    source.rename(target)
                except OSError as exc:
                    if exc.errno == errno.EXDEV:
                        raise ValueError("Cross-volume moves require copying first, then moving the original to Trash") from None
                    raise
            return self._finish(operation, receipt, {"path": destination, "root": destination_root})

    def _root_path(self, root_id):
        return next(root.path for root in self.roots() if root.id == root_id)

    def trash(self, root_id, relative, expected_revision):
        with self.lock:
            path, record = self.resolve(root_id, relative, write=True, allow_root=False)
            if revision(path) != expected_revision:
                raise ValueError("File changed since selection; refresh before moving it to Trash")
            operation, receipt = self._begin("trash", root=root_id, path=relative)
            trash = Path(record.path) / (INTERNAL_PREFIX + "trash")
            if trash.is_symlink() or trash.is_junction():
                raise PermissionError("Trash folder must not be a link")
            trash.mkdir(mode=0o700, exist_ok=True)
            item = trash / operation
            path.rename(item)
            return self._finish(operation, receipt, {"trash_id": operation, "path": relative})

    def history(self):
        if not self.receipts.exists():
            return []
        paths = sorted(self.receipts.glob("*/intent.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        return [json.loads((path.with_name("completed.json") if path.with_name("completed.json").exists() else path).read_text(encoding="utf-8")) for path in paths[:200]]

    def restore(self, operation_id):
        operation_id = str(UUID(str(operation_id)))
        original = json.loads((self.receipts / operation_id / "completed.json").read_text(encoding="utf-8"))
        details = original["details"]
        path, record = self.resolve(details["root"], details["path"], write=True, allow_root=False)
        operation, receipt = self._begin("restore", original=operation_id, root=details["root"], path=details["path"])
        if original["action"] == "trash":
            if path.exists():
                raise ValueError("The original path now exists; move it before restoring")
            trash = Path(record.path) / (INTERNAL_PREFIX + "trash")
            if trash.is_symlink() or trash.is_junction():
                raise PermissionError("Trash folder must not be a link")
            item = trash / operation_id
            if item.is_symlink() or item.is_junction():
                raise PermissionError("Trash entry identity changed")
            item.rename(path)
        else:
            raise ValueError("Only Trash entries can be restored with this operation")
        return self._finish(operation, receipt, {"path": details["path"]})

    def upload_start(self, root_id, relative, size):
        if size < 0:
            raise ValueError("Invalid upload size")
        with self.lock:
            path, _ = self.resolve(root_id, relative, write=True, allow_root=False)
            if path.exists():
                raise ValueError("Upload destination already exists; choose a new name")
            if size > shutil.disk_usage(path.parent).free:
                raise ValueError("Not enough free space for this upload")
            upload_id = str(uuid4())
            temporary = path.parent / (INTERNAL_PREFIX + "upload-" + upload_id)
            with temporary.open("xb"):
                temporary.chmod(0o600)
            manifest = {"id": upload_id, "root": root_id, "path": relative, "size": size,
                        "temporary_revision": revision(temporary)}
            write_private_policy(self.uploads / (upload_id + ".json"), manifest)
            return manifest

    def upload_chunk(self, upload_id, offset, data, *, finish=False, abort=False):
        with self.lock:
            upload_id = str(UUID(str(upload_id)))
            manifest_path = self.uploads / (upload_id + ".json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            target, _ = self.resolve(manifest["root"], manifest["path"], write=True, allow_root=False)
            temporary = target.parent / (INTERNAL_PREFIX + "upload-" + upload_id)
            if temporary.is_symlink() or temporary.is_junction() or revision(temporary) != manifest["temporary_revision"]:
                raise PermissionError("Upload file identity changed")
            if abort:
                temporary.unlink()
                manifest_path.unlink()
                return {"aborted": True}
            if temporary.stat().st_size != offset:
                raise ValueError("Upload offset does not match received bytes")
            content = base64.b64decode(data, validate=True)
            if len(content) > UPLOAD_CHUNK_BYTES or offset + len(content) > manifest["size"]:
                raise ValueError("Upload chunk exceeds its declared bound")
            if finish:
                if content or offset != manifest["size"]:
                    raise ValueError("Upload is incomplete")
                operation, receipt = self._begin("upload", root=manifest["root"], path=manifest["path"], size=offset)
                os.link(temporary, target)
                temporary.unlink()
                manifest_path.unlink()
                return self._finish(operation, receipt, {"path": manifest["path"]})
            with temporary.open("ab") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            manifest["temporary_revision"] = revision(temporary)
            write_private_policy(manifest_path, manifest)
            return {"received": offset + len(content)}
