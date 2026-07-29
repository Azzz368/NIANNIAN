"""Digital-human test endpoints backed by the official Kling avatar API."""

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import kling_avatar


router = APIRouter(prefix="/avatar", tags=["avatar"])


class AvatarCreateRequest(BaseModel):
    image: str = Field(min_length=1, description="Raw Base64 JPG/JPEG/PNG; no data URI prefix")
    sound_file: str = Field(min_length=1, description="Raw Base64 MP3/WAV/M4A/AAC; no data URI prefix")
    prompt: str = Field(default="", max_length=2500)
    mode: Literal["std", "pro"] = "std"
    watermark_enabled: bool = False


@router.get("/health")
def health() -> Dict[str, Any]:
    """Expose only configuration state; never expose the API key itself."""
    return {
        "configured": kling_avatar.configured(),
        "provider": "kling_official",
        "base_url": kling_avatar.KLING_AVATAR_BASE_URL,
    }


@router.post("/tasks")
def create_task(request: AvatarCreateRequest) -> Dict[str, Any]:
    try:
        result = kling_avatar.create_avatar_task(
            image_b64=request.image,
            sound_b64=request.sound_file,
            prompt=request.prompt,
            mode=request.mode,
            watermark_enabled=request.watermark_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.get("error"):
        status_code = 503 if result.get("configuration") else 502
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    try:
        result = kling_avatar.get_avatar_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.get("error"):
        raise HTTPException(status_code=502, detail=result["error"])
    return result
