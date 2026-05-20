# backend/routers/agent_realtime.py — 念念 · Qwen-Omni-Realtime WebSocket 代理
# 浏览器 <-> 本服务 <-> wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime
#
# 协议参考：阿里云 Realtime audio and video understanding 文档
# - 浏览器推 PCM16 16kHz mono base64，事件: input_audio_buffer.append
# - 服务端回 PCM16 24kHz mono base64，事件: response.audio.delta
# - 文字流：response.audio_transcript.delta

import os
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

try:
    import websockets
    from websockets.asyncio.client import connect as ws_connect  # websockets >= 12
except Exception:  # pragma: no cover
    websockets = None
    ws_connect = None

router = APIRouter(prefix="/agent", tags=["agent-realtime"])

UPSTREAM_URL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime?model=qwen3.5-omni-plus-realtime"

NIANNIAN_INSTRUCTIONS = (
    "你是『念念』，一个温柔、细腻、有同理心的追思影像创作助手。"
    "用温暖的对话引导用户讲述思念之人的故事、性格、人生经历；"
    "语气克制、有分寸，像贴心的倾听者。每次回复控制在 80 字以内，"
    "主动追问一个具体细节。使用中文。"
)


@router.websocket("/realtime")
async def realtime_proxy(client_ws: WebSocket):
    """
    浏览器 <-> 本端点 <-> 阿里云 Qwen Realtime
    双向透传 JSON 事件；连接建立后由服务端先发送 session.update 配置念念人格。
    """
    await client_ws.accept()

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        await client_ws.send_json({
            "type": "error",
            "message": "服务端未配置 DASHSCOPE_API_KEY，无法启用实时语音。"
        })
        await client_ws.close()
        return

    if ws_connect is None:
        await client_ws.send_json({
            "type": "error",
            "message": "服务端缺少 websockets 库，请安装：pip install websockets>=12"
        })
        await client_ws.close()
        return

    headers = [("Authorization", f"Bearer {api_key}")]

    try:
        async with ws_connect(
            UPSTREAM_URL,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=30,
        ) as upstream:
            # ── 1. 推送 session 配置 ─────────────────────────────────
            session_cfg = {
                "event_id": "evt_nn_session_init",
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": "Serena",                # 温柔女声，适合追思
                    "instructions": NIANNIAN_INSTRUCTIONS,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_sample_rate": 16000,
                    "output_audio_sample_rate": 24000,
                    "input_audio_transcription": {"model": "paraformer-realtime-v2"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 600,
                    },
                },
            }
            await upstream.send(json.dumps(session_cfg, ensure_ascii=False))

            # ── 2. 双向透传 ─────────────────────────────────────────
            async def client_to_upstream():
                try:
                    while True:
                        msg = await client_ws.receive_text()
                        await upstream.send(msg)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print(f"[realtime] c2u closed: {e}")

            async def upstream_to_client():
                try:
                    async for msg in upstream:
                        if isinstance(msg, (bytes, bytearray, memoryview)):
                            msg = bytes(msg).decode("utf-8", errors="ignore")
                        await client_ws.send_text(str(msg))
                except Exception as e:
                    print(f"[realtime] u2c closed: {e}")

            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()

    except Exception as e:
        try:
            await client_ws.send_json({"type": "error", "message": f"上游连接失败: {e}"})
        except Exception:
            pass

    try:
        await client_ws.close()
    except Exception:
        pass
