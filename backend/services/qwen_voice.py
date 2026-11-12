import asyncio
import hashlib
import json
import os
import time
import uuid
from urllib.parse import urlparse


TARGET_MODEL = "qwen-audio-3.0-tts-plus"
MAX_AUDIO_BYTES = 32 * 1024 * 1024
LANGUAGES = {"zh", "en", "de", "it", "pt", "es", "ja", "ko", "fr", "ru"}


class VoiceError(RuntimeError):
    pass


def _endpoint(value, scheme):
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != scheme or not host or parsed.username or parsed.password
            or host == "aliyuncs.com" or host.endswith(".aliyuncs.com")
            or parsed.query or parsed.fragment):
        raise VoiceError("QwenCloud endpoint must use HTTPS/WSS and must not use aliyuncs.com")
    return value.rstrip("/")


def http_base():
    return _endpoint(os.getenv("QWEN_DASHSCOPE_BASE_URL") or
                     "https://maas.qwencloudapi.com/api/v1", "https")


def websocket_url():
    base = urlparse(http_base())
    return _endpoint(os.getenv("QWEN_TTS_WEBSOCKET_URL") or
                     f"wss://{base.netloc}/api-ws/v1/inference", "wss")


def api_key():
    key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    if not key.strip():
        raise VoiceError("Configure a matching QwenCloud QWEN_API_KEY or DASHSCOPE_API_KEY")
    return key.strip()


def account_scope():
    return hashlib.sha256(f"{http_base()}|{api_key()}".encode()).hexdigest()


def management(action, *, timeout=20, **fields):
    import requests

    try:
        response = requests.post(
            f"{http_base()}/services/audio/tts/customization",
            headers={"Authorization": f"Bearer {api_key()}"},
            json={"model": "voice-enrollment", "input": {"action": action, **fields}},
            timeout=timeout,
        )
        if response.status_code != 200:
            raise VoiceError(f"QwenCloud enrollment HTTP {response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise VoiceError("Invalid QwenCloud enrollment response")
        if data.get("code") not in (None, "", "OK", "Success") or data.get("error"):
            raise VoiceError("QwenCloud rejected enrollment")
        output = data.get("output")
        if not isinstance(output, dict):
            raise VoiceError("QwenCloud enrollment returned no output")
        return output
    except (requests.RequestException, ValueError) as exc:
        raise VoiceError("QwenCloud enrollment request failed") from exc


def create_voice(reference_url, language=""):
    parsed = urlparse(reference_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise VoiceError("Reference recording requires a provider-accessible HTTPS URL")
    fields = {
        "target_model": TARGET_MODEL,
        "prefix": "v" + uuid.uuid4().hex[:9],
        "url": reference_url,
    }
    if language:
        if language not in LANGUAGES:
            raise VoiceError("Unsupported voice language")
        fields["language_hints"] = [language]
    output = management("create_voice", **fields)
    voice_id = output.get("voice_id")
    if not isinstance(voice_id, str) or not voice_id.strip():
        raise VoiceError("QwenCloud enrollment returned no voice_id")
    return voice_id, output.get("target_model") or TARGET_MODEL


def wait_until_ready(voice_id):
    deadline = time.monotonic() + 45
    for attempt in range(45):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        output = management("query_voice", voice_id=voice_id, timeout=min(10, remaining))
        status = output.get("status")
        if status == "OK":
            return
        if status == "UNDEPLOYED":
            raise VoiceError("QwenCloud rejected the reference recording (UNDEPLOYED)")
        if status != "DEPLOYING":
            raise VoiceError("QwenCloud returned an unknown voice status")
        if attempt < 44:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise VoiceError("Voice readiness timed out; voice ID retained. Retry preview, not enrollment")


def validate_text(text, instruction="", language=""):
    text = text.strip()
    if not text or len(text) > 600:
        raise VoiceError("Speech text must contain 1-600 characters")
    if sum(2 if "\u4e00" <= character <= "\u9fff" else 1 for character in instruction) > 100:
        raise VoiceError("Instruction exceeds 100 weighted characters")
    if language and language not in LANGUAGES:
        raise VoiceError("Unsupported speech language")
    return text


async def synthesize(text, voice_id, target_model, *, instruction="", language=""):
    from websockets.legacy.client import connect

    text = validate_text(text, instruction, language)
    if not voice_id or target_model != TARGET_MODEL:
        raise VoiceError("Voice target model mismatch; reenroll this voice on QwenCloud Plus")
    parameters = {"text_type": "PlainText", "voice": voice_id, "format": "mp3", "sample_rate": 24000}
    if instruction:
        parameters["instruction"] = instruction
    if language:
        parameters["language_hints"] = [language]
    task_id = str(uuid.uuid4())

    async def run():
        async with connect(
            websocket_url(), extra_headers={"Authorization": f"Bearer {api_key()}"},
            open_timeout=20, close_timeout=1, max_size=MAX_AUDIO_BYTES,
        ) as socket:
            async def send(action, payload):
                await socket.send(json.dumps({
                    "header": {"action": action, "task_id": task_id, "streaming": "duplex"},
                    "payload": payload,
                }))

            await send("run-task", {
                "task_group": "audio", "task": "tts", "function": "SpeechSynthesizer",
                "model": TARGET_MODEL, "parameters": parameters, "input": {},
            })
            chunks = []
            size = 0
            started = False
            async for message in socket:
                if isinstance(message, bytes):
                    size += len(message)
                    if size > MAX_AUDIO_BYTES:
                        raise VoiceError("Synthesized audio exceeds 32 MiB")
                    chunks.append(message)
                    continue
                try:
                    event = json.loads(message)
                    header = event.get("header") or {}
                    if not isinstance(header, dict):
                        raise ValueError("Invalid event header")
                except (ValueError, AttributeError) as exc:
                    raise VoiceError("Invalid QwenCloud speech event") from exc
                if header.get("task_id") and header["task_id"] != task_id:
                    raise VoiceError("QwenCloud task ID mismatch")
                if (header.get("event") in ("task-failed", "error") or event.get("type") == "error"
                        or event.get("error") or any(
                            code not in (None, "", "OK", "Success")
                            for code in (header.get("error_code"), event.get("code")))):
                    raise VoiceError("QwenCloud rejected speech synthesis")
                if header.get("event") == "task-started" and not started:
                    started = True
                    await send("continue-task", {"input": {"text": text}})
                    await send("finish-task", {"input": {}})
                elif header.get("event") == "task-finished":
                    if not started or not size:
                        raise VoiceError("QwenCloud completed without audio")
                    return b"".join(chunks)
            raise VoiceError("QwenCloud closed before task-finished")

    try:
        return await asyncio.wait_for(run(), timeout=120)
    except VoiceError:
        raise
    except asyncio.TimeoutError as exc:
        raise VoiceError("QwenCloud speech synthesis timed out") from exc
    except Exception as exc:
        raise VoiceError("QwenCloud speech connection failed") from exc