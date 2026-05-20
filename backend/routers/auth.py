# backend/routers/auth.py — 注册 / 登录 / 访问码登录 / 当前用户
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from core import security, storage

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""

class LoginReq(BaseModel):
    email: EmailStr
    password: str

class CodeLoginReq(BaseModel):
    code: str


@router.post("/register")
def register(req: RegisterReq):
    if storage.find_user_by_email(req.email):
        raise HTTPException(400, "邮箱已注册")
    if len(req.password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    uid = security.new_user_id()
    u = storage.create_user(
        user_id=uid,
        email=req.email,
        password_hash=security.hash_password(req.password),
        display_name=req.display_name or req.email.split("@")[0],
    )
    tok = security.make_token(uid, req.email, False)
    return {"token": tok, "user": _public(u)}


@router.post("/login")
def login(req: LoginReq):
    u = storage.find_user_by_email(req.email)
    if not u or not security.verify_password(req.password, u.get("password_hash", "")):
        raise HTTPException(401, "邮箱或密码错误")
    tok = security.make_token(u["user_id"], u["email"], bool(u.get("is_owner")))
    return {"token": tok, "user": _public(u)}


@router.post("/code")
def code_login(req: CodeLoginReq):
    """访问码登录：输入主人码即可作为 owner 登录，数据写到 data/users/owner/"""
    if not security.check_owner_code(req.code):
        raise HTTPException(401, "访问码错误")
    u = storage.ensure_owner_user()
    tok = security.make_token("owner", u.get("email", "owner@local"), True)
    return {"token": tok, "user": _public(u)}


@router.get("/me")
def me(user = Depends(security.get_current_user)):
    u = storage.find_user_by_id(user["user_id"])
    if not u:
        raise HTTPException(404, "用户不存在")
    return {"user": _public(u)}


def _public(u: dict) -> dict:
    return {
        "user_id": u.get("user_id"),
        "email": u.get("email"),
        "display_name": u.get("display_name"),
        "is_owner": bool(u.get("is_owner")),
        "created_at": u.get("created_at"),
    }
