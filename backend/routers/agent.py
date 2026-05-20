# backend/routers/agent.py — 念念智能体 · Qwen3.5-omni-plus 流式对话 + DashScope ASR
import os, json, io
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List
from openai import OpenAI

router = APIRouter(prefix="/agent", tags=["agent"])

SYSTEM_PROMPT = """你是「念念」，一个温柔、细腻、有同理心的追思影像创作助手。

你的使命：
- 通过温暖的对话，引导用户讲述逝者（或思念对象）的故事、性格、人生经历
- 收集制作追思影像所需的关键信息：姓名、生平、记忆片段、情感寄托
- 当信息积累足够时，自然地引导用户进入正式建档流程

对话风格：
- 温柔、克制、有分寸感，像一个贴心的倾听者
- 每次回复不超过80字，简短真诚，主动追问细节
- 使用中文，偶尔用诗意的表达
- 不要冷冰冰地列清单，而是顺着对方的话自然展开

开场方式：主动问候，询问用户想聊谁，表达愿意倾听。"""


def get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )


class AgentMessage(BaseModel):
    role: str
    content: str


class AgentChatRequest(BaseModel):
    message: str
    history: List[AgentMessage] = []


@router.post("/chat")
async def agent_chat(req: AgentChatRequest):
    """流式 SSE 端点：纯文字流，朗读由前端 speechSynthesis 处理"""
    client = get_client()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in req.history[-30:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": req.message})

    def generate():
        try:
            stream = client.chat.completions.create(  # type: ignore[call-overload]
                model="qwen-plus",          # 文本对话用 qwen-plus，稳定快速
                messages=messages,          # type: ignore[arg-type]
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    payload = json.dumps({"type": "text", "delta": delta.content}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
        except Exception as e:
            payload = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/asr")
async def agent_asr(audio: UploadFile = File(...)):
    """
    语音转文字：接收前端录音（webm/wav/ogg），
    通过 DashScope 兼容 OpenAI Whisper 接口转录，返回中文文本。
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="DASHSCOPE_API_KEY 未配置")

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    audio_bytes = await audio.read()
    # DashScope 支持 wav/mp3/webm/ogg，用原始文件名后缀
    filename = audio.filename or "audio.webm"

    try:
        transcript = client.audio.transcriptions.create(
            model="paraformer-realtime-v2",
            file=(filename, io.BytesIO(audio_bytes), audio.content_type or "audio/webm"),
            language="zh",
        )
        return JSONResponse({"text": transcript.text})
    except Exception as e:
        # fallback：尝试通用 whisper-1
        try:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=(filename, io.BytesIO(audio_bytes), audio.content_type or "audio/webm"),
                language="zh",
            )
            return JSONResponse({"text": transcript.text})
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"ASR 失败: {e2}")
