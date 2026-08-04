import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.services import bunny_storage


class BunnyStorageTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "BUNNY_STORAGE_ZONE": "nian-zone",
            "BUNNY_ACCESS_KEY": "test-secret",
            "BUNNY_STORAGE_REGION": "sg",
            "BUNNY_PULL_ZONE_URL": "https://nian-cdn.example",
        },
        clear=False,
    )
    @patch.object(bunny_storage.requests, "get")
    @patch.object(bunny_storage.requests, "put")
    def test_upload_returns_public_pull_zone_url(self, put, get):
        put.return_value = Mock(status_code=201, text="")
        get_response = Mock(status_code=206)
        get.return_value = get_response

        result = bunny_storage.upload_bytes(
            b"image-bytes",
            "niannian/tokenstar/scope/job/frame.jpg",
            "image/jpeg",
        )

        self.assertEqual(
            result["cdn_url"],
            "https://nian-cdn.example/niannian/tokenstar/scope/job/frame.jpg",
        )
        self.assertEqual(
            put.call_args.args[0],
            "https://sg.storage.bunnycdn.com/nian-zone/niannian/tokenstar/scope/job/frame.jpg",
        )
        self.assertEqual(put.call_args.kwargs["headers"]["AccessKey"], "test-secret")
        get_response.close.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "BUNNY_STORAGE_ZONE": "nian-zone",
            "BUNNY_ACCESS_KEY": "test-secret",
            "BUNNY_STORAGE_REGION": "sg",
            "BUNNY_PULL_ZONE_URL": "https://nian-cdn.example",
        },
        clear=False,
    )
    @patch.object(bunny_storage.requests, "delete")
    def test_delete_uses_storage_api_not_public_cdn(self, delete):
        delete.return_value = Mock(status_code=200, text="")

        bunny_storage.delete_file("niannian/tokenstar/scope/job/frame.jpg")

        self.assertTrue(delete.call_args.args[0].startswith("https://sg.storage.bunnycdn.com/"))
        self.assertEqual(delete.call_args.kwargs["headers"]["AccessKey"], "test-secret")


if __name__ == "__main__":
    unittest.main()
