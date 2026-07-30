# backend/routers/uploads.py — 文件上传 + LLM 自动打标签
import os, mimetypes, json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from openai import OpenAI
from core import security, storage
from services import asset_analysis, asset_vision, material_context

router = APIRouter(prefix="/memorials", tags=["uploads"])


def _get_llm() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY", ""),
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )


def _guess_kind(filename: str, mime: str) -> str:
    m = (mime or "").lower()
    if m.startswith("image/"): return "image"
    if m.startswith("audio/"): return "audio"
    if m.startswith("video/"): return "video"
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    if ext in ("txt","md","pdf","doc","docx","csv","json"): return "document"
    return "other"


def _auto_tag(filename: str, kind: str, description: str) -> dict:
    """调用 LLM 给文件打标签 + 推断可用场景。失败则降级为基础标签。"""
    fallback = {
        "tags": [kind],
        "usable_for": ["dossier"],
        "summary": description or filename,
    }
    if not os.getenv("DASHSCOPE_API_KEY"):
        return fallback
    try:
        client = _get_llm()
        prompt = f"""你是念念追思助手的资料管理 Agent。用户上传了一个文件，请输出 JSON：
{{
  "tags": [3-6个中文标签，刻画文件主题/年代/场景/情绪],
  "usable_for": ["person_profile" | "video_storyboard" | "biography_chapter" | "digital_human_voice" | "digital_human_memory" 中的若干],
  "summary": "20字以内中文摘要"
}}
不要输出任何 JSON 以外的内容。

文件名：{filename}
文件类型：{kind}
用户描述：{description or "(用户未填写)"}"""
        resp = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        txt = (resp.choices[0].message.content or "").strip()
        # 取出第一段 { ... }
        i, j = txt.find("{"), txt.rfind("}")
        if i >= 0 and j > i:
            return json.loads(txt[i:j+1])
    except Exception as e:
        print("[auto_tag] failed:", e)
    return fallback


def _merge_tags(*tag_lists) -> list[str]:
    merged: list[str] = []
    for tags in tag_lists:
        for tag in tags or []:
            tag = str(tag).strip()
            if tag and tag not in merged:
                merged.append(tag)
    return merged[:12]


def _analyze_library_asset(user_id: str, memorial_id: str, asset_id: str) -> None:
    """Background multimodal indexing. User-authored text remains untouched."""
    assets = storage.list_assets(user_id, memorial_id)
    asset = next((item for item in assets if item.get("asset_id") == asset_id), None)
    if not asset:
        return
    path = storage.memorial_dir(user_id, memorial_id) / "assets" / asset.get("stored_name", "")
    try:
        result = asset_analysis.analyze_asset(
            raw=path.read_bytes(),
            filename=asset.get("filename") or "image",
            mime=asset.get("mime") or "image/jpeg",
            kind=asset.get("kind") or "other",
            user_description=asset.get("user_description") or asset.get("description") or "",
        )
    except Exception as exc:
        result = {"error": str(exc)}

    if result.get("error"):
        patch = {
            "analysis_status": "failed",
            "analysis_error": str(result["error"])[:300],
            "vision_error": str(result["error"])[:300],
        }
        if asset.get("kind") == "image":
            patch["vision_status"] = "failed"
        storage.update_asset(user_id, memorial_id, asset_id, patch)
        return

    stored_tags = asset.get("tags") or []
    stored_uses = asset.get("usable_for") or []
    patch = dict(result)
    patch.update({
        "analysis_status": "succeeded",
        "analysis_error": "",
        "tags": _merge_tags(stored_tags, result.get("tags"), result.get("visual_tags")),
        "usable_for": _merge_tags(stored_uses, result.get("usable_for")),
        "summary": (
            asset.get("user_description")
            or asset.get("description")
            or result.get("ai_summary")
            or result.get("visual_summary")
            or asset.get("summary", "")
        ),
    })
    if asset.get("kind") == "image":
        patch.update({
            "vision_status": "succeeded",
            "vision_error": "",
            "vision_model": result.get("analysis_model", asset_vision.VISION_MODEL),
        })
    storage.update_asset(user_id, memorial_id, asset_id, patch)


def _analyze_library_image(user_id: str, memorial_id: str, asset_id: str) -> None:
    """Compatibility alias for the existing image retry path."""
    _analyze_library_asset(user_id, memorial_id, asset_id)


@router.post("/{mid}/upload")
async def upload(
    mid: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: str = Form(""),
    user = Depends(security.get_current_user),
):
    uid = user["user_id"]
    meta = storage.get_memorial(uid, mid)
    if not meta:
        raise HTTPException(404, "未找到该纪念对象")

    raw = await file.read()
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "单文件不超过 50MB")

    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    kind = _guess_kind(file.filename or "", mime)
    ext = (file.filename or "file").rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    aid = storage.new_id("a_")
    save_name = f"{aid}.{ext}"
    save_path = storage.memorial_dir(uid, mid) / "assets" / save_name
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(raw)

    # A text-only tagger cannot see image pixels. Images receive vision tags in
    # the background; non-image files retain the existing text-tagging flow.
    tag_info = _auto_tag(file.filename or "", kind, description) if kind != "image" else {
        "tags": ["image"], "usable_for": ["dossier"], "summary": description or file.filename or ""
    }

    asset = {
        "asset_id": aid,
        "filename": file.filename,
        "stored_name": save_name,
        "mime": mime,
        "kind": kind,                 # image / audio / video / document / other
        "size": len(raw),
        "description": description,   # 兼容旧字段
        "user_description": description,
        "tags": tag_info.get("tags", []),
        "usable_for": tag_info.get("usable_for", []),
        "summary": tag_info.get("summary", ""),
        "url": f"/api/memorials/{mid}/assets/{aid}",
        "created_at": storage.now_iso(),
        "transcript": "",
        "ai_summary": "",
        "people": [],
        "time_period": "",
        "event": "",
        "scene": "",
        "objects": [],
        "emotion": [],
        "related_memory_ids": [],
        "analysis_status": "queued",
    }
    if kind == "image":
        asset.update({
            "vision_status": "queued",
            "vision_model": asset_vision.VISION_MODEL,
            "visual_summary": "",
            "visual_tags": [],
            "ocr_text": "",
            "search_text": "",
        })
    storage.add_asset(uid, mid, asset)
    background_tasks.add_task(_analyze_library_asset, uid, mid, aid)
    return {"asset": asset}


@router.post("/{mid}/assets/{aid}/analyze-image")
def analyze_image_asset(
    mid: str,
    aid: str,
    background_tasks: BackgroundTasks,
    user = Depends(security.get_current_user),
):
    """Retry or backfill visual indexing for an existing library image."""
    uid = user["user_id"]
    asset = next((item for item in storage.list_assets(uid, mid) if item.get("asset_id") == aid), None)
    if not asset:
        raise HTTPException(404, "素材不存在")
    if asset.get("kind") != "image":
        raise HTTPException(400, "仅图片素材支持视觉分析")
    updated = storage.update_asset(uid, mid, aid, {
        "vision_status": "queued", "vision_error": "", "vision_model": asset_vision.VISION_MODEL,
    })
    background_tasks.add_task(_analyze_library_image, uid, mid, aid)
    return {"asset": updated}


@router.post("/{mid}/assets/{aid}/analyze")
def analyze_asset(
    mid: str,
    aid: str,
    background_tasks: BackgroundTasks,
    user = Depends(security.get_current_user),
):
    """Retry multimodal indexing for any supported library asset."""
    uid = user["user_id"]
    asset = next((item for item in storage.list_assets(uid, mid) if item.get("asset_id") == aid), None)
    if not asset:
        raise HTTPException(404, "素材不存在")
    patch = {"analysis_status": "queued", "analysis_error": ""}
    if asset.get("kind") == "image":
        patch.update({"vision_status": "queued", "vision_error": ""})
    updated = storage.update_asset(uid, mid, aid, patch)
    background_tasks.add_task(_analyze_library_asset, uid, mid, aid)
    return {"asset": updated}


@router.get("/{mid}/assets")
def list_assets(mid: str, user = Depends(security.get_current_user)):
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "未找到")
    return {"assets": storage.list_assets(user["user_id"], mid)}


@router.get("/{mid}/assets/catalog")
def asset_catalog(mid: str, user = Depends(security.get_current_user)):
    """Return the stable, video-ready material contract."""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "未找到")
    catalog = material_context.build_asset_catalog(user["user_id"], mid)
    return {
        "assets": catalog,
        "groups": material_context.group_asset_catalog(catalog),
    }


@router.post("/{mid}/assets/organize")
def organize_assets(
    mid: str,
    background_tasks: BackgroundTasks,
    user = Depends(security.get_current_user),
):
    """Return every file immediately and backfill analysis for legacy assets."""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "未找到")
    catalog = material_context.build_asset_catalog(user["user_id"], mid)
    stats = material_context.catalog_analysis_stats(catalog)
    queued_asset_ids = stats["not_analyzed_asset_ids"]
    raw_assets = {
        str(asset.get("asset_id")): asset
        for asset in storage.list_assets(user["user_id"], mid)
    }
    if os.getenv("DASHSCOPE_API_KEY", "").strip():
        for asset_id in queued_asset_ids:
            raw_asset = raw_assets.get(asset_id) or {}
            patch = {"analysis_status": "queued", "analysis_error": ""}
            if raw_asset.get("kind") == "image":
                patch.update({"vision_status": "queued", "vision_error": ""})
            storage.update_asset(user["user_id"], mid, asset_id, patch)
            background_tasks.add_task(
                _analyze_library_asset, user["user_id"], mid, asset_id
            )
    else:
        queued_asset_ids = []
    return {
        "assets": catalog,
        "groups": material_context.group_asset_catalog(catalog),
        "analysis": stats,
        "queued_asset_ids": queued_asset_ids,
        "video_ready_asset_ids": [
            asset["asset_id"]
            for asset in catalog
            if any(
                usage in asset.get("usable_for", [])
                for usage in (
                    "video_storyboard", "opening_or_ending", "narration",
                    "original_footage", "background_audio",
                )
            )
        ],
    }


@router.get("/{mid}/assets/{aid}")
def get_asset_file(mid: str, aid: str, user = Depends(security.get_current_user)):
    uid = user["user_id"]
    assets = storage.list_assets(uid, mid)
    a = next((x for x in assets if x.get("asset_id") == aid), None)
    if not a:
        raise HTTPException(404, "文件不存在")
    p = storage.memorial_dir(uid, mid) / "assets" / a.get("stored_name", "")
    if not p.exists():
        raise HTTPException(404, "文件已删除")
    return FileResponse(str(p), media_type=a.get("mime", "application/octet-stream"), filename=a.get("filename") or a.get("stored_name"))


class AssetPatchReq(__import__("pydantic").BaseModel):
    description: str | None = None
    user_description: str | None = None
    tags: list[str] | None = None
    usable_for: list[str] | None = None

@router.patch("/{mid}/assets/{aid}")
def patch_asset(mid: str, aid: str, req: AssetPatchReq, user = Depends(security.get_current_user)):
    patch = {k: v for k, v in req.dict().items() if v is not None}
    if "description" in patch and "user_description" not in patch:
        patch["user_description"] = patch["description"]
    if "user_description" in patch and "description" not in patch:
        patch["description"] = patch["user_description"]
    a = storage.update_asset(user["user_id"], mid, aid, patch)
    if not a:
        raise HTTPException(404, "文件不存在")
    return {"asset": a}

@router.delete("/{mid}/assets/{aid}")
def delete_asset(mid: str, aid: str, user = Depends(security.get_current_user)):
    asset = storage.delete_asset(user["user_id"], mid, aid)
    if not asset:
        raise HTTPException(404, "文件不存在")
    return {"deleted": True}
