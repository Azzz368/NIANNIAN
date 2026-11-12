# backend/routers/voice.py — 声音工坊：样本管理 + 克隆 + 试听
import os, time, json, io, asyncio
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from core import security, storage
from services import qwen_voice

router = APIRouter(prefix="/memorials", tags=["voice"])

# ─── DashScope 区域配置 ──────────────────────────────────────────
# 默认走新加坡（国际）区，与 agent.py / agent_realtime.py 保持一致
# 想切到北京区：设 DASHSCOPE_REGION=cn
def _dashscope_region() -> str:
    return (os.getenv("DASHSCOPE_REGION", "intl") or "intl").lower()

def _http_base() -> str:
    return "https://dashscope-intl.aliyuncs.com/api/v1" if _dashscope_region() == "intl" else "https://dashscope.aliyuncs.com/api/v1"

def _ws_base() -> str:
    return "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference" if _dashscope_region() == "intl" else "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

def _apply_region_to_sdk():
    """设置 dashscope SDK 的全局 endpoint（影响 SpeechSynthesizer / VoiceEnrollmentService）"""
    try:
        import dashscope  # type: ignore
        dashscope.base_http_api_url = _http_base()
        dashscope.base_websocket_api_url = _ws_base()
    except Exception:
        pass

# ─── 默认克隆配置 ────────────────────────────────────────────────
DEFAULT_VOICE = {
    "voice_id": "",           # 克隆完成后的 voice_id；空 = 尚未克隆
    "provider": "",           # qwen_tts / legacy dashscope / mock
    "status": "idle",         # idle / cloning / ready / failed / mock
    "samples": [],            # 参与克隆的 asset_id 列表
    "params": {
        "speed": 1.0,         # 0.5 ~ 2.0
        "pitch": 0,           # -12 ~ +12 半音
        "volume": 1.0,        # 0 ~ 2
        "emotion": "neutral", # neutral / warm / serious / gentle
        "base_voice": "longxiaochun",  # 未克隆时用的预制音色
    },
    "preview_text": "今天天气真好，我们一起去散步吧。",
    "last_clone_at": "",
    "history": [],            # [{voice_id, created_at, sample_count, note}]
    "error": "",
}

def _voice_path(user_id: str, memorial_id: str) -> Path:
    return storage.memorial_dir(user_id, memorial_id) / "voice.json"

def _get_voice_cfg(user_id: str, memorial_id: str) -> dict:
    p = _voice_path(user_id, memorial_id)
    if not p.exists():
        return json.loads(json.dumps(DEFAULT_VOICE))  # deep copy
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        # 兜底字段
        base = json.loads(json.dumps(DEFAULT_VOICE))
        base.update(d)
        base["params"] = {**DEFAULT_VOICE["params"], **(d.get("params") or {})}
        return base
    except Exception:
        return json.loads(json.dumps(DEFAULT_VOICE))

def _save_voice_cfg(user_id: str, memorial_id: str, cfg: dict):
    p = _voice_path(user_id, memorial_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def _list_audio_assets(user_id: str, memorial_id: str) -> List[dict]:
    """从 assets.json 过滤出音频类素材"""
    try:
        assets = storage.list_assets(user_id, memorial_id)
    except Exception:
        assets = []
    return [a for a in (assets or []) if a.get("kind") == "audio"]


# ─── 路由 ────────────────────────────────────────────────────────
@router.get("/{mid}/voice")
def get_voice(mid: str, user = Depends(security.get_current_user)):
    """获取声音克隆配置 + 可用音频素材列表"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    cfg = _get_voice_cfg(user["user_id"], mid)
    audios = _list_audio_assets(user["user_id"], mid)
    return {
        "voice": cfg,
        "audio_assets": audios,
        "preset_voices": [
            {"id": "longxiaochun", "name": "龙小淳 · 温柔女声"},
            {"id": "longxiaocheng", "name": "龙小诚 · 沉稳男声"},
            {"id": "longwan", "name": "龙婉 · 柔和女声"},
            {"id": "longcheng", "name": "龙橙 · 阳光男声"},
            {"id": "longhua", "name": "龙华 · 童声"},
        ]
    }


class UpdateVoiceReq(BaseModel):
    params: Optional[dict] = None
    samples: Optional[List[str]] = None  # asset_id 列表
    preview_text: Optional[str] = None

@router.put("/{mid}/voice")
def update_voice(mid: str, req: UpdateVoiceReq, user = Depends(security.get_current_user)):
    """更新克隆参数 / 样本选择 / 试听文案（不触发克隆）"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    cfg = _get_voice_cfg(user["user_id"], mid)
    if req.params is not None:
        cfg["params"] = {**cfg["params"], **req.params}
    if req.samples is not None:
        cfg["samples"] = req.samples
    if req.preview_text is not None:
        cfg["preview_text"] = req.preview_text
    _save_voice_cfg(user["user_id"], mid, cfg)
    return {"ok": True, "voice": cfg}


class CloneReq(BaseModel):
    sample_ids: List[str]    # 必须从已上传的音频素材里选
    note: str = ""
    consent_confirmed: bool = False
    language: str = ""


def _reference_url(user_id: str, mid: str, asset: dict) -> str:
    cdn_url = asset.get("bunny_cdn_url", "")
    if cdn_url and asset.get("bunny_sync_status") == "succeeded":
        if urlparse(cdn_url).scheme == "https":
            return cdn_url
    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    parsed = urlparse(public_base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(400, "样本需可公网访问：请配置 HTTPS PUBLIC_BASE_URL 或先同步至 Bunny CDN")
    token = jwt.encode({
        "purpose": "voice-reference", "user_id": user_id, "mid": mid,
        "asset_id": asset["asset_id"], "exp": int(time.time()) + 900,
    }, security.JWT_SECRET, algorithm=security.JWT_ALG)
    return f"{public_base}/api/memorials/{mid}/voice/reference/{asset['asset_id']}?sig={token}"


@router.get("/{mid}/voice/reference/{aid}")
def voice_reference(mid: str, aid: str, sig: str):
    try:
        claims = jwt.decode(sig, security.JWT_SECRET, algorithms=[security.JWT_ALG],
                            options={"require": ["exp", "purpose", "user_id", "mid", "asset_id"]})
        if (claims["purpose"] != "voice-reference" or claims["mid"] != mid
                or claims["asset_id"] != aid):
            raise ValueError("Reference scope mismatch")
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(403, "样本签名无效或已过期")
    if not storage.get_memorial(claims["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    asset = next((item for item in _list_audio_assets(claims["user_id"], mid)
                  if item["asset_id"] == aid), None)
    if not asset:
        raise HTTPException(404, "声音样本不存在")
    path = storage.memorial_dir(claims["user_id"], mid) / "assets" / asset.get("stored_name", "")
    if not path.is_file():
        raise HTTPException(404, "声音样本不存在")
    return FileResponse(path, media_type=asset.get("mime") or "audio/mpeg",
                        headers={"Cache-Control": "private, no-store"})

@router.post("/{mid}/voice/clone")
def clone_voice(mid: str, req: CloneReq, user = Depends(security.get_current_user)):
    """注册 QwenCloud Plus 音色并等待就绪，不回退为其他音色。"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    if not req.consent_confirmed:
        raise HTTPException(400, "请先确认已获得声音所有者的克隆授权")
    if len(req.sample_ids) != 1:
        raise HTTPException(400, "请仅选择一个声音样本")
    if req.language and req.language not in qwen_voice.LANGUAGES:
        raise HTTPException(400, "不支持的声音语言")
    audios = _list_audio_assets(user["user_id"], mid)
    sample_asset = next((asset for asset in audios if asset["asset_id"] == req.sample_ids[0]), None)
    if not sample_asset:
        raise HTTPException(400, "请选择已上传的音频样本")
    sample_path = storage.memorial_dir(user["user_id"], mid) / "assets" / sample_asset.get("stored_name", "")
    if not sample_path.is_file():
        raise HTTPException(400, "声音样本文件不存在")
    if not 0 < sample_path.stat().st_size <= 10 * 1024 * 1024:
        raise HTTPException(400, "声音样本不能为空，且不能超过 10 MiB")
    mime = (sample_asset.get("mime") or "").split(";", 1)[0].strip().lower()
    if mime not in {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave", "audio/mpeg",
                    "audio/mp3", "audio/mp4", "audio/m4a", "audio/x-m4a"}:
        raise HTTPException(400, "克隆仅支持 WAV、MP3、M4A/MP4 音频；请先转换 WebM/Ogg/FLAC")
    reference_url = _reference_url(user["user_id"], mid, sample_asset)
    cfg = _get_voice_cfg(user["user_id"], mid)

    def persist():
        try:
            _save_voice_cfg(user["user_id"], mid, cfg)
        except OSError:
            raise HTTPException(500, "VOICE_PERSISTENCE_FAILED：本地保存失败，请保留音色 ID="
                                f"{cfg.get('voice_id', '')}，模型={cfg.get('target_model', '')}，勿重复克隆")

    try:
        qwen_voice.api_key()
        qwen_voice.http_base()
        voice_id, target_model = qwen_voice.create_voice(reference_url, req.language)
        cfg.update({
            "voice_id": voice_id, "provider": "qwen_tts", "target_model": target_model,
            "samples": req.sample_ids, "language": req.language, "status": "cloning", "error": "",
            "consent_confirmed_at": storage.now_iso(), "last_clone_at": storage.now_iso(),
            "provider_account": qwen_voice.account_scope(),
        })
        cfg["history"] = (cfg.get("history") or [])[-9:] + [{
            "voice_id": voice_id, "created_at": cfg["last_clone_at"], "sample_count": 1,
            "note": req.note, "provider": "qwen_tts", "target_model": target_model,
        }]
        persist()
        if target_model != qwen_voice.TARGET_MODEL:
            raise qwen_voice.VoiceError("注册返回的音色模型与 Plus 不一致，请检查 QwenCloud 配置")
        qwen_voice.wait_until_ready(voice_id)
    except qwen_voice.VoiceError as exc:
        cfg.update({"status": "failed", "error": str(exc)})
        persist()
        raise HTTPException(502, str(exc))
    cfg.update({"status": "ready", "error": ""})
    persist()
    return {"ok": True, "voice": cfg}


class PreviewReq(BaseModel):
    text: str
    use_clone: bool = True    # True 用克隆音色；False 用预制音色
    instruction: str = ""
    language: str = ""

@router.post("/{mid}/voice/preview")
def preview(mid: str, req: PreviewReq, user = Depends(security.get_current_user)):
    """合成试听音频；返回 audio/mpeg 字节流"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    text = (req.text or "").strip()
    try:
        text = qwen_voice.validate_text(text, req.instruction, req.language)
    except qwen_voice.VoiceError as exc:
        raise HTTPException(400, str(exc))

    cfg = _get_voice_cfg(user["user_id"], mid)
    params = cfg["params"]
    if req.use_clone:
        if not cfg.get("voice_id") or cfg.get("provider") != "qwen_tts":
            raise HTTPException(409, "尚无可用的 QwenCloud 克隆音色，请先克隆，不会自动改用预制音色")
        if cfg.get("target_model") != qwen_voice.TARGET_MODEL:
            raise HTTPException(409, "旧音色与 QwenCloud Plus 模型不兼容，请使用同一账户重新克隆")
        try:
            if cfg.get("provider_account") and cfg["provider_account"] != qwen_voice.account_scope():
                raise HTTPException(409, "QwenCloud 账户或端点已更改，请切回原配置或重新克隆")
            if cfg.get("status") != "ready":
                qwen_voice.wait_until_ready(cfg["voice_id"])
                cfg.update({"status": "ready", "error": ""})
                _save_voice_cfg(user["user_id"], mid, cfg)
            instruction = req.instruction or {
                "warm": "Speak warmly and naturally.", "serious": "Speak in a serious, steady tone.",
                "gentle": "Speak gently and softly.",
            }.get(params.get("emotion"), "")
            audio_bytes = asyncio.run(qwen_voice.synthesize(
                text, cfg["voice_id"], cfg["target_model"], instruction=instruction,
                language=req.language or cfg.get("language", ""),
            ))
            return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
        except qwen_voice.VoiceError as exc:
            raise HTTPException(502, str(exc))
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "DASHSCOPE_API_KEY 未配置，无法合成")

    try:
        import dashscope  # type: ignore
        from dashscope.audio.tts_v2 import SpeechSynthesizer  # type: ignore
        _apply_region_to_sdk()
        dashscope.api_key = api_key
        synth = SpeechSynthesizer(model="cosyvoice-v1", voice=params.get("base_voice", "longxiaochun"))
        result = synth.call(text)
        audio_bytes = None
        if isinstance(result, (bytes, bytearray)):
            audio_bytes = bytes(result)
        elif hasattr(result, "get_audio_data"):
            audio_bytes = result.get_audio_data()
        elif hasattr(result, "output"):
            out = getattr(result, "output")
            if isinstance(out, (bytes, bytearray)):
                audio_bytes = bytes(out)
            elif isinstance(out, dict) and "audio" in out:
                audio_bytes = out["audio"]
        if not audio_bytes:
            print(f"[voice.preview] cosy result type={type(result)}, value={str(result)[:200]}")
            raise RuntimeError(f"CosyVoice 返回为空（type={type(result).__name__}）")
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
    except ImportError:
        raise HTTPException(500, "服务端未安装 dashscope SDK：pip install dashscope")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("[voice.preview] failed:", traceback.format_exc())
        raise HTTPException(500, f"合成失败：{e}")


@router.delete("/{mid}/voice")
def reset_voice(mid: str, user = Depends(security.get_current_user)):
    """重置：清空当前克隆，回到 idle"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    cfg = _get_voice_cfg(user["user_id"], mid)
    history = cfg.get("history", [])
    cfg = json.loads(json.dumps(DEFAULT_VOICE))
    cfg["history"] = history  # 保留历史
    _save_voice_cfg(user["user_id"], mid, cfg)
    return {"ok": True, "voice": cfg}


@router.get("/{mid}/voice/diagnose")
def diagnose_voice(mid: str, user = Depends(security.get_current_user)):
    """检查本地配置与样本访问，不创建音色或发起付费合成。"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    result = {"checks": [], "ready_for_clone": False}

    def add(name, ok, detail=""):
        result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        qwen_voice.api_key()
        add("QwenCloud API Key 已配置", True, "QWEN_API_KEY 或 DASHSCOPE_API_KEY；需与音色同账户")
    except qwen_voice.VoiceError as exc:
        add("QwenCloud API Key 已配置", False, str(exc))
    try:
        add("QwenCloud HTTP / WebSocket 端点", True,
            f"{qwen_voice.http_base()} / {qwen_voice.websocket_url()}")
    except qwen_voice.VoiceError as exc:
        add("QwenCloud HTTP / WebSocket 端点", False, str(exc))
    try:
        from websockets.legacy.client import connect
        add("WebSocket 依赖已安装", bool(connect))
    except ImportError:
        add("WebSocket 依赖已安装", False, "请安装 backend/requirements.txt")
    audios = _list_audio_assets(user["user_id"], mid)
    add("有可用音频样本", len(audios) > 0, f"共 {len(audios)} 个")
    if audios:
        try:
            import requests
            sample_url = _reference_url(user["user_id"], mid, audios[0])
            with requests.get(sample_url, headers={"Range": "bytes=0-0"}, stream=True, timeout=8) as response:
                add("样本 HTTPS 可访问", response.status_code in (200, 206), f"HTTP {response.status_code}")
        except HTTPException as exc:
            add("样本 HTTPS 可访问", False, str(exc.detail))
        except Exception:
            add("样本 HTTPS 可访问", False, "无法拉取样本，请检查 CDN 或公网 HTTPS 域名")
    result["ready_for_clone"] = all(check["ok"] for check in result["checks"])
    return result


