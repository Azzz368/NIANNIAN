"""Shared DashScope endpoint selection for Agent and material services."""

import os


def region() -> str:
    """Return ``intl`` or ``cn`` from the deployment environment."""
    value = (os.getenv("DASHSCOPE_REGION", "intl") or "intl").strip().lower()
    return "cn" if value in {"cn", "china", "domestic", "beijing"} else "intl"


def compatible_base_url() -> str:
    if region() == "cn":
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"


def realtime_ws_url(model: str = "qwen3.5-omni-plus-realtime") -> str:
    host = "dashscope.aliyuncs.com" if region() == "cn" else "dashscope-intl.aliyuncs.com"
    return f"wss://{host}/api-ws/v1/realtime?model={model}"
