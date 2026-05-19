# backend/services/gate_manager.py
# 不依赖 Streamlit 的纯内存版门控管理器。
# 每个 session 维护独立的 gate 状态，由 session_store 持有。
from typing import Any, Dict, List

GATE_ORDER: List[str] = ["MV01", "MV02", "MV03", "MV04", "MV05", "MV06"]


def new_state() -> Dict[str, Any]:
    """返回一个全新的 gate 状态字典"""
    return {
        "gate_status":    {g: "pending" for g in GATE_ORDER},
        "gate_rejections": {g: {} for g in GATE_ORDER},
    }


def get_status(state: Dict[str, Any], gate: str) -> str:
    return state["gate_status"].get(gate, "pending")


def set_running(state: Dict[str, Any], gate: str) -> None:
    state["gate_status"][gate] = "running"


def set_awaiting_review(state: Dict[str, Any], gate: str) -> None:
    state["gate_status"][gate] = "awaiting_review"


def approve(state: Dict[str, Any], gate: str) -> None:
    state["gate_status"][gate] = "approved"
    state["gate_rejections"][gate] = {}


def reject(state: Dict[str, Any], gate: str, scope: Dict[str, Any]) -> None:
    state["gate_status"][gate] = "rejected"
    state["gate_rejections"][gate] = scope


def can_run(state: Dict[str, Any], gate: str) -> bool:
    if gate not in GATE_ORDER:
        return False
    idx = GATE_ORDER.index(gate)
    if idx == 0:
        return True
    return state["gate_status"].get(GATE_ORDER[idx - 1]) == "approved"


def reset_from(state: Dict[str, Any], gate: str) -> None:
    if gate not in GATE_ORDER:
        return
    start = GATE_ORDER.index(gate)
    for g in GATE_ORDER[start:]:
        state["gate_status"][g] = "pending"
        state["gate_rejections"][g] = {}
