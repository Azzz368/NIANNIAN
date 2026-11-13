import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm_client


class ChatResponseTests(unittest.TestCase):
    def test_chat_explicitly_disables_stream_for_both_models(self):
        primary = Mock()
        primary.chat.completions.create.side_effect = RuntimeError("primary failed")
        fallback = Mock()
        fallback.chat.completions.create.return_value = {"choices": [{"message": {"content": "ok"}}]}
        with patch.object(llm_client, "_iter_model_clients", return_value=[
                ("gemini-3.5-flash-lite", primary), ("gemini-3.7-flash", fallback)]), \
                patch.object(llm_client.time, "sleep"):
            self.assertEqual(llm_client.call_memorial_chat("system", []), "ok")
        for client in (primary, fallback):
            for call in client.chat.completions.create.call_args_list:
                self.assertIs(call.kwargs["stream"], False)

    def test_text_content_type_with_json_envelope(self):
        body = {"choices": [{"message": {"content": "hello"}}]}
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, text=json.dumps(body), headers={"content-type": "text/plain"}))
        with httpx.Client(transport=transport) as http_client:
            client = OpenAI(api_key="test-key", base_url="https://api.apimart.ai/v1", http_client=http_client)
            with patch.object(llm_client, "model_client", return_value=client):
                result = llm_client.call_memorial_chat("system", [], model="gemini-3.7-flash")
        self.assertEqual(result, "hello")

    def test_nonstandard_responses_are_not_chat_replies(self):
        for response in ("<html>gateway error</html>", "plain text", '{"error":{"message":"failed"}}',
                         {}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                llm_client._chat_response_text(response)

    def test_errors_include_both_models_without_returning_html(self):
        primary = Mock()
        primary.chat.completions.create.side_effect = RuntimeError("primary failed")
        fallback = Mock()
        fallback.chat.completions.create.return_value = "<html>gateway error</html>"
        with patch.object(llm_client, "_iter_model_clients", return_value=[
                ("gemini-3.5-flash-lite", primary), ("gemini-3.7-flash", fallback)]), \
                patch.object(llm_client.time, "sleep"):
            result = llm_client.call_memorial_chat("system", [])
        self.assertIn("gemini-3.5-flash-lite: primary failed", result)
        self.assertIn("gemini-3.7-flash: 上游返回非 JSON 文本", result)
        self.assertNotIn("<html>", result)
        self.assertNotIn("has no attribute", result)


if __name__ == "__main__":
    unittest.main()