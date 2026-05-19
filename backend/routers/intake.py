# backend/routers/intake.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import service_manager as sm
from services import session_store

router = APIRouter(prefix="/intake", tags=["intake"])


class IntakeSubmit(BaseModel):
    session_id: Optional[str] = None
    form_data: Dict[str, Any] = {}


@router.post("/submit")
def submit(payload: IntakeSubmit) -> Dict[str, Any]:
    """提交/更新表单。无 session_id 时新建一个。"""
    if payload.session_id:
        try:
            s = session_store.patch_form(payload.session_id, payload.form_data)
        except KeyError:
            sid = session_store.create_session(payload.form_data)
            s = session_store.require(sid)
    else:
        sid = session_store.create_session(payload.form_data)
        s = session_store.require(sid)
    return {
        "session_id": s["session_id"],
        "form_data":  s["form_data"],
    }


@router.get("/test-data")
def test_data() -> Dict[str, Any]:
    """返回测试用人物数据（陈文斌）"""
    return {"form_data": sm.TEST_DATA}


@router.get("/session/{sid}")
def get_session(sid: str) -> Dict[str, Any]:
    s = session_store.get(sid)
    if not s:
        raise HTTPException(404, "session not found")
    # 排除大对象
    return {
        "session_id":     s["session_id"],
        "form_data":      s["form_data"],
        "assets":         s["assets"],
        "chat_history":   s["chat_history"],
        "preview_text":   s["preview_text"],
        "pipeline_state": s["pipeline_state"],
        "mv_outputs_keys": list(s["mv_outputs"].keys()),
    }


# ── 深度搜索（Deep Search Agent）──────────────────────────────────────────
class DeepSearchReq(BaseModel):
    query: str
    extra: str = ""
    session_id: Optional[str] = None


@router.post("/deep-search")
def deep_search(req: DeepSearchReq) -> Dict[str, Any]:
    if not req.query.strip():
        raise HTTPException(400, "query required")
    result = sm.deep_search(req.query.strip(), req.extra)
    fields = sm.deep_search_extract_fields(result["organized"], req.query.strip())

    # 写入 session（如有）
    if req.session_id:
        s = session_store.get(req.session_id)
        if s is not None:
            s["ds_chat"].append({"role": "user", "content": req.query.strip()})
            s["ds_chat"].append({"role": "ai",   "content": result["organized"]})
            s["ds_result"] = {"organized": result["organized"], "fields": fields}

    return {
        "organized":  result["organized"],
        "model":      result["model"],
        "fallback":   result["fallback"],
        "fields":     fields,
    }


class ApplyFieldsReq(BaseModel):
    session_id: str
    fields: Dict[str, Any]


@router.post("/apply-fields")
def apply_fields(req: ApplyFieldsReq) -> Dict[str, Any]:
    """将深度搜索提取的字段写入 form_data"""
    try:
        s = session_store.patch_form(req.session_id, req.fields)
    except KeyError:
        raise HTTPException(404, "session not found")
    return {"ok": True, "form_data": s["form_data"]}
