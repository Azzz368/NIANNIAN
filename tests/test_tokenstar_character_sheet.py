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

_SPEC = importlib.util.spec_from_file_location(
    "character_sheet_under_test", BACKEND_DIR / "services" / "tokenstar_character_sheet.py"
)
assert _SPEC and _SPEC.loader
character_sheet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(character_sheet)


def _png_b64() -> str:
    output = BytesIO()
    Image.new("RGB", (400, 400), "white").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _response(status, payload):
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    response.text = ""
    return response


class TokenStarCharacterSheetTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"TOKENSTAR_API_KEY": "test-key"}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    @patch.object(character_sheet._requests, "post")
    def test_uses_gemini_3_pro_image_endpoint_with_photorealistic_reference(self, post):
        post.return_value = _response(200, {
            "candidates": [{"content": {"parts": [
                {"text": "done"},
                {"inlineData": {"mimeType": "image/png", "data": "cmVzdWx0"}},
            ]}}]
        })

        result = character_sheet.generate_character_sheet(_png_b64())

        self.assertEqual(result["source"], "tokenstar_gemini_3_pro")
        self.assertEqual(result["image_data_url"], "data:image/png;base64,cmVzdWx0")
        self.assertEqual(
            post.call_args.args[0],
            "https://api.tokenstar.world/v1beta/models/gemini-3-pro-image-preview:generateContent",
        )
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["generationConfig"]["imageConfig"]["aspectRatio"], "16:9")
        parts = body["contents"][0]["parts"]
        self.assertIn("三视图", parts[0]["text"])
        self.assertIn("不得生成动漫", parts[0]["text"])
        self.assertIn("真人参考照片", parts[0]["text"])
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/png")

    def test_rejects_data_uri_reference(self):
        with self.assertRaisesRegex(ValueError, "data: 前缀"):
            character_sheet.generate_character_sheet("data:image/png;base64,abcd")


if __name__ == "__main__":
    unittest.main()
