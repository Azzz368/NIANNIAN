import unittest
import base64
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import llm_client
from backend.services import service_manager


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

    @patch.object(llm_client.time, "sleep", return_value=None)
    @patch.object(llm_client._requests, "get")
    @patch.object(llm_client._requests, "post")
    def test_seedance_asset_upload_matches_unlimited_map_and_polls_readiness(self, post, get, _sleep):
        post.side_effect = [
            _response(200, {"Result": {"Id": "group-1"}}),
            _response(200, {"Result": {"Id": "asset-1"}}),
            _response(200, {"Result": {"Items": [{"AssetId": "asset-1", "Status": "Active"}]}}),
            _response(200, {"id": "task-1"}),
        ]
        get.return_value = _response(
            200,
            {"status": "succeeded", "result_url": "https://cdn.example/seedance.mp4"},
        )
        progress = []

        result = llm_client.generate_video_tokenstar_seedance_asset(
            "Preserve the portrait; apply only a very slow camera push-in.",
            b"\xff\xd8\xfflocal-image-bytes",
            filename="portrait.jpg",
            duration=5,
            model="seedance-asset-fast",
            max_wait=8,
            progress=progress.append,
        )

        self.assertEqual(result["url"], "https://cdn.example/seedance.mp4")
        self.assertEqual(result["model"], "seedance-2.0-asset-fast")
        self.assertEqual(post.call_args_list[0].args[0], "https://api.tokenstar.world/volc/asset/CreateAssetGroup")
        upload_body = post.call_args_list[1].kwargs["json"]
        self.assertEqual(upload_body["GroupId"], "group-1")
        self.assertEqual(upload_body["MaterialGroupId"], "group-1")
        self.assertTrue(upload_body["URL"].startswith("data:image/jpeg;base64,"))
        list_body = post.call_args_list[2].kwargs["json"]
        self.assertEqual(list_body["Filter"]["GroupIds"], ["group-1"])
        generation_body = post.call_args_list[3].kwargs["json"]
        self.assertEqual(generation_body["model"], "seedance-2.0-asset-fast")
        self.assertEqual([item["type"] for item in generation_body["content"]], ["text", "image_url"])
        self.assertEqual(generation_body["content"][1]["image_url"]["url"], "asset://asset-1")
        self.assertEqual(generation_body["content"][1]["role"], "reference_image")
        self.assertEqual(generation_body["resolution"], "720p")
        self.assertEqual(get.call_args.args[0], "https://api.tokenstar.world/v1/video/generations/task-1")
        self.assertTrue(any(item.get("task_id") == "task-1" for item in progress))

    @patch.object(llm_client.time, "sleep", return_value=None)
    @patch.object(llm_client._requests, "get")
    @patch.object(llm_client._requests, "post")
    def test_seedance_prefers_public_https_asset_url(self, post, get, _sleep):
        post.side_effect = [
            _response(200, {"Id": "asset-public-1"}),
            _response(200, {"Items": [{"Id": "asset-public-1", "Status": "Active"}]}),
            _response(200, {"id": "task-public-1"}),
        ]
        get.return_value = _response(
            200,
            {"status": "succeeded", "result_url": "https://cdn.example/public.mp4"},
        )

        result = llm_client.generate_video_tokenstar_seedance_asset(
            "Only a restrained camera push-in.",
            b"\xff\xd8\xffimage",
            image_url="https://nian.example/api/video-projects/public-frame/frame.jpg",
            group_id="group-existing",
            max_wait=8,
        )

        self.assertEqual(result["url"], "https://cdn.example/public.mp4")
        upload_call = post.call_args_list[0]
        self.assertEqual(
            upload_call.kwargs["json"]["URL"],
            "https://nian.example/api/video-projects/public-frame/frame.jpg",
        )
        self.assertNotIn("files", upload_call.kwargs)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["Filter"]["GroupIds"], ["group-existing"])

    @patch.object(llm_client.time, "sleep", return_value=None)
    @patch.object(llm_client._requests, "get")
    @patch.object(llm_client._requests, "post")
    def test_seedance_asset_upload_falls_back_to_full_compat_multipart(self, post, get, _sleep):
        post.side_effect = [
            _response(200, {"Result": {"Id": "group-1"}}),
            _response(500, {"error": {"code": "material_create_failed", "message": "create material failed"}}),
            _response(200, {"Result": {"Id": "asset-1"}}),
            _response(200, {"Result": {"Items": [{"Id": "asset-1", "Status": "ACTIVE"}]}}),
            _response(200, {"task_id": "task-1"}),
        ]
        get.return_value = _response(
            200, {"status": "succeeded", "result_url": "https://cdn.example/out.mp4"}
        )

        result = llm_client.generate_video_tokenstar_seedance_asset(
            "Only a slow camera push-in.",
            b"\x89PNG\r\n\x1a\nimage-bytes",
            mime_type="application/octet-stream",
            max_wait=8,
        )

        self.assertEqual(result["url"], "https://cdn.example/out.mp4")
        fallback_form = post.call_args_list[2].kwargs["data"]
        fallback_file = post.call_args_list[2].kwargs["files"]["file"]
        self.assertEqual(fallback_form["GroupId"], "group-1")
        self.assertEqual(fallback_form["MaterialGroupId"], "group-1")
        self.assertEqual(fallback_form["asset_group_id"], "group-1")
        self.assertEqual(fallback_form["model"], "volc-asset")
        self.assertEqual(fallback_form["AssetType"], "Image")
        self.assertEqual(fallback_file[2], "image/png")

    @patch.object(llm_client.time, "sleep", return_value=None)
    @patch.object(llm_client._requests, "get")
    @patch.object(llm_client._requests, "post")
    def test_seedance_retries_until_asset_oss_object_is_ready(self, post, get, _sleep):
        post.side_effect = [
            _response(200, {"Id": "group-1"}),
            _response(200, {"Id": "asset-1"}),
            _response(200, {"Result": {"Items": [{"Id": "asset-1", "Status": "READY"}]}}),
            _response(422, {"error": {"code": "material_resource_oss_missing", "message": "material resource oss object is missing"}}),
            _response(200, {"id": "task-1"}),
        ]
        get.return_value = _response(
            200,
            {"status": "SUCCESS", "content": {"video_url": "https://cdn.example/ready.mp4"}},
        )

        result = llm_client.generate_video_tokenstar_seedance_asset(
            "Use only a restrained camera move.",
            b"\xff\xd8\xffimage",
            max_wait=8,
        )

        self.assertEqual(result["url"], "https://cdn.example/ready.mp4")
        generation_calls = [
            call for call in post.call_args_list
            if call.args[0].endswith("/v1/video/generations")
        ]
        self.assertEqual(len(generation_calls), 2)


class PublicSceneFrameTests(unittest.TestCase):
    def test_generated_frame_uses_public_https_service_url(self):
        image_b64 = base64.b64encode(b"fake-png-bytes").decode("ascii")
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service_manager, "UPLOADS_DIR", Path(temp_dir)):
                url = service_manager._public_scene_frame_url(
                    "session-123",
                    3,
                    image_b64,
                    public_base_url="https://nian.example/",
                )
                saved = list(Path(temp_dir).glob("*.png"))

        self.assertTrue(url.startswith("https://nian.example/api/assets/file/"))
        self.assertEqual(len(saved), 1)

    def test_localhost_is_not_exposed_to_tokenstar(self):
        image_b64 = base64.b64encode(b"fake-png-bytes").decode("ascii")
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service_manager, "UPLOADS_DIR", Path(temp_dir)):
                url = service_manager._public_scene_frame_url(
                    "session-123",
                    0,
                    image_b64,
                    public_base_url="http://127.0.0.1:8000/",
                )

        self.assertEqual(url, "")


if __name__ == "__main__":
    unittest.main()
