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
            if v not in (None, ""):
                s["form_data"][k] = v
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
