import os
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from core import studio_ai


class StudioAITests(unittest.TestCase):
    def test_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(studio_ai.model(), "gpt-6-luna")

    def test_missing_key_fails_without_fallback(self):
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "old-key"}, clear=True):
            with self.assertRaisesRegex(ValueError, "APIMART_API_KEY"):
                studio_ai.client()

    def test_apimart_client(self):
        with patch.dict(os.environ, {"APIMART_API_KEY": "test-key"}, clear=True), \
                patch.object(studio_ai, "OpenAI") as create:
            studio_ai.client()
        create.assert_called_once_with(api_key="test-key", base_url="https://api.apimart.ai/v1")

    def test_chat_completions_http_contract(self):
        captured = []

        def respond(request):
            captured.append(request)
            return httpx.Response(200, json={
                "id": "test", "object": "chat.completion", "created": 0,
                "model": "gpt-6-luna", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "test reply"}}],
            })

        with patch.dict(os.environ, {"APIMART_API_KEY": "test-key"}, clear=True), \
                httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            def create_client(**kwargs):
                return OpenAI(**kwargs, http_client=http_client)

            with patch.object(studio_ai, "OpenAI", side_effect=create_client):
                client = studio_ai.client()
            reply = client.chat.completions.create(
                model=studio_ai.model(), messages=[{"role": "user", "content": "hello"}],
            )
        self.assertEqual(reply.choices[0].message.content, "test reply")
        self.assertEqual(str(captured[0].url), "https://api.apimart.ai/v1/chat/completions")
        self.assertEqual(captured[0].headers["Authorization"], "Bearer test-key")
        self.assertEqual(json.loads(captured[0].content)["model"], "gpt-6-luna")

    def test_studio_services_share_client_and_model(self):
        from services import director_script, video_project

        with patch.object(studio_ai, "client", return_value="apimart-client") as create:
            self.assertEqual(director_script._client(), "apimart-client")
            self.assertEqual(video_project._client(), "apimart-client")
        self.assertEqual(create.call_count, 2)


if __name__ == "__main__":
    unittest.main()