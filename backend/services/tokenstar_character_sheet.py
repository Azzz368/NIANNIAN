"""TokenStar Gemini 3 Pro character-sheet image generation.

This is intentionally separate from the official Kling avatar client: it creates
a still character-design reference sheet and never changes the avatar video flow.
"""

import base64
import binascii
import os
from io import BytesIO
from typing import Any, Dict, Tuple

import requests as _requests
from PIL import Image


DEFAULT_MODEL = "gemini-3-pro-image-preview"
DEFAULT_BASE_URL = "https://api.tokenstar.world"
MAX_IMAGE_BYTES = 10 * 1024 * 1024

CHARACTER_SHEET_PROMPT = (
    "严格以提供的真人参考照片作为唯一人物身份基准，生成高真实感、摄影级真人角色设定图。"
    "输出必须是写实真人摄影风格，不得生成动漫、插画、漫画、卡通、游戏角色、3D 渲染或任何风格化绘画。"
    "必须精准复现参考人物的性别、年龄感、种族特征、肤色、脸型、五官比例、眼睛、鼻子、嘴唇、发型、发色、"
    "服装、配饰与整体气质；不得美化、年轻化、换脸、改变发型、改变衣着或改变人物身份。"
    "画面右侧为同一真人的标准全身正面、侧面、背面三视图，真人比例、身高、体型和服装必须完全统一，"
    "姿势自然端正，头到脚完整可见。画面左侧为同一真人脸部的 9 宫格真实摄影表情，"
    "包含微笑、平静、害羞、生气、疑惑、开心、难过、惊讶等情绪。"
    "纯白影棚背景，均匀柔和的真实摄影棚光线，结构清晰工整，无文字、无标签、无水印，比例 16:9。"
)


def _tokenstar_base_url() -> str:
    base = os.getenv("TOKENSTAR_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def model_name() -> str:
    return os.getenv("TOKENSTAR_CHARACTER_SHEET_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def configured() -> bool:
    """Whether TokenStar is configured, without exposing its secret."""
    return bool(os.getenv("TOKENSTAR_API_KEY", "").strip())


def _decode_image(value: str) -> Tuple[str, str]:
    value = (value or "").strip()
    if not value:
        raise ValueError("请选择人物参考图")
    if value.lower().startswith("data:"):
        raise ValueError("请传原始 Base64，不要包含 data: 前缀")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("参考图 Base64 格式无效") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("参考图不能为空且不能超过 10MB")

    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
    except Exception as exc:
        raise ValueError("参考图必须是有效的 JPG、JPEG 或 PNG 图片") from exc
    if image_format not in {"JPEG", "PNG"}:
        raise ValueError("参考图仅支持 JPG、JPEG 或 PNG 格式")
    if width < 300 or height < 300:
        raise ValueError("参考图宽高均不能小于 300px")
    mime_type = "image/jpeg" if image_format == "JPEG" else "image/png"
    return mime_type, base64.b64encode(raw).decode("ascii")


def _error_detail(response: Any) -> str:
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return f"HTTP {response.status_code}: {getattr(response, 'text', '')[:300]}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or payload)
        return str(payload.get("message") or payload.get("detail") or error or payload)
    return f"HTTP {response.status_code}"


def _result_image(payload: Dict[str, Any]) -> Tuple[str, str]:
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        for part in parts or []:
            inline = part.get("inlineData") if isinstance(part, dict) else None
            if not isinstance(inline, dict):
                continue
            data = inline.get("data")
            mime_type = inline.get("mimeType") or "image/png"
            if isinstance(data, str) and data:
                return mime_type, data
    raise ValueError("TokenStar 未返回图片数据")


def generate_character_sheet(image_b64: str) -> Dict[str, Any]:
    """Generate one photorealistic 16:9 sheet from a reference image."""
    api_key = os.getenv("TOKENSTAR_API_KEY", "").strip()
    if not api_key:
        return {"error": "未配置 TOKENSTAR_API_KEY，无法调用 TokenStar Gemini 图像模型", "configuration": True}

    mime_type, normalized_image = _decode_image(image_b64)
    model = model_name()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": CHARACTER_SHEET_PROMPT},
                {"inlineData": {"mimeType": mime_type, "data": normalized_image}},
            ],
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "16:9"},
        },
    }
    url = f"{_tokenstar_base_url()}/v1beta/models/{model}:generateContent"
    try:
        response = _requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
    except _requests.RequestException as exc:
        return {"error": f"TokenStar Gemini 图像请求异常：{exc}"}
    if response.status_code >= 400:
        return {"error": f"TokenStar Gemini 图像生成失败：{_error_detail(response)}"}
    try:
        result = response.json()
        output_mime, output_b64 = _result_image(result)
    except (ValueError, TypeError) as exc:
        return {"error": f"TokenStar Gemini 图像响应解析失败：{exc}"}
    return {
        "image_data_url": f"data:{output_mime};base64,{output_b64}",
        "model": model,
        "source": "tokenstar_gemini_3_pro",
    }
