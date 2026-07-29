import base64
import importlib.util
import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

_MODULE_SPEC = importlib.util.spec_from_file_location(
    "kling_avatar_under_test", BACKEND_DIR / "services" / "kling_avatar.py"
)
assert _MODULE_SPEC and _MODULE_SPEC.loader
kling_avatar = importlib.util.module_from_spec(_MODULE_SPEC)
_MODULE_SPEC.loader.exec_module(kling_avatar)


def _png_b64() -> str:
    image = Image.new("RGB", (400, 400), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _response(status, payload, headers=None):
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    response.headers = headers or {}
    response.text = ""
    return response


class KlingAvatarTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"KLING_API_KEY": "test-key"}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    @patch.object(kling_avatar._requests, "request")
    def test_create_uses_official_avatar_endpoint_with_raw_base64(self, request):
        request.return_value = _response(
            200, {"code": 0, "request_id": "req-1", "data": {"task_id": "avatar-1", "task_status": "submitted"}}
        )

        result = kling_avatar.create_avatar_task(
            _png_b64(), base64.b64encode(b"fake-audio").decode("ascii"), "自然讲话", "pro", True
        )

        self.assertEqual(result["task_id"], "avatar-1")
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(request.call_args.args[0], "POST")
        self.assertEqual(
            request.call_args.args[1],
            "https://api-beijing.klingai.com/v1/videos/avatar/image2video",
        )
        body = request.call_args.kwargs["json"]
        self.assertNotIn("data:", body["image"])
        self.assertNotIn("data:", body["sound_file"])
        self.assertEqual(body["mode"], "pro")
        self.assertEqual(body["watermark_info"], {"enabled": True})

    @patch.object(kling_avatar._requests, "request")
    def test_task_status_returns_official_video_url(self, request):
        request.return_value = _response(
            200,
            {
                "code": 0,
                "data": {
                    "task_id": "avatar-1",
                    "task_status": "succeed",
                    "task_result": {"videos": [{"url": "https://cdn.example/avatar.mp4", "duration": "8"}]},
                },
            },
        )

        result = kling_avatar.get_avatar_task("avatar-1")

        self.assertEqual(result["status"], "succeed")
        self.assertEqual(result["video_url"], "https://cdn.example/avatar.mp4")
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertEqual(
            request.call_args.args[1],
            "https://api-beijing.klingai.com/v1/videos/avatar/image2video/avatar-1",
        )

    def test_rejects_data_uri_prefix(self):
        with self.assertRaisesRegex(ValueError, "不要包含 data: 前缀"):
            kling_avatar.create_avatar_task("data:image/png;base64,abcd", "YWJj")


if __name__ == "__main__":
    unittest.main()
