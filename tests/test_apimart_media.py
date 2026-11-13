import base64
from io import BytesIO
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import apimart_media


def response(body):
    return Mock(status_code=200, json=Mock(return_value=body))


class APIMartMediaTests(unittest.TestCase):
    def test_existing_image_entry_returns_16_9_png(self):
        import llm_client
        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (64, 64), "green").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()
        with patch("backend.services.apimart_media.generate_image_apimart", return_value=(encoded, None)) as generate:
            image, error = llm_client.generate_image_tokenstar("scene", reference_b64="reference")
        self.assertIsNone(error)
        with Image.open(BytesIO(base64.b64decode(image))) as rendered:
            self.assertEqual(rendered.width * 9, rendered.height * 16)
            self.assertEqual(rendered.format, "PNG")
        self.assertEqual(generate.call_args.kwargs["reference_b64"], "reference")

    @patch.dict(os.environ, {"APIMART_API_KEY": "test-key", "APIMART_BASE_URL": "https://api.apimart.ai/v1"})
    @patch.object(apimart_media.time, "sleep")
    @patch.object(apimart_media.requests, "get")
    @patch.object(apimart_media.requests, "post")
    def test_first_frame_1080p_and_result_array(self, post, get, pause):
        post.return_value = response({"code": 200, "data": [{"task_id": "task-1"}]})
        get.return_value = response({"code": 200, "data": {"status": "completed", "result": {
            "videos": [{"url": ["https://cdn.example/video.mp4"]}]}}})
        result = apimart_media.generate_video_apimart("motion", "https://cdn.example/frame.png")
        self.assertEqual(result["url"], "https://cdn.example/video.mp4")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["first_frame_image"], "https://cdn.example/frame.png")
        self.assertEqual(body["resolution"], "1080P")
        self.assertEqual(body["model"], "MiniMax-H3-Max")
        self.assertNotIn("watermark", body)
        self.assertNotIn("image_urls", body)
        self.assertEqual(get.call_args.args[0], "https://api.apimart.ai/v1/tasks/task-1")

    @patch.dict(os.environ, {"APIMART_API_KEY": "test-key"})
    @patch.object(apimart_media.requests, "post")
    def test_invalid_duration_does_not_submit(self, post):
        self.assertIn("error", apimart_media.generate_video_apimart("motion", "https://cdn.example/frame.png", duration=4))
        post.assert_not_called()

    @patch.dict(os.environ, {"APIMART_API_KEY": "test-key"})
    @patch.object(apimart_media.time, "sleep")
    @patch.object(apimart_media.requests, "get")
    @patch.object(apimart_media.requests, "post")
    def test_video_failure_and_tail_frame(self, post, get, pause):
        post.return_value = response({"data": [{"task_id": "task-fail"}]})
        get.return_value = response({"data": {"status": "failed", "error": {"message": "rejected"}}})
        result = apimart_media.generate_video_apimart("motion", "https://cdn.example/start.png",
            image_tail_url="https://cdn.example/end.png")
        self.assertIn("rejected", result["error"])
        self.assertEqual(result["task_id"], "task-fail")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(post.call_args.kwargs["json"]["last_frame_image"], "https://cdn.example/end.png")

    @patch.dict(os.environ, {"APIMART_API_KEY": "test-key"})
    @patch.object(apimart_media.requests, "post")
    def test_video_timeout_preserves_task(self, post):
        post.return_value = response({"data": [{"task_id": "task-wait"}]})
        result = apimart_media.generate_video_apimart("motion", "https://cdn.example/frame.png", max_wait=0)
        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["task_id"], "task-wait")
        post.assert_called_once()

    @patch.dict(os.environ, {"APIMART_API_KEY": "test-key"})
    @patch.object(apimart_media.time, "sleep")
    @patch.object(apimart_media.requests, "get")
    @patch.object(apimart_media.requests, "post")
    def test_image_reference_upload_medium_and_async_download(self, post, get, pause):
        post.side_effect = [response({"url": "https://cdn.example/ref.png"}),
                            response({"data": [{"task_id": "image-1"}]})]
        downloaded = Mock()
        downloaded.__enter__ = Mock(return_value=downloaded)
        downloaded.__exit__ = Mock(return_value=False)
        downloaded.iter_content.return_value = [b"image-bytes"]
        get.side_effect = [response({"data": {"status": "completed", "result": {
            "images": [{"url": ["https://cdn.example/image.png"]}]}}}), downloaded]
        image, error = apimart_media.generate_image_apimart("portrait", base64.b64encode(b"reference").decode())
        self.assertIsNone(error)
        self.assertEqual(base64.b64decode(image), b"image-bytes")
        upload = post.call_args_list[0]
        self.assertEqual(upload.kwargs["files"]["file"][1], b"reference")
        self.assertEqual(upload.kwargs["params"], {"retention_days": 3})
        self.assertNotIn("Content-Type", upload.kwargs["headers"])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "gpt-image-2.5-flare")
        self.assertEqual(body["quality"], "medium")
        self.assertEqual(body["size"], "16:9")
        self.assertEqual(body["resolution"], "1k")
        self.assertEqual(body["n"], 1)
        self.assertEqual(body["image_urls"], ["https://cdn.example/ref.png"])

    @patch.dict(os.environ, {"APIMART_API_KEY": "test-key"})
    @patch.object(apimart_media.time, "sleep")
    @patch.object(apimart_media.requests, "get")
    @patch.object(apimart_media.requests, "post")
    def test_image_failure_does_not_resubmit(self, post, get, pause):
        post.return_value = response({"data": [{"task_id": "image-fail"}]})
        get.return_value = response({"data": {"status": "failed", "error": {"message": "rejected"}}})
        image, error = apimart_media.generate_image_apimart("portrait")
        self.assertIsNone(image)
        self.assertIn("rejected", error)
        self.assertNotIn("image_urls", post.call_args.kwargs["json"])
        post.assert_called_once()

    @patch.dict(os.environ, {"APIMART_API_KEY": ""})
    @patch.object(apimart_media.requests, "post")
    def test_missing_key_and_private_frame_do_not_submit(self, post):
        self.assertIn("APIMART_API_KEY", apimart_media.generate_video_apimart("motion", "https://cdn.example/f.png")["error"])
        self.assertFalse(apimart_media._public_url("https://192.168.1.1/frame.png"))
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()