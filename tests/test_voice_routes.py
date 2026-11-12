import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse, parse_qs

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from routers import voice


class VoiceRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(voice.router, prefix="/api")
        app.dependency_overrides[voice.security.get_current_user] = lambda: {"user_id": "owner"}
        self.client = TestClient(app)
        self.cfg = copy.deepcopy(voice.DEFAULT_VOICE)
        self.cfg.update({"voice_id": "voice-123", "provider": "qwen_tts", "status": "ready",
                         "target_model": voice.qwen_voice.TARGET_MODEL})
        self.enterContext(patch.object(voice.storage, "get_memorial", return_value={"name": "test"}))
        self.enterContext(patch.object(voice, "_get_voice_cfg", side_effect=lambda *args: copy.deepcopy(self.cfg)))
        self.save = self.enterContext(patch.object(voice, "_save_voice_cfg"))

    def test_preview_uses_plus_speech(self):
        with patch.object(voice.qwen_voice, "synthesize", new_callable=AsyncMock, return_value=b"mp3") as synth:
            response = self.client.post("/api/memorials/test/voice/preview", json={"text": "hello"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"mp3")
        self.assertIn("audio/mpeg", response.headers["content-type"])
        self.assertEqual(synth.call_args.args, ("hello", "voice-123", voice.qwen_voice.TARGET_MODEL))

    def test_no_preset_fallback_and_no_truncation(self):
        for update in ({"provider": "mock"}, {"target_model": "qwen3-tts-vc-2026-01-22"}, {"voice_id": ""}):
            original = self.cfg.copy()
            self.cfg.update(update)
            self.assertEqual(self.client.post("/api/memorials/test/voice/preview", json={"text": "hello"}).status_code, 409)
            self.cfg = original
        self.assertEqual(self.client.post("/api/memorials/test/voice/preview", json={"text": "x" * 601}).status_code, 400)

    def enrollment_request(self, readiness_error=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "assets").mkdir()
            (path / "assets" / "sample.wav").write_bytes(b"reference")
            asset = {"asset_id": "sample", "stored_name": "sample.wav", "mime": "audio/wav"}
            with patch.dict(os.environ, {"QWEN_API_KEY": "test-key"}), \
                    patch.object(voice.storage, "memorial_dir", return_value=path), \
                    patch.object(voice, "_list_audio_assets", return_value=[asset]), \
                    patch.object(voice, "_reference_url", return_value="https://cdn.example/sample.wav"), \
                    patch.object(voice.qwen_voice, "create_voice", return_value=("new-voice", voice.qwen_voice.TARGET_MODEL)), \
                    patch.object(voice.qwen_voice, "wait_until_ready", side_effect=readiness_error):
                response = self.client.post("/api/memorials/test/voice/clone", json={
                    "sample_ids": ["sample"], "consent_confirmed": True,
                })
        return response

    def test_enrollment_keeps_id_on_readiness_failure(self):
        response = self.enrollment_request(voice.qwen_voice.VoiceError("timeout"))
        self.assertEqual(response.status_code, 502)
        saved = self.save.call_args.args[2]
        self.assertEqual(saved["voice_id"], "new-voice")
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["history"][-1]["voice_id"], "new-voice")

    def test_successful_enrollment(self):
        response = self.enrollment_request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["voice"]["status"], "ready")
        self.assertEqual(response.json()["voice"]["provider"], "qwen_tts")

    def test_persistence_failure_returns_recovery_id(self):
        self.save.side_effect = OSError("disk full")
        response = self.enrollment_request()
        self.assertEqual(response.status_code, 500)
        self.assertIn("VOICE_PERSISTENCE_FAILED", response.json()["detail"])
        self.assertIn("new-voice", response.json()["detail"])

    def test_consent_required(self):
        response = self.client.post("/api/memorials/test/voice/clone", json={"sample_ids": ["sample"]})
        self.assertEqual(response.status_code, 400)

    def test_preview_recovers_without_reenrollment(self):
        self.cfg["status"] = "failed"
        with patch.object(voice.qwen_voice, "wait_until_ready") as query, \
                patch.object(voice.qwen_voice, "create_voice") as create, \
                patch.object(voice.qwen_voice, "synthesize", new_callable=AsyncMock, return_value=b"mp3"):
            response = self.client.post("/api/memorials/test/voice/preview", json={"text": "hello"})
        self.assertEqual(response.status_code, 200)
        query.assert_called_once_with("voice-123")
        create.assert_not_called()
        self.assertEqual(self.save.call_args.args[2]["status"], "ready")

    def test_account_change_rejected(self):
        self.cfg["provider_account"] = "old-account"
        with patch.object(voice.qwen_voice, "account_scope", return_value="new-account"):
            response = self.client.post("/api/memorials/test/voice/preview", json={"text": "hello"})
        self.assertEqual(response.status_code, 409)

    def test_signed_reference_returns_only_authorized_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "assets").mkdir()
            (path / "assets" / "sample.mp3").write_bytes(b"reference")
            asset = {"asset_id": "sample", "stored_name": "sample.mp3", "mime": "audio/mpeg"}
            with patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://app.example"}), \
                    patch.object(voice.storage, "memorial_dir", return_value=path), \
                    patch.object(voice, "_list_audio_assets", return_value=[asset]) as assets:
                url = voice._reference_url("owner", "test", asset)
                response = self.client.get(urlparse(url).path + "?" + urlparse(url).query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b"reference")
                assets.assert_called_with("owner", "test")
                self.assertEqual(response.headers["cache-control"], "private, no-store")

    def test_multiple_samples_rejected(self):
        response = self.client.post("/api/memorials/test/voice/clone", json={
            "sample_ids": ["one", "two"], "consent_confirmed": True,
        })
        self.assertEqual(response.status_code, 400)

    def test_signed_reference_scope_and_expiry(self):
        with patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://app.example"}):
            url = voice._reference_url("owner", "test", {"asset_id": "sample"})
        token = parse_qs(urlparse(url).query)["sig"][0]
        response = self.client.get("/api/memorials/other/voice/reference/sample", params={"sig": token})
        self.assertEqual(response.status_code, 403)
        with patch.object(voice.time, "time", return_value=1), \
                patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://app.example"}):
            expired = voice._reference_url("owner", "test", {"asset_id": "sample"})
        expired_token = parse_qs(urlparse(expired).query)["sig"][0]
        self.assertEqual(self.client.get("/api/memorials/test/voice/reference/sample", params={"sig": expired_token}).status_code, 403)


if __name__ == "__main__":
    unittest.main()