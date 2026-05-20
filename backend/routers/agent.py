# backend/routers/agent.py — 念念智能体 · Qwen3.5-omni-plus 语音+文字聊天
import os, json, base64
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
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
    voice_out: bool = False


@router.post("/chat")
async def agent_chat(req: AgentChatRequest):
    """流式 SSE 端点：支持文字回复 + 可选音频输出"""
    client = get_client()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in req.history[-30:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": req.message})

    def generate():
        audio_chunks: list[str] = []
        try:
            if req.voice_out:
                stream = client.chat.completions.create(  # type: ignore[call-overload]
                    model="qwen3.5-omni-plus",
                    messages=messages,  # type: ignore[arg-type]
                    modalities=["text", "audio"],
                    audio={"voice": "Ethan", "format": "wav"},
                    stream=True,
                    stream_options={"include_usage": True},
                )
            else:
                stream = client.chat.completions.create(  # type: ignore[call-overload]
                    model="qwen3.5-omni-plus",
                    messages=messages,  # type: ignore[arg-type]
                    modalities=["text"],
                    stream=True,
                    stream_options={"include_usage": True},
                )

            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # 文字片段
                if getattr(delta, "content", None):
                    payload = json.dumps({"type": "text", "delta": delta.content}, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                # 音频片段
                if req.voice_out:
                    audio = getattr(delta, "audio", None)
                    if audio and getattr(audio, "data", None):
                        audio_chunks.append(audio.data)

            # 发送完整音频（base64 WAV）
            if audio_chunks:
                combined = "".join(audio_chunks)
                payload = json.dumps({"type": "audio", "data": combined})
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
