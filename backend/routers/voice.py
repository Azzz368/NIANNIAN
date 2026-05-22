# backend/routers/voice.py — 声音工坊：样本管理 + 克隆 + 试听
import os, time, uuid, json, io
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from openai import OpenAI

from core import security, storage

router = APIRouter(prefix="/memorials", tags=["voice"])

# ─── 默认克隆配置 ────────────────────────────────────────────────
DEFAULT_VOICE = {
    "voice_id": "",           # 克隆完成后的 voice_id；空 = 尚未克隆
    "provider": "",           # dashscope / mock
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

@router.post("/{mid}/voice/clone")
def clone_voice(mid: str, req: CloneReq, user = Depends(security.get_current_user)):
    """触发声音克隆。优先调用 DashScope CosyVoice 自训；不可用时落回 mock。"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    audios = _list_audio_assets(user["user_id"], mid)
    valid_ids = {a["asset_id"] for a in audios}
    samples = [s for s in req.sample_ids if s in valid_ids]
    if not samples:
        raise HTTPException(400, "请至少选择一个已上传的音频样本")

    cfg = _get_voice_cfg(user["user_id"], mid)
    cfg["samples"] = samples
    cfg["status"] = "cloning"
    cfg["error"] = ""
    _save_voice_cfg(user["user_id"], mid, cfg)

    # 真实克隆（DashScope）—— 需要 dashscope SDK + 音频可公网访问
    # 若环境没有 dashscope SDK，则走 mock：生成一个本地 voice_id 标记
    voice_id = ""
    provider = ""
    err = ""
    try:
        import dashscope  # type: ignore
        from dashscope.audio.tts_v2 import VoiceEnrollmentService  # type: ignore
        api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")
        dashscope.api_key = api_key
        # 取第一个样本（CosyVoice clone 一次只用一个样本，10-30s 效果最佳）
        sample_asset = next(a for a in audios if a["asset_id"] == samples[0])
        sample_path = storage.memorial_dir(user["user_id"], mid) / "assets" / sample_asset.get("stored_name", "")
        if not sample_path.exists():
            raise RuntimeError("样本文件不存在")
        # DashScope 要求公网 URL；这里假设有 PUBLIC_BASE_URL 环境变量；否则报错回 mock
        public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        if not public_base:
            raise RuntimeError("PUBLIC_BASE_URL 未配置，无法将样本提交给 DashScope，已切换 mock")
        from .uploads import make_asset_sig
        sig = make_asset_sig(mid, sample_asset["asset_id"])
        sample_url = f"{public_base}/api/memorials/{mid}/assets/{sample_asset['asset_id']}/raw?sig={sig}"
        svc = VoiceEnrollmentService()
        prefix = f"nian{mid[:6]}"
        target_model = "cosyvoice-v1"
        voice_id = svc.create_voice(target_model=target_model, prefix=prefix, url=sample_url)
        provider = "dashscope"
    except ImportError:
        # mock 模式
        voice_id = f"mock_vc_{mid[:6]}_{int(time.time())}"
        provider = "mock"
    except Exception as e:
        err = str(e)
        # 失败也给 mock，让前端流程继续
        voice_id = f"mock_vc_{mid[:6]}_{int(time.time())}"
        provider = "mock"

    cfg["voice_id"] = voice_id
    cfg["provider"] = provider
    cfg["status"] = "ready" if provider == "dashscope" else "mock"
    cfg["last_clone_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    cfg["error"] = err
    cfg["history"] = (cfg.get("history") or [])[-9:] + [{
        "voice_id": voice_id,
        "created_at": cfg["last_clone_at"],
        "sample_count": len(samples),
        "note": req.note,
        "provider": provider,
    }]
    _save_voice_cfg(user["user_id"], mid, cfg)
    return {"ok": True, "voice": cfg}


class PreviewReq(BaseModel):
    text: str
    use_clone: bool = True    # True 用克隆音色；False 用预制音色

@router.post("/{mid}/voice/preview")
def preview(mid: str, req: PreviewReq, user = Depends(security.get_current_user)):
    """合成试听音频；返回 audio/mpeg 字节流"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "请输入试听文本")
    if len(text) > 300:
        text = text[:300]

    cfg = _get_voice_cfg(user["user_id"], mid)
    params = cfg["params"]
    voice = cfg["voice_id"] if (req.use_clone and cfg.get("voice_id") and cfg.get("provider") == "dashscope") else params.get("base_voice", "longxiaochun")

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "DASHSCOPE_API_KEY 未配置，无法合成")

    # 调用 DashScope CosyVoice
    try:
        import dashscope  # type: ignore
        from dashscope.audio.tts_v2 import SpeechSynthesizer  # type: ignore
        dashscope.api_key = api_key
        # 注意：新版 dashscope SDK 不再支持 __init__ 传 speech_rate/pitch_rate
        # 这些参数得在 call() 时通过 SSML 或者额外参数传；这里先用基础调用确保稳定
        synth = SpeechSynthesizer(model="cosyvoice-v1", voice=voice)
        result = synth.call(text)
        # 兼容多种返回：bytes / Result 对象 / dict
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
            # 把 result 打印出来便于排查
            print(f"[voice.preview] unexpected result type={type(result)}, value={str(result)[:200]}")
            raise RuntimeError(f"合成返回为空（type={type(result).__name__}）")
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
    """诊断声音克隆链路：把每个环节单独探一遍，告诉你卡在哪。"""
    if not storage.get_memorial(user["user_id"], mid):
        raise HTTPException(404, "纪念对象不存在")
    result = {"checks": [], "ready_for_clone": False}

    def add(name, ok, detail=""):
        result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    # 1) dashscope SDK
    try:
        import dashscope  # type: ignore
        from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer  # type: ignore
        add("dashscope SDK 已安装", True, getattr(dashscope, "__version__", "unknown"))
        sdk_ok = True
    except ImportError as e:
        add("dashscope SDK 已安装", False, f"未安装：{e}")
        sdk_ok = False

    # 2) DASHSCOPE_API_KEY
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    add("DASHSCOPE_API_KEY 已配置", bool(api_key), f"长度={len(api_key)}" if api_key else "未设置")

    # 3) PUBLIC_BASE_URL
    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    add("PUBLIC_BASE_URL 已配置", bool(public_base), public_base or "未设置")

    # 4) 有音频样本
    audios = _list_audio_assets(user["user_id"], mid)
    add("有可用音频样本", len(audios) > 0, f"共 {len(audios)} 个")

    # 5) 样本公网可拉（拿第一个试探）
    sample_url = ""
    fetch_ok = False
    fetch_detail = "跳过：缺前置条件"
    if audios and public_base:
        a0 = audios[0]
        try:
            from .uploads import make_asset_sig
            sig = make_asset_sig(mid, a0["asset_id"])
            sample_url = f"{public_base}/api/memorials/{mid}/assets/{a0['asset_id']}/raw?sig={sig}"
            import urllib.request
            req = urllib.request.Request(sample_url, method="HEAD")
            with urllib.request.urlopen(req, timeout=8) as resp:
                fetch_ok = (200 <= resp.status < 300)
                fetch_detail = f"HTTP {resp.status} · Content-Type={resp.headers.get('Content-Type','')} · Content-Length={resp.headers.get('Content-Length','')}"
        except Exception as e:
            fetch_detail = f"无法拉取：{type(e).__name__}: {e}"
    add(f"样本可被 DashScope 拉取（HEAD {sample_url[:80]}...）" if sample_url else "样本可被 DashScope 拉取", fetch_ok, fetch_detail)

    result["ready_for_clone"] = sdk_ok and bool(api_key) and bool(public_base) and len(audios) > 0 and fetch_ok
    result["sample_url_example"] = sample_url
    return result


