"""Digital-human test endpoints backed by the official Kling avatar API."""

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import kling_avatar, tokenstar_character_sheet


router = APIRouter(prefix="/avatar", tags=["avatar"])


class AvatarCreateRequest(BaseModel):
    image: str = Field(min_length=1, description="Raw Base64 JPG/JPEG/PNG; no data URI prefix")
    sound_file: str = Field(min_length=1, description="Raw Base64 MP3/WAV/M4A/AAC; no data URI prefix")
    prompt: str = Field(default="", max_length=2500)
    mode: Literal["std", "pro"] = "std"
    watermark_enabled: bool = False


class CharacterSheetRequest(BaseModel):
    image: str = Field(min_length=1, description="Raw Base64 JPG/JPEG/PNG; no data URI prefix")


@router.get("/health")
def health() -> Dict[str, Any]:
    """Expose only configuration state; never expose the API key itself."""
    return {
        "configured": kling_avatar.configured(),
        "provider": "kling_official",
        "base_url": kling_avatar.KLING_AVATAR_BASE_URL,
        "character_sheet": {
            "configured": tokenstar_character_sheet.configured(),
            "provider": "tokenstar_gemini_3_pro",
            "model": tokenstar_character_sheet.model_name(),
        },
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


@router.post("/character-sheet")
def create_character_sheet(request: CharacterSheetRequest) -> Dict[str, Any]:
    """Generate a three-view and expression-sheet image without touching avatar tasks."""
    try:
        result = tokenstar_character_sheet.generate_character_sheet(request.image)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.get("error"):
        status_code = 503 if result.get("configuration") else 502
        raise HTTPException(status_code=status_code, detail=result["error"])
    return result
