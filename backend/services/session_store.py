# backend/services/session_store.py
# 内存级 session 存储，开发阶段够用；生产可替换为 Redis。
import threading
import time
import uuid
from typing import Any, Dict, Optional

from . import gate_manager

_LOCK = threading.RLock()
_SESSIONS: Dict[str, Dict[str, Any]] = {}

# session 自动清理时间（24 小时）
_TTL_SEC = 24 * 3600


def create_session(form_data: Optional[Dict[str, Any]] = None) -> str:
    sid = uuid.uuid4().hex
    with _LOCK:
        _SESSIONS[sid] = {
            "session_id":    sid,
            "created_at":    time.time(),
            "updated_at":    time.time(),
            "form_data":     dict(form_data or {}),
            "assets":        [],
            "chat_history":  [],
            "mv_outputs":    {},
            "preview_text":  "",
            "gate":          gate_manager.new_state(),
            "pipeline_state": {
                m: {"status": "pending", "duration_sec": None, "error": None}
                for m in gate_manager.GATE_ORDER
            },
            "ds_chat":       [],   # 深度搜索对话
            "ds_result":     None,
            # 数字人对话子状态（独立于 memorial 影像建档流程）
            "dialogue": {
                "persona_dna":      None,   # dict：聊天分析出的语言风格
                "persona_name":     "",
                "persona_override": "",     # 人设编辑器中累积的描述
                "message_count":    0,      # 已分析的消息条数
                "history":          [],     # [{role, content}]
            },
            # 人物传记生成子状态（BIO Pipeline）
            "bio_state": {
                "extracted_chunks": [],    # BIO01 输出：原始信息块
                "usable_chunks": [],       # BIO02 输出：过滤后的信息块
                "info_gaps": [],           # BIO02 输出：信息缺口列表
                "timeline": [],            # BIO03 输出：时间线结构
                "bio_draft": "",           # BIO04 输出：传记草稿 (Markdown)
                "bio_final": "",           # BIO05 输出：最终传记 (Markdown)
                "bio_json": {},            # BIO05 输出：结构化段落 JSON
                "quality_assessment": {},  # BIO05 输出：质量评审报告
                "control": {
                    "paused": False,
                    "canceled": False,
                },
                "step_status": {           # 各步骤执行状态
                    "BIO01": "pending",
                    "BIO02": "pending",
                    "BIO03": "pending",
                    "BIO04": "pending",
                    "BIO05": "pending",
                    "BIO06": "pending",
                },
                "last_error": None,        # 最后一次错误信息
            },
        }
    return sid


def get(sid: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        return _SESSIONS.get(sid)


def require(sid: str) -> Dict[str, Any]:
    s = get(sid)
    if not s:
        raise KeyError(f"session not found: {sid}")
    return s


def update(sid: str, **patches: Any) -> Dict[str, Any]:
    with _LOCK:
        s = _SESSIONS.get(sid)
        if s is None:
            raise KeyError(f"session not found: {sid}")
        for k, v in patches.items():
            s[k] = v
        s["updated_at"] = time.time()
        return s


def patch_form(sid: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        s = _SESSIONS.get(sid)
        if s is None:
            raise KeyError(f"session not found: {sid}")
        for k, v in fields.items():
            if v is not None:
                s["form_data"][k] = v
        s["updated_at"] = time.time()
        return s


def patch_bio_control(sid: str, paused: Optional[bool] = None, canceled: Optional[bool] = None) -> Dict[str, Any]:
    with _LOCK:
        s = _SESSIONS.get(sid)
        if s is None:
            raise KeyError(f"session not found: {sid}")
        control = s["bio_state"].setdefault("control", {"paused": False, "canceled": False})
        if paused is not None:
            control["paused"] = paused
        if canceled is not None:
            control["canceled"] = canceled
        s["updated_at"] = time.time()
        return s


def gc() -> int:
    """清理过期 session"""
    now = time.time()
    removed = 0
    with _LOCK:
        for sid in list(_SESSIONS.keys()):
            if now - _SESSIONS[sid]["updated_at"] > _TTL_SEC:
                del _SESSIONS[sid]
                removed += 1
    return removed


def list_ids() -> list:
    with _LOCK:
        return list(_SESSIONS.keys())
