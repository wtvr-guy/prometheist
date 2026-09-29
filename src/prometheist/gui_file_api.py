"""Registered operator-only file controls for the local app."""
from uuid import UUID
from functools import wraps

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from prometheist.environment_contracts import content_digest
from prometheist.gui_files import FileManager, scope_proposal


class FileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: str = "files"
    path: str = Field(default="", max_length=4096)


class ScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=4096)
    label: str = Field(min_length=1, max_length=80)
    writable: bool = False
    accepted_digest: str | None = None


class TextInput(FileInput):
    text: str
    revision: str | None = None


class MutationInput(FileInput):
    revision: str


class RelocateInput(MutationInput):
    destination_root: str
    destination: str = Field(min_length=1, max_length=4096)
    copy_file: bool = Field(default=False, alias="copy")


class UploadInput(FileInput):
    size: int = Field(ge=0)


class ChunkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset: int = Field(ge=0)
    data: str = Field(default="", max_length=1398104)
    finish: bool = False
    abort: bool = False


def file_router(state):
    manager = FileManager(state.root)
    state.files = manager
    router = APIRouter(prefix="/api/files")

    def writable_now():
        from prometheist.gui_jobs import JobBusy
        with state.jobs.lock:
            if state.jobs.active and state.jobs.get(state.jobs.active)["action"] == "file_copy":
                raise JobBusy("Finish or cancel the active file copy before changing files")

    def file_change(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            with state.jobs.lock:
                writable_now()
                return function(*args, **kwargs)
        return guarded

    @router.get("/roots")
    def roots():
        return {"roots": [root.model_dump(mode="json") for root in manager.roots()]}

    @router.post("/roots/proposal")
    def propose(body: ScopeInput):
        proposal = scope_proposal(body.path, body.label, body.writable)
        return {"proposal": proposal, "accepted_digest": content_digest(proposal)}

    @router.post("/roots")
    def add(body: ScopeInput):
        return manager.add_root(body.path, body.label, body.writable, body.accepted_digest).model_dump(mode="json")

    @router.delete("/roots/{root_id}")
    def remove(root_id: UUID):
        manager.remove_root(str(root_id))
        return {"removed": True, "files_deleted": False}

    @router.get("")
    def listing(root: str = "files", path: str = "", offset: int = Query(default=0, ge=0), q: str = Query(default="", max_length=200)):
        return manager.list(root, path, offset=offset, query=q)

    @router.get("/preview")
    def preview(root: str, path: str):
        return manager.preview(root, path)

    @router.get("/download")
    def download(root: str, path: str):
        target, _ = manager.resolve(root, path)
        if not target.is_file():
            raise ValueError("Choose an ordinary file to download")
        # Always attachment; arbitrary HTML/SVG can never execute in the app's origin.
        return FileResponse(target, media_type="application/octet-stream", filename=target.name)

    @router.get("/media")
    def media(root: str, path: str):
        import mimetypes
        target, _ = manager.resolve(root, path)
        media_type = mimetypes.guess_type(target.name)[0]
        if media_type not in {"image/png", "image/jpeg", "image/gif", "image/webp", "audio/mpeg", "audio/wav", "video/mp4", "video/webm"} or not target.is_file():
            raise ValueError("This format is download-only")
        return FileResponse(target, media_type=media_type)

    @router.post("/folders")
    @file_change
    def mkdir(body: FileInput):
        writable_now()
        return manager.mkdir(body.root, body.path)

    @router.put("/text")
    @file_change
    def write(body: TextInput):
        writable_now()
        return manager.write_text(body.root, body.path, body.text, body.revision)

    @router.post("/relocate")
    @file_change
    def relocate(body: RelocateInput):
        writable_now()
        if body.copy_file:
            manager.resolve(body.root, body.path)
            manager.resolve(body.destination_root, body.destination, write=True, allow_root=False)
            return state.jobs.submit("file_copy", body.model_dump(by_alias=True), state.settings)
        return manager.relocate(body.root, body.path, body.destination_root, body.destination, body.revision)

    @router.post("/trash")
    @file_change
    def trash(body: MutationInput):
        writable_now()
        return manager.trash(body.root, body.path, body.revision)

    @router.get("/history")
    def history():
        return {"operations": manager.history()}

    @router.post("/restore/{operation_id}")
    @file_change
    def restore(operation_id: UUID):
        writable_now()
        return manager.restore(operation_id)

    @router.get("/versions/{operation_id}")
    def previous(operation_id: UUID):
        path = manager.receipts / str(operation_id) / "previous-content"
        return FileResponse(path, media_type="application/octet-stream", filename="previous-content.txt")

    @router.post("/uploads")
    @file_change
    def upload(body: UploadInput):
        writable_now()
        return manager.upload_start(body.root, body.path, body.size)

    @router.put("/uploads/{upload_id}")
    def chunk(upload_id: UUID, body: ChunkInput):
        with state.jobs.lock:
            if not body.abort:
                writable_now()
            return manager.upload_chunk(upload_id, body.offset, body.data, finish=body.finish, abort=body.abort)

    return router
