# backend/core/memory.py — 念念长期记忆：用 qwen-plus 把对话+档案精炼成 200 字 brief
"""
策略：
- 触发条件：
  1) 每 4 轮新增对话自动刷新一次（_persist_and_extract 里调用）
  2) 用户语音/文字中说出关键词（记一下/记住/总结一下/重点）立即刷新
  3) 前端手动触发 POST /api/memorials/{mid}/memory/refresh
- 生成内容：
  一段 ≤ 200 字的中文白描，包含：对象身份、关系、性格底色、3~5 个最重要的记忆/金句、
  用户的产品倾向、当前正在聊的话题。
- 注入：
  realtime / text agent 在每次新会话/SSE 开头都把 brief 拼进 system prompt 最前面。
"""
import os
import json
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

from . import storage
from .dashscope_config import compatible_base_url


MEMORY_KEYWORDS = (
    "记一下", "记住", "请记住", "总结一下", "重点", "标记一下",
    "我说完了", "下次记得", "别忘了",
)


def has_memory_trigger(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    for kw in MEMORY_KEYWORDS:
        if kw in t:
            return True
    return False


def _client():
    if OpenAI is None or not os.getenv("DASHSCOPE_API_KEY"):
        return None
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url=compatible_base_url(),
    )


def refresh_memory_brief(user_id: str, memorial_id: str, force: bool = False) -> Optional[str]:
    """调用 qwen-plus 重新生成 memory_brief，写回 dossier。返回新 brief 或 None。"""
    cli = _client()
    if cli is None:
        return None
    try:
        dossier = storage.get_dossier(user_id, memorial_id) or {}
        convs = storage.read_conversations(user_id, memorial_id, limit=30) or []
        if not convs and not dossier.get("subject", {}).get("name"):
            return None  # 完全没素材，跳过

        # 紧凑上下文（不要塞太多）
        subj = dossier.get("subject", {}) or {}
        pers = (dossier.get("personality") or {}).get("keywords") or []
        mems = dossier.get("memories") or []
        quotes = dossier.get("quotes") or []
        pi = (dossier.get("product_intent") or {}).get("primary") or ""

        ctx_parts = []
        if subj.get("name") or subj.get("relation"):
            ctx_parts.append(f"对象：{subj.get('name','')}（{subj.get('relation','')}）"
                             f" {subj.get('birth','')}~{subj.get('passing','')}")
        if pers:
            ctx_parts.append("性格关键词：" + "，".join(pers[:10]))
        if mems:
            ctx_parts.append("记忆片段：" + " | ".join(
                [f"{(m.get('title') or '')}-{(m.get('content') or '')[:40]}" for m in mems[-6:]]
            ))
        if quotes:
            ctx_parts.append("金句：" + " / ".join(quotes[:5]))
        if pi:
            ctx_parts.append(f"用户产品倾向：{pi}")

        # 最近对话（精简）
        conv_text = []
        for c in convs[-20:]:
            role = "用户" if c.get("role") == "user" else "念念"
            txt = (c.get("content") or "").strip().replace("\n", " ")
            if len(txt) > 100:
                txt = txt[:100] + "…"
            conv_text.append(f"{role}：{txt}")

        prompt = f"""你是「念念」追思助手的记忆整理 Agent。请把下面的资料和最近对话整理成一段【中文长期记忆 brief】，供念念在下一次对话时秒级回忆起这位用户和 ta 正在聊的人。

要求：
- 长度 150~220 字，一段，不要分点不要 Markdown
- 用第三人称白描，开头先说"用户正在追忆 XXX（关系）"
- 包含：身份信息、性格底色、3~5 个最具体的记忆/物件/金句、用户的产品倾向（如果有）、当前对话焦点
- **不要编造**，只整理已知信息
- 末尾用一句话指出"下次接续聊"的最佳切入点

【已知资料】
{chr(10).join(ctx_parts) if ctx_parts else '(暂无)'}

【最近对话】
{chr(10).join(conv_text) if conv_text else '(暂无)'}

直接输出 brief 文本，不要加任何前缀。"""

        resp = cli.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        brief = (resp.choices[0].message.content or "").strip()
        if not brief or len(brief) < 20:
            return None

        # 写回 dossier
        dossier["memory_brief"] = brief
        dossier["memory_brief_updated_at"] = storage.now_iso()
        storage.save_dossier(user_id, memorial_id, dossier)
        print(f"[memory] brief refreshed for {user_id}/{memorial_id}: {brief[:60]}...")
        return brief
    except Exception as e:
        print(f"[memory] refresh failed: {e}")
        return None


def get_memory_brief(user_id: str, memorial_id: str) -> str:
    try:
        d = storage.get_dossier(user_id, memorial_id) or {}
        return (d.get("memory_brief") or "").strip()
    except Exception:
        return ""


def maybe_refresh(user_id: str, memorial_id: str, user_msg: str = "") -> Optional[str]:
    """决定要不要刷新：关键词触发 / 每 4 轮触发。返回新 brief 或 None。"""
    try:
        if user_msg and has_memory_trigger(user_msg):
            return refresh_memory_brief(user_id, memorial_id, force=True)
        # 每 4 轮自动刷新（按对话总条数：user+assistant=2 条算一轮，所以 8 条触发一次）
        convs = storage.read_conversations(user_id, memorial_id, limit=200) or []
        if len(convs) > 0 and len(convs) % 8 == 0:
            return refresh_memory_brief(user_id, memorial_id)
    except Exception as e:
        print(f"[memory] maybe_refresh failed: {e}")
    return None
