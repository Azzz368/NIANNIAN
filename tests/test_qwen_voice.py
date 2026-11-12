import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import qwen_voice


class FakeSocket:
    def __init__(self, events):
        self.events = events
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        event = self.events.pop(0)
        if isinstance(event, bytes):
            return event
        if isinstance(event, dict):
            return json.dumps(event)
        return json.dumps({"header": {"event": event, "task_id": self.sent[0]["header"]["task_id"]}})


class QwenVoiceTests(unittest.TestCase):
    def test_endpoints_and_aliyun_rejection(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(qwen_voice.http_base(), "https://maas.qwencloudapi.com/api/v1")
            self.assertEqual(qwen_voice.websocket_url(), "wss://maas.qwencloudapi.com/api-ws/v1/inference")
        with patch.dict(os.environ, {"QWEN_DASHSCOPE_BASE_URL": "https://dashscope-intl.aliyuncs.com/api/v1"}):
            with self.assertRaises(qwen_voice.VoiceError):
                qwen_voice.http_base()

    def test_create_contract(self):
        with patch.object(qwen_voice, "management", return_value={"voice_id": "voice-123"}) as request:
            self.assertEqual(qwen_voice.create_voice("https://cdn.example/reference.wav", "zh"),
                             ("voice-123", qwen_voice.TARGET_MODEL))
        args, fields = request.call_args
        self.assertEqual(args, ("create_voice",))
        self.assertEqual(fields["target_model"], qwen_voice.TARGET_MODEL)
        self.assertEqual(fields["language_hints"], ["zh"])
        self.assertEqual(len(fields["prefix"]), 10)
        self.assertEqual(fields["url"], "https://cdn.example/reference.wav")

    def test_management_http_contract(self):
        response = Mock(status_code=200)
        response.json.return_value = {"output": {"voice_id": "voice-123"}}
        with patch.dict(os.environ, {"QWEN_API_KEY": "test-key"}, clear=True), \
                patch("requests.post", return_value=response) as post:
            qwen_voice.create_voice("https://cdn.example/sample.wav")
        self.assertEqual(post.call_args.args[0],
                         "https://maas.qwencloudapi.com/api/v1/services/audio/tts/customization")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "voice-enrollment")
        self.assertEqual(payload["input"]["action"], "create_voice")
        self.assertNotIn("audio", payload["input"])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_readiness_is_bounded(self):
        with patch.object(qwen_voice, "management", return_value={"status": "DEPLOYING"}) as query, \
                patch.object(qwen_voice.time, "sleep"):
            with self.assertRaisesRegex(qwen_voice.VoiceError, "retained"):
                qwen_voice.wait_until_ready("voice-123")
        self.assertEqual(query.call_count, 45)

    def test_bad_reference_and_missing_voice_id(self):
        for url in ("http://cdn.example/sample.wav", "blob:recording", "data:audio/wav;base64,abc"):
            with self.assertRaises(qwen_voice.VoiceError):
                qwen_voice.create_voice(url)
        with patch.object(qwen_voice, "management", return_value={}):
            with self.assertRaises(qwen_voice.VoiceError):
                qwen_voice.create_voice("https://cdn.example/sample.wav")

    def test_readiness(self):
        with patch.object(qwen_voice, "management", side_effect=[{"status": "DEPLOYING"}, {"status": "OK"}]), \
                patch.object(qwen_voice.time, "sleep"):
            qwen_voice.wait_until_ready("voice-123")
        for status in ("UNDEPLOYED", "unknown", None):
            with patch.object(qwen_voice, "management", return_value={"status": status}):
                with self.assertRaises(qwen_voice.VoiceError):
                    qwen_voice.wait_until_ready("voice-123")

    def run_speech(self, events, **kwargs):
        socket = FakeSocket(events)
        with patch.dict(os.environ, {"QWEN_API_KEY": "test-key"}), \
                patch("websockets.legacy.client.connect", return_value=socket) as connect:
            result = asyncio.run(qwen_voice.synthesize(" hello ", "voice-123", qwen_voice.TARGET_MODEL, **kwargs))
        self.assertEqual(connect.call_args.kwargs["extra_headers"], {"Authorization": "Bearer test-key"})
        return result, socket.sent

    def test_duplex_protocol_and_mp3(self):
        audio, messages = self.run_speech(["task-started", b"mp3-", b"audio", "task-finished"], language="zh")
        self.assertEqual(audio, b"mp3-audio")
        self.assertEqual([message["header"]["action"] for message in messages],
                         ["run-task", "continue-task", "finish-task"])
        self.assertEqual(len({message["header"]["task_id"] for message in messages}), 1)
        self.assertEqual(messages[0]["payload"]["model"], qwen_voice.TARGET_MODEL)
        self.assertEqual(messages[0]["payload"]["parameters"]["format"], "mp3")
        self.assertEqual(messages[1]["payload"]["input"]["text"], "hello")

    def test_no_false_success(self):
        for events in (["task-started", "task-finished"], ["task-started", b"partial"], ["task-failed"]):
            with self.subTest(events=events), self.assertRaises(qwen_voice.VoiceError):
                self.run_speech(list(events))

    def test_task_mismatch_and_provider_error(self):
        for event in ({"header": {"task_id": "wrong", "event": "task-started"}},
                      {"code": "InvalidApiKey"}, {"error": {"message": "rejected"}},
                      {"header": []}, {"header": "malformed"}):
            with self.subTest(event=event), self.assertRaises(qwen_voice.VoiceError):
                self.run_speech([event])

    def test_audio_size_limit(self):
        with patch.object(qwen_voice, "MAX_AUDIO_BYTES", 2):
            with self.assertRaisesRegex(qwen_voice.VoiceError, "32 MiB"):
                self.run_speech(["task-started", b"large"])

    def test_real_local_websocket_transport(self):
        from websockets.legacy.server import serve

        async def exercise():
            async def provider(socket):
                self.assertEqual(socket.request_headers["Authorization"], "Bearer test-key")
                start = json.loads(await socket.recv())
                task_id = start["header"]["task_id"]
                await socket.send(json.dumps({"header": {"event": "task-started", "task_id": task_id}}))
                continuation = json.loads(await socket.recv())
                self.assertEqual(continuation["payload"]["input"]["text"], "hello")
                self.assertEqual(json.loads(await socket.recv())["header"]["action"], "finish-task")
                await socket.send(b"local-mp3")
                await socket.send(json.dumps({"header": {"event": "task-finished", "task_id": task_id}}))

            async with serve(provider, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                with patch.object(qwen_voice, "websocket_url", return_value=f"ws://127.0.0.1:{port}"), \
                        patch.object(qwen_voice, "api_key", return_value="test-key"):
                    result = await qwen_voice.synthesize("hello", "voice-123", qwen_voice.TARGET_MODEL)
                self.assertEqual(result, b"local-mp3")

        asyncio.run(exercise())

    def test_text_validation(self):
        self.assertEqual(qwen_voice.validate_text(" hello "), "hello")
        for text in (" ", "a" * 601):
            with self.assertRaises(qwen_voice.VoiceError):
                qwen_voice.validate_text(text)
        with self.assertRaises(qwen_voice.VoiceError):
            qwen_voice.validate_text("hello", "\u4e2d" * 51)


if __name__ == "__main__":
    unittest.main()