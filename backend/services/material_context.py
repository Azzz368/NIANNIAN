"""Memorial material catalog, retrieval, and MV-pipeline context assembly.

The persistent memorial library is the source of truth.  AI-derived metadata is
kept separate from the user's own description so downstream generation can
prefer first-hand context without losing machine-searchable annotations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from core import storage


VIDEO_USES = {
    "image": ["person_reference", "video_storyboard", "opening_or_ending", "digital_human"],
    "audio": ["narration", "background_audio", "digital_human_voice"],
    "video": ["video_storyboard", "opening_or_ending", "original_footage", "background_audio"],
    "document": ["narration", "video_storyboard", "biography_chapter"],
    "text": ["narration", "video_storyboard", "digital_human_memory"],
    "other": ["dossier"],
}

INVENTORY_PHRASES = (
    "有哪些素材", "整理素材", "素材清单", "素材库", "可用于视频",
    "适合做视频", "按人物", "按时间", "按事件", "按场景",
    "有什么素材", "全部素材", "所有素材", "素材统计",
)

FULL_LISTING_PHRASES = (
    "有哪些素材", "有什么素材", "素材库有什么", "素材清单",
    "全部素材", "所有素材", "素材统计",
)


def _text(value: Any, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _list(value: Any, limit: int = 12) -> List[str]:
    if isinstance(value, str):
        value = re.split(r"[,，、；;\n]+", value)
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = _text(item, 80)
        if text and text not in out:
            out.append(text)
    return out[:limit]


def _merge_lists(*values: Any, limit: int = 16) -> List[str]:
    out: List[str] = []
    for value in values:
        for item in _list(value, limit=limit):
            if item not in out:
                out.append(item)
    return out[:limit]


def normalize_asset(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Return the stable asset contract consumed by Agent and MV skills."""
    kind = _text(asset.get("kind") or "other", 24).lower()
    user_description = _text(
        asset.get("user_description") or asset.get("description"), 2000
    )
    ai_summary = _text(
        asset.get("ai_summary")
        or asset.get("visual_summary")
        or asset.get("summary"),
        1200,
    )
    usable_for = _merge_lists(
        asset.get("usable_for"),
        VIDEO_USES.get(kind, VIDEO_USES["other"]),
    )
    return {
        "asset_id": _text(asset.get("asset_id"), 80),
        "kind": kind,
        "filename": _text(asset.get("filename"), 300),
        "url": _text(asset.get("url"), 1000),
        "mime": _text(asset.get("mime"), 100),
        "user_description": user_description,
        "transcript": _text(asset.get("transcript"), 6000),
        "ai_summary": ai_summary,
        "people": _list(asset.get("people") or asset.get("visual_people")),
        "time_period": _text(asset.get("time_period") or asset.get("period"), 120),
        "event": _text(asset.get("event"), 500),
        "scene": _text(asset.get("scene") or asset.get("visual_scene"), 500),
        "objects": _list(asset.get("objects")),
        "emotion": _list(asset.get("emotion")),
        "tags": _merge_lists(asset.get("tags"), asset.get("visual_tags")),
        "usable_for": usable_for,
        "related_memory_ids": _list(asset.get("related_memory_ids")),
        "vision_status": _text(
            asset.get("vision_status") or asset.get("analysis_status") or "not_analyzed",
            40,
        ),
        "analysis_status": _text(asset.get("analysis_status"), 40),
        "created_at": _text(asset.get("created_at"), 80),
    }


def build_asset_catalog(user_id: str, memorial_id: str) -> List[Dict[str, Any]]:
    return [
        normalize_asset(asset)
        for asset in storage.list_assets(user_id, memorial_id)
        if asset.get("asset_id")
    ]


def group_asset_catalog(catalog: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    assets = list(catalog)
    by_kind: Dict[str, List[str]] = {}
    by_time: Dict[str, List[str]] = {}
    by_person: Dict[str, List[str]] = {}
    by_event: Dict[str, List[str]] = {}
    by_scene: Dict[str, List[str]] = {}
    by_use: Dict[str, List[str]] = {}

    def add(group: Dict[str, List[str]], key: str, asset_id: str) -> None:
        key = _text(key, 80)
        if not key or not asset_id:
            return
        group.setdefault(key, [])
        if asset_id not in group[key]:
            group[key].append(asset_id)

    for asset in assets:
        aid = asset.get("asset_id", "")
        add(by_kind, asset.get("kind", "other"), aid)
        add(by_time, asset.get("time_period", ""), aid)
        add(by_event, asset.get("event", ""), aid)
        add(by_scene, asset.get("scene", ""), aid)
        for person in asset.get("people", []):
            add(by_person, person, aid)
        for usage in asset.get("usable_for", []):
            add(by_use, usage, aid)

    return {
        "total": len(assets),
        "by_kind": by_kind,
        "by_time": by_time,
        "by_person": by_person,
        "by_event": by_event,
        "by_scene": by_scene,
        "by_use": by_use,
    }


def catalog_analysis_stats(catalog: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Describe indexing coverage without confusing unindexed files with missing files."""
    assets = list(catalog)
    statuses: Dict[str, int] = {}
    pending_ids: List[str] = []
    for asset in assets:
        status = _text(asset.get("vision_status") or "not_analyzed", 40)
        statuses[status] = statuses.get(status, 0) + 1
        if status in ("", "not_analyzed"):
            pending_ids.append(_text(asset.get("asset_id"), 80))
    return {
        "total": len(assets),
        "analyzed": statuses.get("succeeded", 0),
        "pending": statuses.get("queued", 0),
        "failed": statuses.get("failed", 0),
        "not_analyzed": len(pending_ids),
        "not_analyzed_asset_ids": [asset_id for asset_id in pending_ids if asset_id],
        "by_status": statuses,
    }


def is_inventory_query(query: str) -> bool:
    compact = (query or "").replace(" ", "")
    return any(phrase in compact for phrase in INVENTORY_PHRASES)


def is_full_listing_query(query: str) -> bool:
    compact = (query or "").replace(" ", "")
    return any(phrase in compact for phrase in FULL_LISTING_PHRASES)


def _terms(text: str) -> set[str]:
    lowered = (text or "").lower()
    words = set(re.findall(r"[a-z0-9]{2,}", lowered))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    words.update(
        chinese[index:index + 2]
        for index in range(max(0, len(chinese) - 1))
        if len(chinese[index:index + 2]) == 2
    )
    return {word for word in words if word}


def _asset_score(query: str, asset: Dict[str, Any]) -> int:
    query_terms = _terms(query)
    if not query_terms:
        return 0
    user_text = " ".join([
        asset.get("filename", ""),
        asset.get("user_description", ""),
        asset.get("time_period", ""),
        asset.get("event", ""),
    ]).lower()
    ai_text = " ".join([
        asset.get("ai_summary", ""),
        asset.get("scene", ""),
        " ".join(asset.get("people", [])),
        " ".join(asset.get("objects", [])),
        " ".join(asset.get("emotion", [])),
        " ".join(asset.get("tags", [])),
        asset.get("transcript", ""),
    ]).lower()
    score = sum(3 for term in query_terms if term in user_text)
    score += sum(1 for term in query_terms if term in ai_text)
    if "照片" in query and asset.get("kind") == "image":
        score += 2
    if "录音" in query and asset.get("kind") == "audio":
        score += 2
    if "视频" in query and asset.get("kind") == "video":
        score += 2
    if "文档" in query and asset.get("kind") in ("document", "text"):
        score += 2
    return score


def search_asset_catalog(
    query: str,
    catalog: Iterable[Dict[str, Any]],
    limit: int = 8,
) -> List[Dict[str, Any]]:
    assets = list(catalog)
    if is_inventory_query(query):
        return assets[:limit]
    ranked = [
        (_asset_score(query, asset), asset.get("created_at", ""), asset)
        for asset in assets
    ]
    ranked = [item for item in ranked if item[0] > 0]
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked[:limit]]


def is_high_confidence_image_asset(asset: Dict[str, Any]) -> bool:
    """Return whether an image has enough verified analysis to be reused as real media.

    A merely uploaded portrait should not automatically become a repeated dynamic clip.
    Require a completed visual analysis plus substantive user- or AI-confirmed context.
    """
    if asset.get("kind") != "image":
        return False
    # New uploads always carry an explicit analysis_status and must finish visual
    # analysis first. Legacy assets without that field remain eligible only when a
    # sufficiently detailed user description provides factual grounding.
    analysis_status = str(asset.get("analysis_status") or "").strip().lower()
    if analysis_status and analysis_status != "succeeded":
        return False
    evidence = " ".join(str(value or "") for value in (
        asset.get("user_description"), asset.get("visual_summary"),
        asset.get("ai_summary"), asset.get("scene"), asset.get("event"),
        asset.get("time_period"),
    )).strip()
    signals = sum(bool(value) for value in (
        asset.get("people"), asset.get("objects"), asset.get("visual_tags"),
        asset.get("tags"), asset.get("emotion"), asset.get("event"), asset.get("scene"),
        asset.get("user_description"), asset.get("ai_summary"),
    ))
    return len(evidence) >= 18 and signals >= 1


def build_memorial_context(session: Dict[str, Any]) -> Dict[str, Any]:
    """Build one bounded context shared by MV01-MV04."""
    form_data = dict(session.get("form_data") or {})
    user_id = _text(form_data.get("user_id"), 100)
    memorial_id = _text(form_data.get("memorial_id"), 100)
    dossier: Dict[str, Any] = {}
    persistent_conversations: List[Dict[str, Any]] = []
    catalog: List[Dict[str, Any]] = []

    if user_id and memorial_id and storage.get_memorial(user_id, memorial_id):
        dossier = storage.get_dossier(user_id, memorial_id) or {}
        persistent_conversations = storage.read_conversations(
            user_id, memorial_id, limit=80
        )
        catalog = build_asset_catalog(user_id, memorial_id)
    else:
        catalog = [
            normalize_asset(asset)
            for asset in (session.get("assets") or [])
            if isinstance(asset, dict)
        ]

    # 当建档页显式勾选资料库照片时，分镜只使用这些图片；音频、视频和文本素材仍保留。
    # 未提供字段的旧会话保持完整素材库行为。
    if "selected_asset_ids" in form_data:
        selected_ids = {
            str(asset_id) for asset_id in (form_data.get("selected_asset_ids") or [])
            if asset_id
        }
        catalog = [
            asset for asset in catalog
            if asset.get("kind") != "image" or asset.get("asset_id") in selected_ids
        ]

    session_chat = [
        {
            "role": _text(turn.get("role"), 24),
            "content": _text(turn.get("content"), 1500),
        }
        for turn in (session.get("chat_history") or [])[-60:]
        if isinstance(turn, dict) and turn.get("content")
    ]
    agent_chat = [
        {
            "role": _text(turn.get("role"), 24),
            "content": _text(turn.get("content"), 1500),
        }
        for turn in persistent_conversations[-60:]
        if isinstance(turn, dict) and turn.get("content")
    ]

    return {
        "user_id": user_id,
        "memorial_id": memorial_id,
        "form_data": form_data,
        "subject": dossier.get("subject") or {},
        "dossier": dossier,
        "session_chat_history": session_chat,
        "agent_conversation_history": agent_chat,
        "assets": catalog[:80],
        "asset_groups": group_asset_catalog(catalog),
        "source_priority": [
            "user_description",
            "transcript",
            "dossier",
            "ai_summary",
        ],
    }


def attach_assets_to_storyboard(
    mv04_result: Dict[str, Any],
    memorial_context: Dict[str, Any],
    max_assets_per_scene: int = 2,
) -> Dict[str, Any]:
    """Validate model references and deterministically bind real assets to scenes."""
    if not isinstance(mv04_result, dict):
        return mv04_result
    catalog = memorial_context.get("assets") or []
    by_id = {
        asset.get("asset_id"): asset
        for asset in catalog
        if isinstance(asset, dict) and asset.get("asset_id")
    }
    raw_scenes = mv04_result.get("scenes")
    if isinstance(raw_scenes, dict):
        scenes = [raw_scenes[key] for key in sorted(raw_scenes)]
    elif isinstance(raw_scenes, list):
        scenes = raw_scenes
    elif isinstance(mv04_result.get("storyboard"), list):
        scenes = mv04_result["storyboard"]
    else:
        return mv04_result

    used_image_ids: set[str] = set()
    strict_min_score = 3
    skipped_recommendations: List[Dict[str, Any]] = []

    for scene_index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        query = " ".join(
            _text(scene.get(key), 1000)
            for key in (
                "description", "scene_desc", "visual", "voice_script",
                "narration", "subject", "scene_ref",
            )
            if scene.get(key)
        )
        requested: List[str] = []
        for value in (
            scene.get("source_asset_ids"),
            scene.get("asset_ids"),
            [scene.get("asset_ref")] if scene.get("asset_ref") else [],
        ):
            for asset_id in _list(value, limit=max_assets_per_scene):
                if asset_id in by_id and asset_id not in requested:
                    requested.append(asset_id)

        # Explicit user/model references remain valid, but automatic recommendations
        # are deliberately stricter: no duplicate image across scenes, no unanalyzed
        # upload, and no weak keyword match.
        matched = [
            asset_id for asset_id in requested
            if asset_id not in used_image_ids or by_id.get(asset_id, {}).get("kind") != "image"
        ][:max_assets_per_scene]
        if not matched:
            image_candidates = [
                asset for asset in catalog
                if is_high_confidence_image_asset(asset)
                and asset.get("asset_id") not in used_image_ids
            ]
            ranked = search_asset_catalog(query, image_candidates, limit=max_assets_per_scene * 3)
            high_score_candidates = [
                asset
                for asset in ranked
                if _asset_score(query, asset) >= strict_min_score
            ]
            # Reuse the existing visual-semantic ranker after strict factual filtering.
            # It does not add a new agent or script; it ranks the already analysed
            # library descriptions to prefer the picture that covers this scene's
            # missing person/time/place/object elements.
            try:
                from services import asset_vision

                semantic_ids = asset_vision.semantic_rank_assets(
                    query, high_score_candidates, limit=max_assets_per_scene
                )
            except Exception:
                semantic_ids = []
            matched = semantic_ids or [
                asset["asset_id"]
                for asset in high_score_candidates
            ][:max_assets_per_scene]

        selected = [by_id[asset_id] for asset_id in matched if asset_id in by_id]
        used_image_ids.update(
            str(asset.get("asset_id")) for asset in selected if asset.get("kind") == "image"
        )
        scene["source_asset_ids"] = [asset["asset_id"] for asset in selected]
        scene["source_assets"] = [
            {
                "asset_id": asset["asset_id"],
                "kind": asset["kind"],
                "filename": asset["filename"],
                "url": asset["url"],
                "user_description": asset["user_description"],
                "ai_summary": asset["ai_summary"],
            }
            for asset in selected
        ]
        if selected:
            scene["asset_type"] = "user_asset"
            scene["asset_ref"] = selected[0]["asset_id"]
            scene["media_strategy"] = "reuse_real_asset"
            scene["asset_usage_reason"] = (
                selected[0]["user_description"]
                or selected[0]["ai_summary"]
                or "与本镜头内容相关的真实素材"
            )[:240]
        else:
            scene["media_strategy"] = "ai_generated"
            scene.setdefault("source_asset_ids", [])
            skipped_recommendations.append({
                "scene_index": scene_index,
                "scene_id": scene.get("scene_id") or scene.get("id") or "",
                "reason": "资料库中没有同时满足视觉分析完成、语义高度相关且未被其他分镜使用的真实图片；建议保留 AI 画面。",
            })

    mv04_result["material_usage"] = {
        "real_asset_scene_count": sum(
            1 for scene in scenes
            if isinstance(scene, dict) and scene.get("source_asset_ids")
        ),
        "total_scene_count": len(scenes),
        "strict_min_score": strict_min_score,
        "skipped_recommendations": skipped_recommendations,
    }
    return mv04_result
