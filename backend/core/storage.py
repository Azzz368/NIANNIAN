# backend/core/storage.py — 文件型用户/档案/资料库存储
"""
目录结构：
data/
  users.json                              # 全部用户索引
  users/
    {user_id}/
      profile.json                        # 用户基础信息
      memorials/
        {memorial_id}/
          meta.json                       # 被纪念人物基础信息（姓名/关系/生卒）
          dossier.json                    # 累积资料库（性格/记忆/金句/关系...）
          conversations.jsonl             # 对话历史（逐行 JSON）
          assets/
            {asset_id}.{ext}              # 原始文件
          assets.json                     # 文件元数据 + 标签
"""
import os, json, uuid, time, threading
from pathlib import Path
from typing import List, Dict, Optional, Any
from . import oss_sync

_LOCK = threading.RLock()

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = ROOT_DIR / "data"
USERS_INDEX = DATA_DIR / "users.json"

def _ensure():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "users").mkdir(parents=True, exist_ok=True)
    if not USERS_INDEX.exists():
        USERS_INDEX.write_text(json.dumps({"users": []}, ensure_ascii=False, indent=2), encoding="utf-8")

def _read_json(p: Path, default: Any) -> Any:
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(p: Path, data: Any):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(p: Path, content: str):
    """保存文本文件并同步推送到 OSS。"""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    oss_sync.push_path(p)

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")

def new_id(prefix: str = "") -> str:
    return (prefix + uuid.uuid4().hex[:12])

# ─── 用户索引 ─────────────────────────────────────────────────────
def list_users() -> list[dict]:
    _ensure()
    with _LOCK:
        return _read_json(USERS_INDEX, {"users": []}).get("users", [])

def find_user_by_email(email: str) -> dict | None:
    email = (email or "").lower().strip()
    for u in list_users():
        if u.get("email", "").lower() == email:
            return u
    return None

def find_user_by_id(user_id: str) -> dict | None:
    for u in list_users():
        if u.get("user_id") == user_id:
            return u
    return None

def create_user(user_id: str, email: str, password_hash: str, display_name: str = "", is_owner: bool = False) -> dict:
    _ensure()
    with _LOCK:
        idx = _read_json(USERS_INDEX, {"users": []})
        user = {
            "user_id": user_id,
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "display_name": display_name or email.split("@")[0] if email else "owner",
            "is_owner": is_owner,
            "created_at": now_iso(),
        }
        idx["users"].append(user)
        _write_json(USERS_INDEX, idx)
        # 用户主目录
        user_dir(user_id).mkdir(parents=True, exist_ok=True)
        (user_dir(user_id) / "memorials").mkdir(parents=True, exist_ok=True)
        _write_json(user_dir(user_id) / "profile.json", {
            "user_id": user_id, "email": email, "display_name": user["display_name"],
            "is_owner": is_owner, "created_at": user["created_at"],
        })
        return user

def ensure_owner_user() -> dict:
    """确保 owner 用户存在，访问码登录用。"""
    u = find_user_by_id("owner")
    if u:
        return u
    return create_user(user_id="owner", email="owner@local", password_hash="", display_name="主人", is_owner=True)

# ─── 路径 helpers ─────────────────────────────────────────────────
def user_dir(user_id: str) -> Path:
    return DATA_DIR / "users" / user_id

def memorial_dir(user_id: str, memorial_id: str) -> Path:
    return user_dir(user_id) / "memorials" / memorial_id


def _normalize_year(value: str = "") -> str:
    import re
    text = (value or "").strip()
    m = re.search(r"(\d{4})", text)
    return m.group(1) if m else ""


def normalize_person_key(name: str = "", birth: str = "", passing: str = "") -> tuple[str, str, str]:
    return (
        (name or "").strip().lower(),
        (birth or "").strip(),
        (passing or "").strip(),
    )


def find_memorial_by_identity(user_id: str, name: str = "", birth: str = "", passing: str = "") -> dict | None:
    target = normalize_person_key(name, birth, passing)
    for mem in list_memorials(user_id):
        meta = get_memorial(user_id, mem.get("memorial_id", "")) or {}
        meta_name = meta.get("name") or meta.get("subject", {}).get("name", "")
        dossier = get_dossier(user_id, mem.get("memorial_id", ""))
        subj = dossier.get("subject", {}) if isinstance(dossier, dict) else {}
        meta_birth = meta.get("birth_date") or subj.get("birth", "")
        meta_passing = meta.get("death_date") or subj.get("passing", "")
        if normalize_person_key(meta_name, meta_birth, meta_passing) == target:
            return meta
    return None


def ensure_memorial_assets(user_id: str, memorial_id: str) -> None:
    md = memorial_dir(user_id, memorial_id)
    md.mkdir(parents=True, exist_ok=True)
    (md / "assets").mkdir(parents=True, exist_ok=True)
    if not (md / "meta.json").exists():
        _write_json(md / "meta.json", {
            "memorial_id": memorial_id,
            "user_id": user_id,
            "name": "未命名",
            "relation": "",
            "note": "",
            "birth_date": "",
            "death_date": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "product_intent": "",
        })
    if not (md / "dossier.json").exists():
        _write_json(md / "dossier.json", default_dossier())
    if not (md / "assets.json").exists():
        _write_json(md / "assets.json", {"assets": []})
    conv = md / "conversations.jsonl"
    if not conv.exists():
        conv.touch()


def add_dossier_memory(user_id: str, memorial_id: str, title: str, content: str, tags: Optional[list] = None) -> dict:
    dossier = get_dossier(user_id, memorial_id)
    if not isinstance(dossier, dict):
        dossier = default_dossier()
    memories = dossier.setdefault("memories", [])
    entry = {
        "title": title or "回忆",
        "content": content or "",
        "source_turn_ids": [],
        "tags": tags or ["biography"],
    }
    memories.insert(0, entry)
    save_dossier(user_id, memorial_id, dossier)
    return entry


def ensure_memorial_for_person(user_id: str, name: str, birth: str = "", passing: str = "", relation: str = "", note: str = "") -> dict:
    existing = find_memorial_by_identity(user_id, name, birth, passing)
    if existing and existing.get("memorial_id"):
        mid = existing["memorial_id"]
        ensure_memorial_assets(user_id, mid)
        update_memorial_meta(user_id, mid, {
            "name": name or existing.get("name") or "未命名",
            "birth_date": birth or existing.get("birth_date", ""),
            "death_date": passing or existing.get("death_date", ""),
            "relation": relation or existing.get("relation", ""),
            "note": note or existing.get("note", ""),
        })
        return get_memorial(user_id, mid) or existing

    created = create_memorial(user_id, name or "未命名", relation=relation, note=note, birth_date=birth, death_date=passing)
    mid = created.get("memorial_id")
    if mid:
        ensure_memorial_assets(user_id, mid)
        update_memorial_meta(user_id, mid, {
            "name": name or "未命名",
            "birth_date": birth or "",
            "death_date": passing or "",
            "relation": relation or "",
            "note": note or "",
        })
    return get_memorial(user_id, mid) or created

# ─── Memorial（纪念对象 / 数字人对象） ────────────────────────────
def list_memorials(user_id: str) -> list[dict]:
    base = user_dir(user_id) / "memorials"
    if not base.exists():
        return []
    out = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        meta = _read_json(d / "meta.json", None)
        if meta:
            out.append(meta)
    out.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
    return out

def get_memorial(user_id: str, memorial_id: str) -> dict | None:
    return _read_json(memorial_dir(user_id, memorial_id) / "meta.json", None)

def create_memorial(user_id: str, name: str, relation: str = "", note: str = "", birth_date: str = "", death_date: str = "", occupation: str = "") -> dict:
    mid = new_id("m_")
    meta = {
        "memorial_id": mid,
        "user_id": user_id,
        "name": name or "未命名",
        "relation": relation or "",
        "note": note or "",
        "birth_date": birth_date or "",
        "death_date": death_date or "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "product_intent": "",     # 用户产品倾向：video / biography / digital_human / unsure
    }
    with _LOCK:
        md = memorial_dir(user_id, mid)
        md.mkdir(parents=True, exist_ok=True)
        (md / "assets").mkdir(parents=True, exist_ok=True)
        _write_json(md / "meta.json", meta)
        _write_json(md / "dossier.json", default_dossier(name, relation, birth_date, death_date))
        (md / "conversations.jsonl").touch()
        _write_json(md / "assets.json", {"assets": []})
    return meta

def update_memorial_meta(user_id: str, memorial_id: str, patch: dict) -> dict | None:
    with _LOCK:
        meta = get_memorial(user_id, memorial_id)
        if not meta:
            return None
        meta.update({k: v for k, v in patch.items() if k not in ("memorial_id", "user_id", "created_at")})
        meta["updated_at"] = now_iso()
        if patch.get("birth_date"):
            meta["birth_date"] = patch.get("birth_date")
        if patch.get("death_date"):
            meta["death_date"] = patch.get("death_date")
        _write_json(memorial_dir(user_id, memorial_id) / "meta.json", meta)
        dossier = get_dossier(user_id, memorial_id)
        if isinstance(dossier, dict):
            subject = dossier.setdefault("subject", {})
            if patch.get("name"):
                subject["name"] = patch.get("name")
            if patch.get("birth_date"):
                subject["birth"] = patch.get("birth_date")
            if patch.get("death_date"):
                subject["passing"] = patch.get("death_date")
            if patch.get("relation"):
                subject["relation"] = patch.get("relation")
            save_dossier(user_id, memorial_id, dossier)
        return meta

def delete_memorial(user_id: str, memorial_id: str) -> bool:
    import shutil
    md = memorial_dir(user_id, memorial_id)
    if not md.exists():
        return False
    with _LOCK:
        shutil.rmtree(md, ignore_errors=True)
    return True

# ─── Dossier（资料库） ────────────────────────────────────────────
def default_dossier(name: str = "", relation: str = "", birth: str = "", passing: str = "") -> dict:
    return {
        "subject": {"name": name, "relation": relation, "birth": birth, "passing": passing, "occupation": "", "locations": [], "occupation_raw": ""},
        "personality": {"keywords": [], "habits": [], "catchphrases": []},
        "relationships": [],          # [{name, relation, note}]
        "memories": [],               # [{title, content, source_turn_ids, tags}]
        "quotes": [],                 # 金句
        "objects": [],                # 代表性物件
        "voice_traits": {"timbre": "", "pace": "", "accent": "", "samples": []},
        "visual_traits": {"appearance": "", "style": ""},
        "permissions": {              # 用户授权
            "public_search": None,
            "voice_clone": None,
            "digital_human": None,
            "image_generation": None,
        },
        "open_questions": [],         # 待确认问题
        "product_intent": {
            "primary": "",            # video / biography / digital_human
            "confidence": 0.0,
            "evidence": [],
        },
        "updated_at": now_iso(),
    }

def get_dossier(user_id: str, memorial_id: str) -> dict:
    p = memorial_dir(user_id, memorial_id) / "dossier.json"
    return _read_json(p, default_dossier())

def save_dossier(user_id: str, memorial_id: str, dossier: dict) -> dict:
    with _LOCK:
        dossier["updated_at"] = now_iso()
        _write_json(memorial_dir(user_id, memorial_id) / "dossier.json", dossier)
        # 同步刷新 memorial meta 的 updated_at
        meta_p = memorial_dir(user_id, memorial_id) / "meta.json"
        meta = _read_json(meta_p, None)
        if meta:
            meta["updated_at"] = dossier["updated_at"]
            if dossier.get("product_intent", {}).get("primary"):
                meta["product_intent"] = dossier["product_intent"]["primary"]
            _write_json(meta_p, meta)
    return dossier

def merge_dossier(user_id: str, memorial_id: str, patch: dict) -> dict:
    """智能合并：list 字段追加去重，dict 字段递归合并，标量字段非空覆盖。"""
    cur = get_dossier(user_id, memorial_id)
    def _merge(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            for k, v in b.items():
                if k in a:
                    a[k] = _merge(a[k], v)
                else:
                    a[k] = v
            return a
        if isinstance(a, list) and isinstance(b, list):
            # 简单去重（按 json 序列化）
            seen = {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in a}
            for it in b:
                k = json.dumps(it, ensure_ascii=False, sort_keys=True)
                if k not in seen:
                    a.append(it); seen.add(k)
            return a
        # 标量：b 非空则覆盖
        if b not in (None, "", 0, 0.0):
            return b
        return a
    merged = _merge(cur, patch)
    return save_dossier(user_id, memorial_id, merged)

# ─── 对话历史 ─────────────────────────────────────────────────────
def append_conversation(user_id: str, memorial_id: str, turns: list[dict]):
    """追加多轮对话到 jsonl。每行：{ts, role, content, ...}"""
    if not turns:
        return
    p = memorial_dir(user_id, memorial_id) / "conversations.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with open(p, "a", encoding="utf-8") as f:
            for t in turns:
                rec = dict(t)
                rec.setdefault("ts", now_iso())
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def read_conversations(user_id: str, memorial_id: str, limit: int = 200) -> list[dict]:
    p = memorial_dir(user_id, memorial_id) / "conversations.jsonl"
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    for ln in lines[-limit:]:
        ln = ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

# ─── Assets（上传的文件） ─────────────────────────────────────────
def list_assets(user_id: str, memorial_id: str) -> list[dict]:
    return _read_json(memorial_dir(user_id, memorial_id) / "assets.json", {"assets": []}).get("assets", [])

def add_asset(user_id: str, memorial_id: str, asset: dict) -> dict:
    with _LOCK:
        p = memorial_dir(user_id, memorial_id) / "assets.json"
        data = _read_json(p, {"assets": []})
        data["assets"].append(asset)
        _write_json(p, data)
    return asset

def update_asset(user_id: str, memorial_id: str, asset_id: str, patch: dict) -> dict | None:
    with _LOCK:
        p = memorial_dir(user_id, memorial_id) / "assets.json"
        data = _read_json(p, {"assets": []})
        for a in data["assets"]:
            if a.get("asset_id") == asset_id:
                a.update(patch)
                _write_json(p, data)
                return a
    return None


def delete_asset(user_id: str, memorial_id: str, asset_id: str) -> dict | None:
    with _LOCK:
        p = memorial_dir(user_id, memorial_id) / "assets.json"
        data = _read_json(p, {"assets": []})
        for idx, a in enumerate(data["assets"]):
            if a.get("asset_id") == asset_id:
                asset = data["assets"].pop(idx)
                _write_json(p, data)
                stored_name = asset.get("stored_name")
                if stored_name:
                    path = memorial_dir(user_id, memorial_id) / "assets" / stored_name
                    if path.exists():
                        try:
                            path.unlink()
                        except Exception:
                            pass
                return asset
    return None
