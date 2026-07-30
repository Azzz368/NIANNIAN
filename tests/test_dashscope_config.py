import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core import dashscope_config


class DashScopeConfigTests(unittest.TestCase):
    def test_international_is_the_safe_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(dashscope_config.region(), "intl")
            self.assertIn("dashscope-intl", dashscope_config.compatible_base_url())
            self.assertIn("dashscope-intl", dashscope_config.realtime_ws_url())

    def test_china_region_uses_domestic_endpoints(self):
        with patch.dict(os.environ, {"DASHSCOPE_REGION": "cn"}, clear=True):
            self.assertEqual(dashscope_config.region(), "cn")
            self.assertNotIn("dashscope-intl", dashscope_config.compatible_base_url())
            self.assertNotIn("dashscope-intl", dashscope_config.realtime_ws_url())


if __name__ == "__main__":
    unittest.main()
