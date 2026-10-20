from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.auth import DEFAULT_USERNAME, login, require_auth
from backend.metadata import (
    extract_artwork,
    library_root,
    list_audio_files,
    read_metadata,
    resolve_audio_path,
    write_artwork,
    write_metadata,
)

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Music Metadata Editor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class MetadataUpdate(BaseModel):
    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    date: str = ""
    genre: str = ""
    tracknumber: str = ""
    discnumber: str = ""
    comment: str = ""
    composer: str = ""
    lyrics: str = ""


@app.post("/api/login")
def api_login(payload: LoginRequest):
    token = login(payload.username, payload.password)
    return {"token": token, "username": payload.username}


@app.get("/api/me")
def api_me(_: Annotated[str, Depends(require_auth)]):
    return {"username": DEFAULT_USERNAME}


@app.get("/api/library")
def api_library(_: Annotated[str, Depends(require_auth)]):
    root = library_root()
    files = list_audio_files()
    return {
        "root": str(root),
        "count": len(files),
        "files": files,
    }


@app.get("/api/files/{file_id}")
def api_file(file_id: str, _: Annotated[str, Depends(require_auth)]):
    try:
        path = resolve_audio_path(file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        meta = read_metadata(path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read metadata: {exc}") from exc

    relative = path.relative_to(library_root()).as_posix()
    return {
        "id": file_id,
        "name": path.name,
        "relative_path": relative,
        "extension": path.suffix.lower().lstrip("."),
        "size": path.stat().st_size,
        **meta,
    }


@app.put("/api/files/{file_id}")
def api_update_file(
    file_id: str,
    payload: MetadataUpdate,
    _: Annotated[str, Depends(require_auth)],
):
    try:
        path = resolve_audio_path(file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        tags = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        meta = write_metadata(path, tags)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not write metadata: {exc}") from exc

    relative = path.relative_to(library_root()).as_posix()
    return {
        "id": file_id,
        "name": path.name,
        "relative_path": relative,
        "extension": path.suffix.lower().lstrip("."),
        "size": path.stat().st_size,
        **meta,
    }


@app.get("/api/files/{file_id}/artwork")
def api_artwork(file_id: str, _: Annotated[str, Depends(require_auth)]):
    try:
        path = resolve_audio_path(file_id)
        data, mime = extract_artwork(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not data:
        raise HTTPException(status_code=404, detail="No artwork")
    return Response(content=data, media_type=mime or "image/jpeg")


@app.post("/api/files/{file_id}/artwork")
async def api_upload_artwork(
    file_id: str,
    _: Annotated[str, Depends(require_auth)],
    file: UploadFile = File(...),
):
    try:
        path = resolve_audio_path(file_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image")

    try:
        write_artwork(path, data, file.content_type or "image/jpeg")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not write artwork: {exc}") from exc

    return {"ok": True}


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
