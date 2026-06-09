# backend/core/security.py — JWT + 密码 + 访问码
import os, time, hmac, hashlib, json, base64, uuid
import bcrypt
import jwt
from fastapi import Header, HTTPException, Depends

JWT_SECRET = os.getenv("JWT_SECRET", "nian-dev-secret-change-me-in-prod")
JWT_ALG = "HS256"
JWT_TTL = 60 * 60 * 24 * 30   # 30 天
OWNER_ACCESS_CODE = os.getenv("OWNER_ACCESS_CODE", "NIAN-2026-OWNER")
OWNER_USER_ID = "owner"


def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pwd: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pwd.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def make_token(user_id: str, email: str = "", is_owner: bool = False) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "owner": is_owner,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_token(tok: str) -> dict:
    try:
        return jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"无效令牌: {e}")


async def get_current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI 依赖：解析 Bearer token，返回 { user_id, email, is_owner }"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少登录令牌")
    tok = authorization.split(" ", 1)[1].strip()
    payload = decode_token(tok)
    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email", ""),
        "is_owner": bool(payload.get("owner", False)),
    }

async def get_current_user_optional(authorization: str = Header(default="")) -> dict | None:
    """可选登录：未登录返回 None，登录返回 user 对象。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        tok = authorization.split(" ", 1)[1].strip()
        payload = decode_token(tok)
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email", ""),
            "is_owner": bool(payload.get("owner", False)),
        }
    except Exception:
        return None


def check_owner_code(code: str) -> bool:
    return hmac.compare_digest((code or "").strip(), OWNER_ACCESS_CODE)

def new_user_id() -> str:
    return uuid.uuid4().hex[:16]
