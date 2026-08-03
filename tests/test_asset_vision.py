import base64
import importlib.util
import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

_SPEC = importlib.util.spec_from_file_location(
    "asset_vision_under_test", BACKEND_DIR / "services" / "asset_vision.py"
)
assert _SPEC and _SPEC.loader
asset_vision = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(asset_vision)


def _image_bytes():
    output = BytesIO()
    Image.new("RGB", (500, 320), "white").save(output, format="PNG")
    return output.getvalue()


def _response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _response(self.content)


class AssetVisionTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def test_image_analysis_persists_searchable_visual_metadata(self):
        completions = _FakeCompletions(
            '{"summary":"一位老人坐在院子里晒太阳","tags":["老人","院子"],"ocr_text":"","people":"一人坐着","scene":"户外院落"}'
        )
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with patch.object(asset_vision, "_client", return_value=fake_client):
            result = asset_vision.analyze_image(_image_bytes(), "yard.png", "image/png")

        self.assertEqual(result["summary"], "一位老人坐在院子里晒太阳")
        self.assertIn("老人", result["search_text"])
        image_part = completions.calls[0]["messages"][1]["content"][1]
        self.assertTrue(image_part["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_semantic_ranking_only_returns_owned_asset_ids(self):
        completions = _FakeCompletions('{"asset_ids":["asset-2","not-owned"]}')
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        assets = [
            {"asset_id": "asset-1", "kind": "image", "visual_summary": "室内合影", "created_at": "2026-01-01"},
            {"asset_id": "asset-2", "kind": "image", "visual_summary": "老人坐在院子里", "created_at": "2026-01-02"},
        ]
        with patch.object(asset_vision, "_client", return_value=fake_client):
            result = asset_vision.semantic_rank_assets("找院子里的照片", assets)

        self.assertEqual(result, ["asset-2"])
        self.assertTrue(asset_vision.is_recent_reference("我刚上传的这张图片是什么"))

    def test_fallback_ranking_handles_unsegmented_chinese_query(self):
        assets = [
            {"asset_id": "asset-1", "kind": "image", "visual_summary": "室内合影", "created_at": "2026-01-01"},
            {"asset_id": "asset-2", "kind": "image", "visual_summary": "老人坐在院子里", "created_at": "2026-01-02"},
        ]
        with patch.object(asset_vision, "configured", return_value=False):
            result = asset_vision.semantic_rank_assets("找院子里的照片", assets)
        self.assertEqual(result, ["asset-2"])


if __name__ == "__main__":
    unittest.main()
