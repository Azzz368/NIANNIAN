import base64
import html
import io
import json
import mimetypes
import os
import re
import sys
import threading
import time
import wave
import uuid
from array import array
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field
from openai import OpenAI

from llm_client import call_skill
from skill_loader import load_skill
from services import service_manager as sm

router = APIRouter(prefix="/diary", tags=["diary"])

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT_DIR / "skills"
DIARY_OUTPUT_DIR = ROOT_DIR / "backend" / "outputs" / "diary"
DIARY_ASSET_DIR = DIARY_OUTPUT_DIR / "assets"
DIARY_PDF_DIR = DIARY_OUTPUT_DIR / "pdf"

for _dir in (DIARY_OUTPUT_DIR, DIARY_ASSET_DIR, DIARY_PDF_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _env_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _diary_asr_provider() -> str:
    provider = os.getenv("DIARY_ASR_PROVIDER", "auto").strip().lower()
    return provider if provider in {"auto", "dashscope", "dashscope_realtime", "302", "ai302", "llm"} else "auto"


def _diary_302_asr_model() -> str:
    return (
        os.getenv("DIARY_302_ASR_MODEL", "").strip()
        or os.getenv("DIARY_ASR_MODEL", "").strip()
        or os.getenv("AI302_AUDIO_MODEL", "").strip()
        or "whisper-1"
    )


def _diary_llm_audio_model() -> str:
    return (
        os.getenv("DIARY_LLM_AUDIO_MODEL", "").strip()
        or os.getenv("DIARY_ASR_MODEL", "").strip()
        or os.getenv("AI302_TEXT_MODEL", "").strip()
        or "gemini-2.5-flash"
    )


def _diary_dashscope_realtime_model() -> str:
    return (
        os.getenv("DIARY_DASHSCOPE_REALTIME_MODEL", "").strip()
        or os.getenv("DIARY_ASR_MODEL", "").strip()
        or "qwen3.5-omni-plus-realtime"
    )


def _resample_int16(samples: List[int], src_rate: int, dst_rate: int = 16000) -> List[int]:
    if src_rate == dst_rate or not samples:
        return samples
    out_len = max(1, int(len(samples) * dst_rate / src_rate))
    return [samples[min(len(samples) - 1, int(i * src_rate / dst_rate))] for i in range(out_len)]


def _audio_to_pcm16_mono_16k(raw: bytes, filename: str, content_type: str) -> bytes:
    ext = Path(filename or "").suffix.lower()
    if ext == ".pcm" or "pcm" in (content_type or "").lower():
        return raw
    if ext != ".wav" and "wav" not in (content_type or "").lower():
        raise ValueError("DashScope realtime 需要 WAV/PCM 音频；请让前端上传 16kHz 单声道 WAV，或先安装音频转码能力。")

    with wave.open(io.BytesIO(raw), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sample_width == 2:
        values = array("h")
        values.frombytes(frames)
        if sys.byteorder != "little":
            values.byteswap()
        raw_samples = list(values)
    elif sample_width == 1:
        raw_samples = [(value - 128) << 8 for value in frames]
    else:
        raise ValueError(f"暂不支持 {sample_width * 8}bit WAV，请上传 16bit PCM WAV")

    if channels > 1:
        mono_samples = []
        for i in range(0, len(raw_samples), channels):
            chunk = raw_samples[i:i + channels]
            mono_samples.append(int(sum(chunk) / len(chunk)))
    else:
        mono_samples = raw_samples

    resampled = _resample_int16(mono_samples, sample_rate, 16000)
    output = array("h", [max(-32768, min(32767, int(sample))) for sample in resampled])
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


class _DiaryRealtimeCallback:
    def __init__(self):
        from dashscope.audio.qwen_omni import OmniRealtimeCallback

        class Callback(OmniRealtimeCallback):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer

            def on_event(self, response):
                self.outer.on_event(response)

        self.transcripts: List[str] = []
        self.errors: List[str] = []
        self.events: List[str] = []
        self.done = threading.Event()
        self.instance = Callback(self)

    def on_event(self, response: Dict[str, Any]) -> None:
        event_type = response.get("type", "")
        if event_type:
            self.events.append(event_type)
        if event_type == "conversation.item.input_audio_transcription.completed":
            text = (response.get("transcript") or "").strip()
            if text:
                self.transcripts.append(text)
            self.done.set()
        elif event_type in {"conversation.item.input_audio_transcription.failed", "error"}:
            self.errors.append(json.dumps(response, ensure_ascii=False))
            self.done.set()
        elif event_type in {"response.text.done", "response.audio_transcript.done"}:
            text = (response.get("text") or response.get("transcript") or "").strip()
            if text:
                self.transcripts.append(text)
            self.done.set()
        elif event_type == "response.done":
            response_obj = response.get("response") or {}
            for item in response_obj.get("output", []) or []:
                for content in item.get("content", []) or []:
                    text = (content.get("text") or content.get("transcript") or "").strip()
                    if text:
                        self.transcripts.append(text)
            self.done.set()


def _audio_format(filename: str, content_type: str) -> str:
    ext = Path(filename or "").suffix.lower().lstrip(".")
    if ext in {"mp3", "wav", "m4a", "aac", "ogg", "webm", "flac"}:
        return ext
    if "wav" in content_type:
        return "wav"
    if "mpeg" in content_type or "mp3" in content_type:
        return "mp3"
    if "mp4" in content_type or "m4a" in content_type:
        return "m4a"
    if "aac" in content_type:
        return "aac"
    if "ogg" in content_type:
        return "ogg"
    if "webm" in content_type:
        return "webm"
    return "mp3"


def _transcribe_with_audio_llm(raw: bytes, filename: str, content_type: str, errors: List[str]) -> str:
    api_key = os.getenv("AI302_API_KEY", "").strip()
    if not api_key:
        errors.append("llm-audio: AI302_API_KEY is not configured")
        return ""

    model = _diary_llm_audio_model()
    base_url = os.getenv("AI302_BASE_URL", "https://api.302.ai/v1").strip().rstrip("/")
    audio_data = base64.b64encode(raw).decode("ascii")
    audio_format = _audio_format(filename, content_type)
    target_lang = os.getenv("DIARY_LLM_AUDIO_TARGET_LANG", "中文").strip() or "中文"
    task = os.getenv("DIARY_LLM_AUDIO_TASK", "transcribe").strip().lower()
    if task == "translate":
        instruction = f"请听这段音频，并翻译成{target_lang}。只输出翻译后的文字，不要解释，不要总结。"
    else:
        instruction = f"请听这段音频，并转写为{target_lang}原文。只输出转写文字，不要解释，不要总结，不要润色。"

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个严谨的音频转写助手，只返回音频中的文字内容。"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {"type": "input_audio", "input_audio": {"data": audio_data, "format": audio_format}},
                    ],
                },
            ],
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            errors.append(f"llm-audio/{model}: empty transcript")
        return text
    except Exception as exc:
        errors.append(f"llm-audio/{model}: {exc}")
        return ""


def _transcribe_with_302(raw: bytes, filename: str, content_type: str, errors: List[str]) -> str:
    api_key = os.getenv("AI302_API_KEY", "").strip()
    if not api_key:
        errors.append("302ai: AI302_API_KEY is not configured")
        return ""

    model = _diary_302_asr_model()
    base_url = os.getenv("AI302_BASE_URL", "https://api.302.ai/v1").strip().rstrip("/")
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        transcript = client.audio.transcriptions.create(
            model=model,
            file=(filename, io.BytesIO(raw), content_type),
            language="zh",
        )
        text = (getattr(transcript, "text", "") or "").strip()
        if not text:
            errors.append(f"302ai/{model}: empty transcript")
        return text
    except Exception as exc:
        errors.append(f"302ai/{model}: {exc}")
        return ""


def _transcribe_with_dashscope(raw: bytes, filename: str, content_type: str, errors: List[str]) -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        errors.append("dashscope: DASHSCOPE_API_KEY is not configured")
        return ""

    client = OpenAI(api_key=api_key, base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    for model in _env_list("DIARY_DASHSCOPE_ASR_MODELS", "paraformer-realtime-v2"):
        try:
            transcript = client.audio.transcriptions.create(
                model=model,
                file=(filename, io.BytesIO(raw), content_type),
                language="zh",
            )
            text = (getattr(transcript, "text", "") or "").strip()
            if text:
                return text
            errors.append(f"dashscope/{model}: empty transcript")
        except Exception as exc:
            errors.append(f"dashscope/{model}: {exc}")
    return ""


def _transcribe_with_dashscope_realtime(raw: bytes, filename: str, content_type: str, errors: List[str]) -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        errors.append("dashscope-realtime: DASHSCOPE_API_KEY is not configured")
        return ""

    try:
        from dashscope.audio.qwen_omni import AudioFormat, MultiModality, OmniRealtimeConversation
    except Exception as exc:
        errors.append(f"dashscope-realtime: dashscope sdk is unavailable: {exc}")
        return ""

    try:
        pcm_bytes = _audio_to_pcm16_mono_16k(raw, filename, content_type)
    except Exception as exc:
        errors.append(f"dashscope-realtime: {exc}")
        return ""

    model = _diary_dashscope_realtime_model()
    url = os.getenv("DASHSCOPE_REALTIME_URL", "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime").strip()
    timeout_sec = float(os.getenv("DIARY_DASHSCOPE_REALTIME_TIMEOUT", "25"))
    callback = _DiaryRealtimeCallback()
    conv = OmniRealtimeConversation(model=model, callback=callback.instance, url=url, api_key=api_key)

    try:
        conv.connect()
        conv.update_session(
            output_modalities=[MultiModality.TEXT],
            voice=os.getenv("DIARY_DASHSCOPE_REALTIME_VOICE", "Ethan"),
            input_audio_format=AudioFormat.PCM_16000HZ_MONO_16BIT,
            enable_input_audio_transcription=True,
            enable_turn_detection=False,
            instructions="请只转写用户音频中的原文，不要回答问题，不要解释，不要润色。",
        )
        chunk_size = 3200
        for start in range(0, len(pcm_bytes), chunk_size):
            conv.append_audio(base64.b64encode(pcm_bytes[start:start + chunk_size]).decode("ascii"))
            time.sleep(0.01)
        conv.commit()
        if not callback.done.wait(timeout_sec):
            conv.create_response(instructions="请输出这段用户音频的原文转写。", output_modalities=[MultiModality.TEXT])
            callback.done.wait(timeout_sec)
    except Exception as exc:
        errors.append(f"dashscope-realtime/{model}: {exc}")
        return ""
    finally:
        try:
            conv.close()
        except Exception:
            pass

    text = "\n".join(item.strip() for item in callback.transcripts if item.strip()).strip()
    if text:
        return text
    if callback.errors:
        errors.extend(f"dashscope-realtime/{model}: {item}" for item in callback.errors[-2:])
    else:
        seen = ", ".join(callback.events[-8:]) if callback.events else "no events"
        errors.append(f"dashscope-realtime/{model}: empty transcript; events={seen}; pcm_bytes={len(pcm_bytes)}")
    return ""


class DiaryJsonImage(BaseModel):
    filename: str = "image.jpg"
    mime: str = "image/jpeg"
    data_base64: str = Field(..., description="base64 string, optional data:image prefix")


class DiaryJsonRequest(BaseModel):
    title: str = ""
    text: str = ""
    tone: str = "温柔、克制、真实"
    images: List[DiaryJsonImage] = Field(default_factory=list)


class _MemoryUploadFile:
    def __init__(self, raw: bytes, filename: str, content_type: str):
        self._raw = raw
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._raw


def _safe_ext(filename: str, content_type: str = "") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in _ALLOWED_IMAGE_EXT:
        return ext
    guessed = mimetypes.guess_extension(content_type or "") or ".jpg"
    return guessed if guessed in _ALLOWED_IMAGE_EXT else ".jpg"


def _data_url(path: Path, mime: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime or 'image/jpeg'};base64,{encoded}"


def _today_cn() -> str:
    return datetime.now().strftime("%Y年%m月%d日")


def _plain_text_from_paragraphs(paragraphs: List[Dict[str, Any]]) -> str:
    return "\n\n".join(str(p.get("text", "")).strip() for p in paragraphs if p.get("text"))


def _fallback_layout(diary_doc: Dict[str, Any], images: List[Dict[str, Any]]) -> Dict[str, Any]:
    caption_map = {item.get("image_id"): item.get("caption", "") for item in diary_doc.get("image_captions", [])}
    image_map = {item["image_id"]: item for item in images}
    sections = []
    paragraph_image_map = []

    for paragraph in diary_doc.get("paragraphs", []):
        pid = paragraph.get("paragraph_id", "")
        image_ids = [iid for iid in paragraph.get("image_ids", []) if iid in image_map]
        figures = []
        for image_id in image_ids[:4]:
            image = image_map[image_id]
            caption = caption_map.get(image_id) or image.get("filename") or "日记照片"
            figures.append(
                '<figure class="diary-image">'
                f'<img src="{html.escape(image.get("data_url") or image.get("url") or "")}" alt="{html.escape(caption)}">'
                f"<figcaption>{html.escape(caption)}</figcaption>"
                "</figure>"
            )
        img_html = f'<div class="diary-image-grid count-{len(figures)}">{"".join(figures)}</div>' if figures else ""
        sections.append(
            f'<section class="diary-section" data-paragraph-id="{html.escape(pid)}">'
            f"<p>{html.escape(str(paragraph.get('text', '')).strip())}</p>{img_html}</section>"
        )
        paragraph_image_map.append({"paragraph_id": pid, "image_ids": image_ids, "layout": "single-center" if len(image_ids) == 1 else "grid"})

    title = html.escape(diary_doc.get("title") or "念念日记")
    date = html.escape(diary_doc.get("date") or _today_cn())
    css = """
.diary-pdf { color: #2b241b; font-family: "Noto Serif SC", "Songti SC", serif; line-height: 1.82; }
.diary-cover { text-align: center; margin: 8mm 0 12mm; padding-bottom: 8mm; border-bottom: 1px solid #e8dcc9; }
.diary-cover h1 { margin: 0; font-size: 26pt; font-weight: 600; letter-spacing: 0; }
.diary-date { margin-top: 4mm; color: #8b765c; font-size: 10pt; }
.diary-section { break-inside: avoid; margin: 0 0 10mm; }
.diary-section p { margin: 0 0 5mm; text-indent: 2em; font-size: 11.5pt; }
.diary-image-grid { break-inside: avoid; display: grid; gap: 4mm; margin: 4mm 0 2mm; }
.diary-image-grid.count-1 { display: block; text-align: center; }
.diary-image-grid.count-2, .diary-image-grid.count-3, .diary-image-grid.count-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.diary-image { break-inside: avoid; margin: 0; text-align: center; }
.diary-image img { max-width: 100%; max-height: 105mm; object-fit: contain; border-radius: 3mm; }
.diary-image-grid.count-1 .diary-image img { max-width: 84%; }
.diary-image figcaption { margin-top: 2mm; color: #8b765c; font-size: 9pt; font-style: italic; }
"""
    return {
        "html": f'<article class="diary-pdf"><header class="diary-cover"><h1>{title}</h1><div class="diary-date">{date}</div></header>{"".join(sections)}</article>',
        "css": css,
        "render_options": {"page_size": "A4", "margin": "18mm 16mm", "print_background": True},
        "paragraph_image_map": paragraph_image_map,
        "overflow_images": [],
        "quality_checks": ["fallback layout generated by backend"],
    }


def _wrap_pdf_html(layout: Dict[str, Any]) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@page {{ size: A4; margin: 18mm 16mm 20mm; }}
html, body {{ margin: 0; padding: 0; background: #fffdf8; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
* {{ box-sizing: border-box; }}
{layout.get("css", "")}
</style>
</head>
<body>{layout.get("html", "")}</body>
</html>"""


def _embed_layout_images(layout: Dict[str, Any], images: List[Dict[str, Any]]) -> Dict[str, Any]:
    html_text = str(layout.get("html", ""))
    for image in images:
        data_url = image.get("data_url", "")
        if not data_url:
            continue
        for candidate in (image.get("url", ""), html.escape(image.get("url", "")), image.get("filename", ""), image.get("stored_name", "")):
            if candidate:
                html_text = html_text.replace(candidate, data_url)
    layout["html"] = html_text
    return layout


async def _render_pdf_with_playwright(html_text: str) -> bytes:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        try:
            page = await browser.new_page(viewport={"width": 1240, "height": 1754}, device_scale_factor=1)
            await page.set_content(html_text, wait_until="networkidle")
            return await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "18mm", "right": "16mm", "bottom": "20mm", "left": "16mm"},
            )
        finally:
            await browser.close()


def _run_skill(skill_id: str, filename: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    system_prompt = load_skill(str(SKILLS_DIR / filename))
    result = call_skill(skill_id, system_prompt, payload)
    if not isinstance(result, dict):
        return {"error": True, "message": f"{skill_id} returned non-object result"}
    return result


@router.get("/assets/{diary_id}/{name}")
def get_diary_asset(diary_id: str, name: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,64}", diary_id):
        raise HTTPException(400, "invalid diary id")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "invalid asset name")
    path = DIARY_ASSET_DIR / diary_id / name
    if not path.exists():
        raise HTTPException(404, "asset not found")
    return FileResponse(str(path))


@router.get("/pdf/{diary_id}")
def get_diary_pdf(diary_id: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{8,64}", diary_id):
        raise HTTPException(400, "invalid diary id")
    path = DIARY_PDF_DIR / f"{diary_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "pdf not found")
    return FileResponse(str(path), media_type="application/pdf", filename=f"念念日记_{diary_id}.pdf")


@router.post("/transcribe")
async def transcribe_diary_audio(audio: UploadFile = File(...)) -> Dict[str, Any]:
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "empty audio")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "audio too large")

    filename = audio.filename or "diary_voice.webm"
    content_type = audio.content_type or mimetypes.guess_type(filename)[0] or "audio/webm"
    errors: List[str] = []
    provider = _diary_asr_provider()

    if provider == "llm":
        text = _transcribe_with_audio_llm(raw, filename, content_type, errors)
        if text:
            return {"ok": True, "text": text, "provider": "llm-audio", "model": _diary_llm_audio_model()}

    if provider == "dashscope_realtime":
        text = _transcribe_with_dashscope_realtime(raw, filename, content_type, errors)
        if text:
            return {"ok": True, "text": text, "provider": "dashscope-realtime", "model": _diary_dashscope_realtime_model()}

    if provider in {"auto", "dashscope"}:
        text = _transcribe_with_dashscope(raw, filename, content_type, errors)
        if text:
            return {"ok": True, "text": text, "provider": "dashscope"}

    if provider in {"auto", "302", "ai302"}:
        text = _transcribe_with_302(raw, filename, content_type, errors)
        if text:
            return {"ok": True, "text": text, "provider": "302ai", "model": _diary_302_asr_model()}

    detail = "；".join(errors[-3:]) if errors else "ASR provider is not configured"
    return {"ok": False, "text": "", "message": "日记语音识别失败", "detail": detail}


@router.post("/generate")
async def generate_diary(
    title: str = Form(""),
    text: str = Form(""),
    tone: str = Form("温柔、克制、真实"),
    images: List[UploadFile] = File(default=[]),
) -> Dict[str, Any]:
    diary_id = uuid.uuid4().hex[:16]
    asset_dir = DIARY_ASSET_DIR / diary_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    clean_title = title.strip() or "念念日记"
    clean_text = text.strip()
    clean_tone = tone.strip() or "温柔、克制、真实"

    print(f"[diary] generate request id={diary_id} title={clean_title!r} text_len={len(clean_text)} images={len(images or [])}")

    if not clean_text and not images:
        return {"error": True, "message": "请先输入文字或上传图片"}

    image_items: List[Dict[str, Any]] = []
    for index, file in enumerate(images[:8], start=1):
        raw = await file.read()
        if not raw:
            continue
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(413, f"{file.filename or '图片'} 超过 10MB")

        ext = _safe_ext(file.filename or "", file.content_type or "")
        image_id = f"img_{index:03d}_{uuid.uuid4().hex[:6]}"
        stored_name = f"{image_id}{ext}"
        save_path = asset_dir / stored_name
        save_path.write_bytes(raw)
        mime = file.content_type or mimetypes.guess_type(stored_name)[0] or "image/jpeg"

        try:
            vision_summary = sm.describe_image(raw, file.filename or stored_name)
            if vision_summary.startswith("[IMAGE_PARSE_ERROR]"):
                print(f"[diary] image vision failed {stored_name}: {vision_summary}")
                vision_summary = ""
        except Exception as exc:
            print(f"[diary] image vision exception {stored_name}: {exc}")
            vision_summary = ""

        image_items.append({
            "image_id": image_id,
            "filename": file.filename or stored_name,
            "stored_name": stored_name,
            "mime": mime,
            "size": len(raw),
            "url": f"/api/diary/assets/{diary_id}/{stored_name}",
            "data_url": _data_url(save_path, mime),
            "vision_summary": vision_summary or f"{file.filename or stored_name}：用户上传的日记图片",
            "user_caption": "",
        })

    common_payload = {"title": clean_title, "date": _today_cn(), "user_text": clean_text, "tone": clean_tone, "images": image_items}

    pairing = _run_skill("DIARY01", "DIARY01-media-pairing.md", common_payload)
    if pairing.get("error"):
        return {"ok": False, "api_called": True, "stage": "DIARY01", "message": "日记配图 Skill 调用失败", "llm_error": pairing.get("message"), "diary_id": diary_id}

    diary_doc = _run_skill("DIARY02", "DIARY02-diary-writer.md", {**pairing, "images": image_items, "user_text": clean_text})
    if diary_doc.get("error"):
        return {"ok": False, "api_called": True, "stage": "DIARY02", "message": "日记写作 Skill 调用失败", "llm_error": diary_doc.get("message"), "diary_id": diary_id}

    layout = _run_skill("DIARY03", "DIARY03-pdf-layout.md", {**diary_doc, "images": image_items, "render_target": "pdf"})
    if layout.get("error") or not layout.get("html") or not layout.get("css"):
        print(f"[diary] DIARY03 failed, backend layout fallback: {layout.get('message')}")
        layout = _fallback_layout(diary_doc, image_items)

    layout = _embed_layout_images(layout, image_items)
    try:
        pdf_bytes = await _render_pdf_with_playwright(_wrap_pdf_html(layout))
    except Exception as exc:
        print(f"[diary] pdf render failed: {exc}")
        return {"ok": False, "api_called": True, "stage": "PDF_RENDER", "message": "PDF 渲染失败，请确认 Playwright 浏览器依赖已安装", "detail": str(exc), "diary_id": diary_id}

    pdf_path = DIARY_PDF_DIR / f"{diary_id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    (DIARY_OUTPUT_DIR / f"{diary_id}.json").write_text(json.dumps({
        "diary_id": diary_id,
        "input": common_payload,
        "pairing": pairing,
        "diary": diary_doc,
        "layout": layout,
        "pdf_path": str(pdf_path),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    filename = f"{clean_title}_念念日记.pdf"
    return {
        "ok": True,
        "api_called": True,
        "diary_id": diary_id,
        "title": diary_doc.get("title") or clean_title,
        "date": diary_doc.get("date") or _today_cn(),
        "diary": _plain_text_from_paragraphs(diary_doc.get("paragraphs", [])),
        "paragraphs": diary_doc.get("paragraphs", []),
        "image_captions": diary_doc.get("image_captions", []),
        "images": [{k: v for k, v in item.items() if k != "data_url"} for item in image_items],
        "paragraph_image_map": layout.get("paragraph_image_map", []),
        "pdf_url": f"/api/diary/pdf/{diary_id}",
        "download_name": filename,
    }


@router.post("/generate-json")
async def generate_diary_json(req: DiaryJsonRequest) -> Dict[str, Any]:
    files: List[_MemoryUploadFile] = []
    for index, item in enumerate(req.images[:8], start=1):
        raw_text = (item.data_base64 or "").strip()
        if "," in raw_text and raw_text.lower().startswith("data:"):
            raw_text = raw_text.split(",", 1)[1]
        try:
            raw = base64.b64decode(raw_text)
        except Exception:
            raise HTTPException(400, f"第 {index} 张图片 base64 解码失败")
        if len(raw) > 10 * 1024 * 1024:
            raise HTTPException(413, f"{item.filename or '图片'} 超过 10MB")
        files.append(_MemoryUploadFile(raw, item.filename or f"image_{index}.jpg", item.mime or "image/jpeg"))

    return await generate_diary(title=req.title, text=req.text, tone=req.tone, images=files)  # type: ignore[arg-type]


@router.post("/generate-pdf")
async def generate_diary_pdf_download(
    title: str = Form(""),
    text: str = Form(""),
    tone: str = Form("温柔、克制、真实"),
    images: List[UploadFile] = File(default=[]),
) -> StreamingResponse:
    result = await generate_diary(title=title, text=text, tone=tone, images=images)
    if not result.get("ok"):
        raise HTTPException(400, result)
    pdf_path = DIARY_PDF_DIR / f"{result['diary_id']}.pdf"
    disposition = f"attachment; filename*=UTF-8''{quote(result.get('download_name') or '念念日记.pdf')}"
    return StreamingResponse(io.BytesIO(pdf_path.read_bytes()), media_type="application/pdf", headers={"Content-Disposition": disposition})
