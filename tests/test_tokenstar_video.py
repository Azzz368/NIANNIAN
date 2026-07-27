import unittest
from unittest.mock import Mock, patch

import llm_client


def _response(status, payload, headers=None):
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    response.headers = headers or {}
    response.text = ""
    return response


class TokenStarVideoTests(unittest.TestCase):
    def setUp(self):
        self.key_patch = patch.object(llm_client, "TOKENSTAR_API_KEY", "test-key")
        self.base_patch = patch.object(
            llm_client, "TOKENSTAR_BASE_URL", "https://api.tokenstar.world/v1"
        )
        self.key_patch.start()
        self.base_patch.start()

    def tearDown(self):
        self.base_patch.stop()
        self.key_patch.stop()

    @patch.object(llm_client.time, "sleep", return_value=None)
    @patch.object(llm_client._requests, "get")
    @patch.object(llm_client._requests, "post")
    def test_success_uses_configured_default_sound_on(self, post, get, _sleep):
        post.return_value = _response(200, {"code": "0", "data": {"task_id": "task-1"}})
        get.return_value = _response(
            200,
            {
                "code": 0,
                "data": {
                    "task_status": "SUCCESS",
                    "task_result": {
                        "videos": [{"url": "https://cdn.example/video-result"}]
                    },
                },
            },
        )

        result = llm_client.generate_video_tokenstar_i2v(
            "subtle natural motion",
            image_url="https://cdn.example/frame.png",
            max_wait=15,
        )

        self.assertEqual(result["url"], "https://cdn.example/video-result")
        submit_url = post.call_args.args[0]
        submit_body = post.call_args.kwargs["json"]
        self.assertEqual(submit_url, "https://api.tokenstar.world/v1/videos/image2video")
        self.assertEqual(submit_body["image"], "https://cdn.example/frame.png")
        self.assertEqual(submit_body["model_name"], "kling-v3")
        self.assertEqual(submit_body["sound"], "on")
        self.assertNotIn("aspect_ratio", submit_body)

    @patch.object(llm_client._requests, "post")
    def test_submit_error_preserves_code_param_and_request_id(self, post):
        post.return_value = _response(
            400,
            {
                "error": {
                    "code": "invalid_request",
                    "message": "sound is unsupported",
                    "param": "sound",
                }
            },
            {"x-request-id": "request-123"},
        )

        result = llm_client.generate_video_tokenstar_i2v(
            "motion",
            image_url="https://cdn.example/frame.png",
            poll=False,
        )

        self.assertIn("code=invalid_request", result["error"])
        self.assertIn("param=sound", result["error"])
        self.assertIn("request_id=request-123", result["error"])

    @patch.object(llm_client.time, "sleep", return_value=None)
    @patch.object(llm_client._requests, "get")
    @patch.object(llm_client._requests, "post")
    def test_failure_status_reports_task_reason(self, post, get, _sleep):
        post.return_value = _response(200, {"data": {"task_id": "task-2"}})
        get.return_value = _response(
            200,
            {
                "data": {
                    "status": "FAILURE",
                    "task_status_msg": "ImageDownloadError",
                }
            },
        )

        result = llm_client.generate_video_tokenstar_i2v(
            "motion",
            image_url="https://cdn.example/frame.png",
            max_wait=15,
        )

        self.assertEqual(result["task_id"], "task-2")
        self.assertIn("ImageDownloadError", result["error"])


if __name__ == "__main__":
    unittest.main()
