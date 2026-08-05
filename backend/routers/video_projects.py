"""Authenticated API for director-script video production projects."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import security
from services import video_project


router = APIRouter(prefix="/video-projects", tags=["video-projects"])


class PromptUpdate(BaseModel):
    motion_prompt: str


class CompileRequest(BaseModel):
    force: bool = False


class FreshProjectRequest(BaseModel):
    source_project_id: str
    studio_scenes: List[Dict[str, Any]] = []


def _error(exc: Exception, status: int = 422) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    return HTTPException(status, str(exc))


@router.get("/public-frame/{name}")
def public_frame(name: str):
    """Unguessable, read-only source frame URL used by the video provider."""
    try:
        path = video_project.public_frame_path(name)
    except video_project.VideoProjectError as exc:
        raise HTTPException(404, str(exc))
    if not path.is_file():
        raise HTTPException(404, "首帧不存在")
    return FileResponse(path)


@router.post("/{memorial_id}/{project_id}/approve-script")
def approve_script(memorial_id: str, project_id: str, user=Depends(security.get_current_user)):
    try:
        return video_project.approve_script(user["user_id"], memorial_id, project_id)
    except Exception as exc:
        raise _error(exc)


@router.post("/{memorial_id}/fresh-from-script")
def fresh_from_script(
    memorial_id: str,
    req: FreshProjectRequest,
    user=Depends(security.get_current_user),
):
    """Start a clean material-selection workspace without reusing old clip caches."""
    try:
        return video_project.create_fresh_project_from_script(
            user["user_id"], memorial_id, req.source_project_id, req.studio_scenes
        )
    except Exception as exc:
        raise _error(exc, 409)


@router.post("/{memorial_id}/{project_id}/compile")
def compile_project(
    memorial_id: str,
    project_id: str,
    req: CompileRequest,
    user=Depends(security.get_current_user),
):
    try:
        return video_project.compile_project(
            user["user_id"], memorial_id, project_id, force=req.force
        )
    except Exception as exc:
        raise _error(exc, 409)


@router.get("/{memorial_id}/{project_id}")
def get_project(memorial_id: str, project_id: str, user=Depends(security.get_current_user)):
    try:
        return video_project.get_project(user["user_id"], memorial_id, project_id)
    except Exception as exc:
        raise _error(exc, 404)


@router.patch("/{memorial_id}/{project_id}/clips/{clip_id}/prompt")
def update_prompt(
    memorial_id: str,
    project_id: str,
    clip_id: str,
    req: PromptUpdate,
    user=Depends(security.get_current_user),
):
    try:
        return video_project.update_prompt(
            user["user_id"], memorial_id, project_id, clip_id, req.motion_prompt
        )
    except Exception as exc:
        raise _error(exc)


@router.post("/{memorial_id}/{project_id}/clips/{clip_id}/generate", status_code=202)
def generate_clip(
    memorial_id: str,
    project_id: str,
    clip_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(security.get_current_user),
):
    try:
        user_id = user["user_id"]
        job_id, created = video_project.queue_clip_generation(user_id, memorial_id, project_id, clip_id)
        if created:
            background_tasks.add_task(
                video_project.run_clip_generation,
                user_id,
                memorial_id,
                project_id,
                clip_id,
                job_id,
            )
        return {"accepted": True, "job_id": job_id, "status": "generating", "already_running": not created}
    except Exception as exc:
        raise _error(exc, 409)


@router.post("/{memorial_id}/{project_id}/clips/{clip_id}/approve")
def approve_clip(memorial_id: str, project_id: str, clip_id: str, user=Depends(security.get_current_user)):
    try:
        return video_project.approve_clip(user["user_id"], memorial_id, project_id, clip_id)
    except Exception as exc:
        raise _error(exc, 409)


@router.post("/{memorial_id}/{project_id}/clips/{clip_id}/fallback")
def fallback_clip(memorial_id: str, project_id: str, clip_id: str, user=Depends(security.get_current_user)):
    try:
        return video_project.fallback_clip(user["user_id"], memorial_id, project_id, clip_id)
    except Exception as exc:
        raise _error(exc, 409)


@router.get("/{memorial_id}/{project_id}/clips/{clip_id}/file")
def clip_file(memorial_id: str, project_id: str, clip_id: str, user=Depends(security.get_current_user)):
    try:
        path = video_project.clip_file_path(user["user_id"], memorial_id, project_id, clip_id)
    except Exception as exc:
        raise _error(exc, 404)
    return FileResponse(path, media_type="video/mp4", filename=f"{clip_id}.mp4")


@router.post("/{memorial_id}/{project_id}/render", status_code=202)
def render(
    memorial_id: str,
    project_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(security.get_current_user),
):
    try:
        user_id = user["user_id"]
        job_id, created = video_project.queue_render(user_id, memorial_id, project_id)
        if created:
            background_tasks.add_task(video_project.run_render, user_id, memorial_id, project_id, job_id)
        return {"accepted": True, "job_id": job_id, "status": "rendering", "already_running": not created}
    except Exception as exc:
        raise _error(exc, 409)


@router.get("/{memorial_id}/{project_id}/final")
def final_file(memorial_id: str, project_id: str, user=Depends(security.get_current_user)):
    try:
        path = video_project.final_file_path(user["user_id"], memorial_id, project_id)
    except Exception as exc:
        raise _error(exc, 404)
    return FileResponse(path, media_type="video/mp4", filename=f"{project_id}_final.mp4")


@router.get("/{memorial_id}/{project_id}/render-manifest")
def render_manifest(memorial_id: str, project_id: str, user=Depends(security.get_current_user)):
    try:
        path = video_project.render_manifest_path(user["user_id"], memorial_id, project_id)
    except Exception as exc:
        raise _error(exc, 404)
    return FileResponse(path, media_type="application/json", filename=f"{project_id}_render_manifest.json")
