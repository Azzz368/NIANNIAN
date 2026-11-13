import os
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import llm_client


class FlashMigrationTests(unittest.TestCase):
    def test_legacy_config_maps_to_new_model(self):
        self.assertEqual(llm_client._migrate_flash_model("gemini-2.5-flash"), "gemini-3.5-flash-lite")
        self.assertEqual(llm_client._migrate_flash_model("gpt-5.4"), "gpt-5.4")

    def test_new_model_uses_apimart(self):
        with patch.dict(os.environ, {"APIMART_API_KEY": "test-key", "APIMART_BASE_URL": "https://api.apimart.ai/v1"}), \
                patch.object(llm_client, "_build_client") as create:
            llm_client.model_client("gemini-3.5-flash-lite")
        create.assert_called_once_with("https://api.apimart.ai/v1", "test-key")

    def test_other_models_keep_original_provider(self):
        for model in ("gpt-5.4", "doubao-seed-2-0-lite-260215", "whisper-1"):
            self.assertIs(llm_client.model_client(model), llm_client.PRIMARY_CLIENT)

    def test_text_storyboard_and_vision_use_new_client(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])
        with patch.object(llm_client, "TEXT_MODEL", llm_client.GEMINI_FLASH_MODEL), \
                patch.object(llm_client, "STORYBOARD_MODEL", llm_client.GEMINI_FLASH_MODEL), \
                patch.object(llm_client, "VISION_MODEL", llm_client.GEMINI_FLASH_MODEL), \
                patch.object(llm_client, "model_client", return_value=client):
            self.assertEqual(llm_client.call_skill("BIO01", "system", {}), {"ok": True})
            self.assertEqual(llm_client.call_storyboard("system", "text"), {"ok": True})
            llm_client.describe_image(b"image", "photo.jpg")
        self.assertEqual(client.chat.completions.create.call_count, 3)
        for call in client.chat.completions.create.call_args_list:
            self.assertEqual(call.kwargs["model"], "gemini-3.5-flash-lite")
            self.assertNotIn("response_format", call.kwargs)

    def test_diary_legacy_audio_config_migrates(self):
        from routers import diary

        with patch.dict(os.environ, {"DIARY_LLM_AUDIO_MODEL": "gemini-2.5-flash"}):
            self.assertEqual(diary._diary_llm_audio_model(), "gemini-3.5-flash-lite")

    def test_diary_audio_llm_uses_apimart_client(self):
        from routers import diary

        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="transcript"))])
        with patch.dict(os.environ, {"DIARY_LLM_AUDIO_MODEL": "gemini-2.5-flash", "APIMART_API_KEY": "test-key"}), \
                patch.object(llm_client, "model_client", return_value=client) as select:
            self.assertEqual(diary._transcribe_with_audio_llm(b"audio", "sample.wav", "audio/wav", []), "transcript")
        select.assert_called_once_with("gemini-3.5-flash-lite")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "gemini-3.5-flash-lite")
        self.assertEqual(request["messages"][1]["content"][1]["type"], "input_audio")

    def test_missing_apimart_key_is_explicit(self):
        with patch.dict(os.environ, {"APIMART_API_KEY": ""}):
            with self.assertRaisesRegex(ValueError, "APIMART_API_KEY"):
                llm_client.model_client("gemini-3.5-flash-lite")

    def test_model_queue_keeps_other_fallback_on_302(self):
        apimart = Mock()
        with patch.dict(os.environ, {"APIMART_API_KEY": "test-key"}), \
                patch.object(llm_client, "_build_client", return_value=apimart), \
                patch.object(llm_client, "TEXT_MODEL", llm_client.GEMINI_FLASH_MODEL), \
                patch.object(llm_client, "TEXT_FALLBACK_MODEL", "gpt-5.4"):
            queue = llm_client._text_model_queue()
        self.assertEqual(queue[0], ("gemini-3.5-flash-lite", apimart))
        self.assertEqual(queue[1], ("gpt-5.4", llm_client.PRIMARY_CLIENT))

    def test_http_request_uses_apimart_chat_endpoint(self):
        captured = []

        def respond(request):
            captured.append(request)
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0,
                "model": "gemini-3.5-flash-lite", "choices": [{"index": 0,
                "finish_reason": "stop", "message": {"role": "assistant", "content": "ok"}}],
            })

        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client, \
                patch.dict(os.environ, {"APIMART_API_KEY": "test-key", "APIMART_BASE_URL": "https://api.apimart.ai/v1"}):
            client = OpenAI(api_key="test-key", base_url="https://api.apimart.ai/v1", http_client=http_client)
            with patch.object(llm_client, "_build_client", return_value=client):
                selected = llm_client.model_client(llm_client.GEMINI_FLASH_MODEL)
                selected.chat.completions.create(model=llm_client.GEMINI_FLASH_MODEL,
                                                 messages=[{"role": "user", "content": "hello"}])
        self.assertEqual(str(captured[0].url), "https://api.apimart.ai/v1/chat/completions")
        self.assertEqual(captured[0].headers["Authorization"], "Bearer test-key")
        self.assertEqual(json.loads(captured[0].content)["model"], "gemini-3.5-flash-lite")


if __name__ == "__main__":
    unittest.main()