"""Kling official avatar image-to-video client.

The avatar API accepts raw Base64 media, so local test files do not need to be
made public.  Keep the official API key server-side in ``KLING_API_KEY``.
"""

import base64
import binascii
import os
from io import BytesIO
from typing import Any, Dict, Tuple

import requests as _requests
from PIL import Image


KLING_AVATAR_BASE_URL = os.getenv(
    "KLING_AVATAR_BASE_URL", "https://api-beijing.klingai.com"
).rstrip("/")

_IMAGE_MAX_BYTES = 10 * 1024 * 1024
_AUDIO_MAX_BYTES = 5 * 1024 * 1024
_VALID_IMAGE_FORMATS = {"JPEG", "PNG"}


def configured() -> bool:
    """Whether the official Kling credential is available, without revealing it."""
    return bool(os.getenv("KLING_API_KEY", "").strip())


def _decode_raw_base64(value: str, label: str, max_bytes: int) -> Tuple[bytes, str]:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"请上传{label}")
    if value.lower().startswith("data:"):
        raise ValueError(f"{label}请传原始 Base64，不要包含 data: 前缀")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{label} Base64 格式无效") from exc
    if not raw:
        raise ValueError(f"{label}不能为空")
    if len(raw) > max_bytes:
        raise ValueError(f"{label}超过允许大小")
    return raw, base64.b64encode(raw).decode("ascii")


def _validate_image(raw: bytes) -> None:
    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except Exception as exc:
        raise ValueError("参考图必须是有效的 JPG、JPEG 或 PNG 图片") from exc

    if image_format not in _VALID_IMAGE_FORMATS:
        raise ValueError("参考图仅支持 JPG、JPEG 或 PNG 格式")
    if width < 300 or height < 300:
        raise ValueError("参考图宽高均不能小于 300px")
    ratio = width / height
    if not 1 / 2.5 <= ratio <= 2.5:
        raise ValueError("参考图宽高比须介于 1:2.5 和 2.5:1 之间")


def _error_detail(payload: Any, http_status: int = 0, request_id: str = "") -> str:
    if not isinstance(payload, dict):
        return f"HTTP {http_status}" if http_status else "响应格式异常"
    parts = []
    if http_status:
        parts.append(f"HTTP {http_status}")
    code = payload.get("code")
    if code not in (None, 0, "0"):
        parts.append(f"code={code}")
    message = payload.get("message") or payload.get("detail") or payload.get("error")
    if message:
        parts.append(str(message))
    req_id = request_id or payload.get("request_id") or payload.get("requestId")
    if req_id:
        parts.append(f"request_id={req_id}")
    return "；".join(parts) or "可灵官方返回未知错误"


def _official_request(method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
    api_key = os.getenv("KLING_API_KEY", "").strip()
    if not api_key:
        return {"error": "未配置 KLING_API_KEY，无法调用可灵官方数字人 API", "configuration": True}

    url = f"{KLING_AVATAR_BASE_URL}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = _requests.request(method, url, headers=headers, timeout=60, **kwargs)
    except _requests.RequestException as exc:
        return {"error": f"可灵官方数字人请求异常：{exc}"}

    try:
        payload = response.json()
    except (ValueError, TypeError):
        return {
            "error": f"可灵官方数字人返回非 JSON：HTTP {response.status_code} "
            f"{getattr(response, 'text', '')[:300]}"
        }

    if response.status_code >= 400 or not isinstance(payload, dict) or payload.get("code") not in (None, 0, "0"):
        return {
            "error": _error_detail(
                payload,
                response.status_code,
                getattr(response, "headers", {}).get("x-request-id", ""),
            ),
            "upstream_status": response.status_code,
        }
    return payload


def create_avatar_task(
    image_b64: str,
    sound_b64: str,
    prompt: str = "",
    mode: str = "std",
    watermark_enabled: bool = False,
) -> Dict[str, Any]:
    """Create an official Kling avatar task from one image and one audio file."""
    image_raw, normalized_image = _decode_raw_base64(image_b64, "参考图", _IMAGE_MAX_BYTES)
    _validate_image(image_raw)
    _, normalized_sound = _decode_raw_base64(sound_b64, "音频", _AUDIO_MAX_BYTES)
    prompt = (prompt or "").strip()
    if len(prompt) > 2500:
        raise ValueError("动作提示词不能超过 2500 个字符")
    if mode not in {"std", "pro"}:
        raise ValueError("生成模式只能是 std 或 pro")

    payload = _official_request(
        "POST",
        "/v1/videos/avatar/image2video",
        json={
            "image": normalized_image,
            "sound_file": normalized_sound,
            "prompt": prompt,
            "mode": mode,
            "watermark_info": {"enabled": bool(watermark_enabled)},
        },
    )
    if payload.get("error"):
        return payload

    data = payload.get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        return {"error": f"可灵官方未返回 task_id：{_error_detail(payload)}"}
    return {
        "task_id": str(task_id),
        "status": str(data.get("task_status") or "submitted"),
        "request_id": payload.get("request_id", ""),
        "source": "kling_official_avatar",
    }


def get_avatar_task(task_id: str) -> Dict[str, Any]:
    """Query an official Kling avatar task and normalize the result for the UI."""
    task_id = (task_id or "").strip()
    if not task_id:
        raise ValueError("task_id 不能为空")
    payload = _official_request("GET", f"/v1/videos/avatar/image2video/{task_id}")
    if payload.get("error"):
        return payload

    data = payload.get("data") or {}
    result = data.get("task_result") or {}
    videos = result.get("videos") or []
    first_video = videos[0] if videos and isinstance(videos[0], dict) else {}
    return {
        "task_id": str(data.get("task_id") or task_id),
        "status": str(data.get("task_status") or "submitted"),
        "message": str(data.get("task_status_msg") or ""),
        "video_url": first_video.get("url") or "",
        "watermark_url": first_video.get("watermark_url") or "",
        "duration": first_video.get("duration") or "",
        "request_id": payload.get("request_id", ""),
        "source": "kling_official_avatar",
    }
