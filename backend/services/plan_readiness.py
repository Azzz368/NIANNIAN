"""Deterministic readiness checks shared by the director-script workflow."""

from __future__ import annotations

from typing import Any, Dict, List

from core import storage
from services import material_context


def _text(value: Any, limit: int = 2000) -> str:
    return str(value or "").strip()[:limit]


def _nonempty_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _meaningful_memory(memory: Any) -> bool:
    if isinstance(memory, dict):
        return bool(_text(memory.get("title")) or _text(memory.get("content")))
    return bool(_text(memory))


def evaluate_readiness(user_id: str, memorial_id: str) -> Dict[str, Any]:
    """Return current collection coverage; this never authors script content."""
    meta = storage.get_memorial(user_id, memorial_id)
    if not meta:
        raise KeyError("未找到当前人物资料库")

    dossier = storage.get_dossier(user_id, memorial_id) or {}
    subject = dossier.get("subject") or {}
    memories = [m for m in _nonempty_list(dossier.get("memories")) if _meaningful_memory(m)]
    conversations = storage.read_conversations(user_id, memorial_id, limit=200)
    user_turns = [t for t in conversations if t.get("role") == "user" and _text(t.get("content"))]
    catalog = material_context.build_asset_catalog(user_id, memorial_id)
    visual_assets = [a for a in catalog if a.get("kind") in ("image", "video")]
    described_assets = [
        a for a in catalog
        if a.get("user_description") or a.get("transcript") or a.get("ai_summary")
    ]

    name = _text(subject.get("name") or meta.get("name"))
    relation = _text(subject.get("relation") or meta.get("relation"))
    personality = dossier.get("personality") or {}
    narrative_signals = (
        len(memories)
        + len(_nonempty_list(dossier.get("quotes")))
        + len(_nonempty_list(personality.get("keywords")))
        + len(_nonempty_list(personality.get("habits")))
    )

    score = 0
    score += 15 if name and name != "未命名" else 0
    score += 5 if relation else 0
    score += min(25, len(memories) * 15 + max(0, narrative_signals - len(memories)) * 5)
    score += 15 if visual_assets else 0
    score += 10 if len(visual_assets) >= 3 else 0
    score += min(10, len(described_assets) * 3)
    score += min(10, len(user_turns) * 2)
    score = min(100, score)

    missing: List[Dict[str, str]] = []
    if not name or name == "未命名":
        missing.append({"field": "subject.name", "label": "人物姓名或称呼"})
    if not relation:
        missing.append({"field": "subject.relation", "label": "您与人物的关系"})
    if not visual_assets:
        missing.append({"field": "visual_assets", "label": "至少一张图片或一段视频"})
    if not memories and not described_assets:
        missing.append({"field": "story", "label": "至少一个真实事件或一项素材说明"})
    elif visual_assets and not any(a in described_assets for a in visual_assets):
        missing.append({"field": "asset_context", "label": "至少一项图片或视频的故事说明"})

    questions = {
        "subject.name": "这段视频主要想纪念谁？您平时怎么称呼 Ta？",
        "subject.relation": "Ta 与您是什么关系？",
        "visual_assets": "请先上传至少一张希望放进视频的照片或一段视频。",
        "story": "您最希望视频记住 Ta 的哪一件真实往事？",
        "asset_context": "这些照片里，哪一张对您最重要？它是什么时候、在哪里拍的？",
    }
    critical_ok = bool(name and name != "未命名" and visual_assets and (memories or described_assets))
    ready = critical_ok and score >= 55
    next_question = questions.get(missing[0]["field"], "") if missing else ""

    return {
        "mode": "director_script",
        "ready": ready,
        "score": score,
        "threshold": 55,
        "missing_fields": missing,
        "next_question": next_question,
        "can_generate_director_script": ready,
        # Compatibility for the current browser state during this transition.
        "can_generate_edit_plan": ready,
        "stats": {
            "conversation_user_turns": len(user_turns),
            "memories": len(memories),
            "assets": len(catalog),
            "visual_assets": len(visual_assets),
            "described_assets": len(described_assets),
        },
    }
