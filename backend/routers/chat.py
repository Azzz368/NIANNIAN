# backend/routers/chat.py
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import service_manager as sm
from services import session_store

router = APIRouter(prefix="/chat", tags=["chat"])


class GreetingReq(BaseModel):
    session_id: str


@router.post("/greeting")
def greeting(req: GreetingReq) -> Dict[str, Any]:
    try:
        s = session_store.require(req.session_id)
    except KeyError:
        raise HTTPException(404, "session not found")
    text = sm.memorial_greeting(s["form_data"])
    s["chat_history"].append({"role": "assistant", "content": text})
    return {"reply": text, "chat_history": s["chat_history"]}


class MessageReq(BaseModel):
    session_id: str
    message: str


@router.post("/message")
def message(req: MessageReq) -> Dict[str, Any]:
    try:
        s = session_store.require(req.session_id)
    except KeyError:
        raise HTTPException(404, "session not found")
    if not req.message.strip():
        raise HTTPException(400, "empty message")
    s["chat_history"].append({"role": "user", "content": req.message.strip()})
    reply = sm.memorial_reply(s["form_data"], s["chat_history"])
    s["chat_history"].append({"role": "assistant", "content": reply})
    return {"reply": reply, "chat_history": s["chat_history"]}


class GenerateJsonReq(BaseModel):
    session_id: str


@router.post("/generate-json")
def generate_json(req: GenerateJsonReq) -> Dict[str, Any]:
    """对话结束，生成结构化 JSON（即触发 MV01）"""
    return sm.run_pipeline_step(req.session_id, "MV01")


@router.get("/preview/{sid}")
def preview(sid: str) -> Dict[str, Any]:
    try:
        s = session_store.require(sid)
    except KeyError:
        raise HTTPException(404, "session not found")
    text = s.get("preview_text") or ""
    if not text:
        # 简易生平预览：从 form_data 拼接
        fd = s["form_data"]
        parts = []
        if fd.get("deceased_name"):
            parts.append(f"亲人：{fd['deceased_name']}")
        if fd.get("birth_date") or fd.get("death_date"):
            parts.append(f"{fd.get('birth_date','')} — {fd.get('death_date','在世')}")
        if fd.get("occupation"):
            parts.append(f"身份：{fd['occupation']}")
        if fd.get("family_memory_text"):
            parts.append(fd["family_memory_text"][:500])
        text = "\n\n".join(parts)
        s["preview_text"] = text
    return {"preview_text": text}
