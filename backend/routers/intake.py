# backend/routers/intake.py
from typing import Any, Dict, Optional
import json, time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import service_manager as sm
from services import session_store
from core import storage as st

router = APIRouter(prefix="/intake", tags=["intake"])


class IntakeSubmit(BaseModel):
    session_id: Optional[str] = None
    form_data: Dict[str, Any] = {}
    reset_chat: bool = False


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
    if payload.reset_chat:
        s["chat_history"] = []
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
    memorial_id: Optional[str] = None   # 有则自动归档并写入 dossier
    user_id: Optional[str] = None       # 配合 memorial_id 使用


@router.post("/deep-search")
def deep_search(req: DeepSearchReq) -> Dict[str, Any]:
    if not req.query.strip():
        raise HTTPException(400, "query required")
    result = sm.deep_search(req.query.strip(), req.extra)
    # deep_search 现在直接返回结构化字段，无需二次提取
    fields = {k: result[k] for k in ("name","birth_date","death_date","occupation",
              "locations","personality_keywords","quotes","objects","core_memories",
              "family_memory_text")
              if k in result}

    archived_path: Optional[str] = None
    dossier_updated = False

    # ── 归档 + 写入 dossier（需要 user_id + memorial_id）──
    uid = (req.user_id or "").strip()
    mid = (req.memorial_id or "").strip()
    if uid and mid:
        try:
            # 1) 归档 JSON 到 memorial 目录下的 search_archives/
            archive_dir = st.memorial_dir(uid, mid) / "search_archives"
            archive_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            version = len(list(archive_dir.glob("*.json"))) + 1
            fname = f"search_{ts}_v{version}.json"
            archive_data = {
                "version": version,
                "archived_at": st.now_iso(),
                "query": req.query.strip(),
                "extra": req.extra,
                "model": result["model"],
                "fallback": result["fallback"],
                "organized": result["organized"],
                "fields": fields,
            }
            fpath = archive_dir / fname
            fpath.write_text(json.dumps(archive_data, ensure_ascii=False, indent=2), encoding="utf-8")
            archived_path = str(fpath.relative_to(st.DATA_DIR))

            # 2) 写入 dossier
            # deep_search 现在直接在 result 里返回结构化字段
            dossier = st.get_dossier(uid, mid)
            if not isinstance(dossier, dict):
                dossier = st.default_dossier()

            # subject 基础信息（只填空字段，不覆盖已有数据）
            subj = dossier.setdefault("subject", {})
            def _fill(key, val):
                if val and not subj.get(key):
                    subj[key] = val
            _fill("name",       result.get("name", ""))
            _fill("birth",      result.get("birth_date", ""))
            _fill("passing",    result.get("death_date", ""))
            _fill("occupation", result.get("occupation", ""))
            locs = result.get("locations", [])
            if locs and not subj.get("locations"):
                subj["locations"] = locs

            # personality keywords
            pkeys = result.get("personality_keywords", [])
            if pkeys:
                existing_kw = dossier.setdefault("personality", {}).setdefault("keywords", [])
                for kw in pkeys:
                    if kw and kw not in existing_kw:
                        existing_kw.append(kw)

            # quotes（金句）
            new_quotes = result.get("quotes", [])
            if new_quotes:
                existing_q = dossier.setdefault("quotes", [])
                for q in new_quotes:
                    if q and q not in existing_q:
                        existing_q.append(q)

            # objects（代表性物件）
            new_objs = result.get("objects", [])
            if new_objs:
                existing_o = dossier.setdefault("objects", [])
                for o in new_objs:
                    if o and o not in existing_o:
                        existing_o.append(o)

            # core_memories → memories
            new_mems = result.get("core_memories", [])
            if new_mems:
                existing_m = dossier.setdefault("memories", [])
                for mem in new_mems:
                    if isinstance(mem, dict) and mem.get("content"):
                        entry = {
                            "title": mem.get("title", "AI 搜索记忆"),
                            "content": mem["content"],
                            "source_turn_ids": [],
                            "tags": ["deep_search", "public_biography", "auto"],
                        }
                        existing_m.insert(0, entry)

            dossier["updated_at"] = st.now_iso()
            st.save_dossier(uid, mid, dossier)

            # 同步更新 meta.json（姓名/生卒）
            meta_patch: dict = {}
            current_meta = st.get_memorial(uid, mid) or {}
            if result.get("name") and not (current_meta.get("name") or "").strip():
                meta_patch["name"] = result["name"]
            if result.get("birth_date"):
                meta_patch["birth_date"] = result["birth_date"]
            if result.get("death_date"):
                meta_patch["death_date"] = result["death_date"]
            if result.get("occupation"):
                meta_patch["occupation"] = result["occupation"]
            if meta_patch:
                st.update_memorial_meta(uid, mid, meta_patch)

            dossier_updated = True
        except Exception as e:
            print(f"[deep-search] archive/dossier write failed: {e}")

    # 写入 session（如有）
    if req.session_id:
        s = session_store.get(req.session_id)
        if s is not None:
            s["ds_chat"].append({"role": "user", "content": req.query.strip()})
            s["ds_chat"].append({"role": "ai",   "content": result["organized"]})
            s["ds_result"] = {"organized": result["organized"], "fields": fields}

    return {
        "organized":       result["organized"],
        "model":           result["model"],
        "fallback":        result["fallback"],
        "fields":          fields,
        "archived_path":   archived_path,
        "dossier_updated": dossier_updated,
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
