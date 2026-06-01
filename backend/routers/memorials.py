# backend/routers/memorials.py — 纪念对象 + 资料库 + 对话历史
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from core import security, storage

router = APIRouter(prefix="/memorials", tags=["memorials"])


class CreateReq(BaseModel):
    name: str
    relation: str = ""
    note: str = ""

class UpdateMetaReq(BaseModel):
    name: Optional[str] = None
    relation: Optional[str] = None
    note: Optional[str] = None
    product_intent: Optional[str] = None


@router.get("")
def list_(user = Depends(security.get_current_user)):
    return {"memorials": storage.list_memorials(user["user_id"])}

@router.post("")
def create_(req: CreateReq, user = Depends(security.get_current_user)):
    m = storage.create_memorial(user["user_id"], req.name, req.relation, req.note)
    return {"memorial": m}

@router.get("/{mid}")
def detail(mid: str, user = Depends(security.get_current_user)):
    meta = storage.get_memorial(user["user_id"], mid)
    if not meta:
        raise HTTPException(404, "未找到")
    dossier = storage.get_dossier(user["user_id"], mid)
    assets = storage.list_assets(user["user_id"], mid)
    return {"meta": meta, "dossier": dossier, "assets": assets}

@router.patch("/{mid}")
def update_meta(mid: str, req: UpdateMetaReq, user = Depends(security.get_current_user)):
    patch = {k: v for k, v in req.dict().items() if v is not None}
    m = storage.update_memorial_meta(user["user_id"], mid, patch)
    if not m:
        raise HTTPException(404, "未找到")
    return {"memorial": m}

@router.delete("/{mid}")
def delete_(mid: str, user = Depends(security.get_current_user)):
    ok = storage.delete_memorial(user["user_id"], mid)
    return {"deleted": ok}


# ─── Dossier 资料库读写 ─────────────────────────────────────────
class DossierReplaceReq(BaseModel):
    dossier: dict

@router.get("/{mid}/dossier")
def get_dossier(mid: str, user = Depends(security.get_current_user)):
    return {"dossier": storage.get_dossier(user["user_id"], mid)}

@router.put("/{mid}/dossier")
def put_dossier(mid: str, req: DossierReplaceReq, user = Depends(security.get_current_user)):
    """用户在资料库页面整体保存（编辑后）。"""
    saved = storage.save_dossier(user["user_id"], mid, req.dossier)
    return {"dossier": saved}

@router.post("/{mid}/dossier/merge")
def merge_dossier(mid: str, req: DossierReplaceReq, user = Depends(security.get_current_user)):
    """增量合并（由 agent 调用，也允许前端调）。"""
    merged = storage.merge_dossier(user["user_id"], mid, req.dossier)
    return {"dossier": merged}


# ─── 对话历史 ───────────────────────────────────────────────────
@router.get("/{mid}/conversations")
def get_conv(mid: str, limit: int = 200, user = Depends(security.get_current_user)):
    return {"conversations": storage.read_conversations(user["user_id"], mid, limit=limit)}


# --- ���ڼ��� brief��qwen-plus �������� agent ע�룩---
from core import memory as _memory_mod

@router.get("/{mid}/memory")
def get_memory(mid: str, user = Depends(security.get_current_user)):
    d = storage.get_dossier(user["user_id"], mid) or {}
    return {
        "brief": d.get("memory_brief", ""),
        "updated_at": d.get("memory_brief_updated_at", ""),
    }

@router.post("/{mid}/memory/refresh")
def refresh_memory(mid: str, user = Depends(security.get_current_user)):
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "δ�ҵ�")
    b = _memory_mod.refresh_memory_brief(user["user_id"], mid, force=True)
    if not b:
        raise HTTPException(500, "��������ʧ��")
    return {"brief": b}
