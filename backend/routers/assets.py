# backend/routers/assets.py
import base64
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from services import service_manager as sm
from services import session_store

router = APIRouter(prefix="/assets", tags=["assets"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".m4a", ".wav", ".mp3"}


@router.post("/upload")
async def upload(
    session_id: str = Form(...),
    period: str = Form("default"),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    try:
        s = session_store.require(session_id)
    except KeyError:
        raise HTTPException(404, "session not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXT:
        raise HTTPException(400, f"unsupported file type: {suffix}")

    fname = f"{session_id}_{period}_{uuid.uuid4().hex[:8]}{suffix}"
    fpath = sm.UPLOADS_DIR / fname
    fpath.write_bytes(await file.read())

    s["assets"].append({
        "filename": file.filename,
        "saved_as": fname,
        "period":   period,
        "url":      f"/api/assets/file/{fname}",
    })
    return {"ok": True, "asset": s["assets"][-1], "total": len(s["assets"])}


@router.get("/file/{name}")
def file_get(name: str) -> FileResponse:
    fpath = sm.UPLOADS_DIR / name
    if not fpath.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(fpath)


@router.get("/background")
def background() -> Dict[str, Any]:
    """返回默认背景图（base64）"""
    bg = sm.ASSET_DIR / "OurDearFriend.jpg"
    if not bg.exists():
        raise HTTPException(404, "background not found")
    data = base64.b64encode(bg.read_bytes()).decode("ascii")
    return {"mime": "image/jpeg", "base64": data}


@router.get("/list/{sid}")
def list_assets(sid: str) -> Dict[str, Any]:
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    return {"assets": s["assets"]}
