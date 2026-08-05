import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.services import video_project, video_renderer


PROJECT_ID = "vp_123456789abc"
SCRIPT = """# 念念导演剪辑脚本

项目编号：vp_123456789abc

## 一、导演构思
使用用户确认的院子照片，克制地建立人物与家庭记忆。

## 二、时间轴剪辑脚本
### 0—5 秒｜开场
- 使用素材：院子.jpg（asset_id：a_one）
- 画面与动态化：缓慢推进，保持人物原貌。
- 旁白：这是父亲在老家院子里的照片。
- 字幕：老家院子
- 原声：无
- 配乐：无
- 转场：交叉淡化

## 三、声音设计
保持安静。

## 四、素材取舍说明
使用 a_one。

## 五、素材缺口与风险
暂无明确缺口。
"""


def payload(asset_id="a_one"):
    return {
        "aspect_ratio": "16:9",
        "clips": [{
            "start_sec": 0,
            "end_sec": 5,
            "narrative_role": "开场",
            "asset_id": asset_id,
            "motion_prompt": "镜头非常缓慢地向人物推进，保持人物身份、五官、服装、人数和背景完全不变。",
            "narration": "这是父亲在老家院子里的照片。",
            "subtitle": "老家院子",
            "transition": {"type": "fade", "duration_sec": 0.5},
            "fact_basis": "用户确认的图片描述",
        }],
        "warnings": [],
    }


class VideoProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.memorial_root = self.root / "u_one" / "memorials" / "m_one"
        assets_dir = self.memorial_root / "assets"
        assets_dir.mkdir(parents=True)
        (assets_dir / "a_one.jpg").write_bytes(b"image-bytes")
        self.assets = [{
            "asset_id": "a_one",
            "kind": "image",
            "filename": "院子.jpg",
            "stored_name": "a_one.jpg",
            "mime": "image/jpeg",
            "user_description": "父亲在老家院子里",
        }]
        self.patchers = [
            patch.object(video_project.storage, "memorial_dir", side_effect=lambda u, m: self.root / u / "memorials" / m),
            patch.object(video_project.storage, "get_memorial", side_effect=lambda u, m: {"memorial_id": m} if (u, m) == ("u_one", "m_one") else None),
            patch.object(video_project.storage, "list_assets", side_effect=lambda u, m: list(self.assets) if (u, m) == ("u_one", "m_one") else []),
            patch.object(video_project.oss_sync, "push_path"),
            patch.object(video_project.bunny_storage, "is_configured", return_value=False),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temp.cleanup()

    def ready_manifest(self):
        digest = video_project._hash_text(SCRIPT)
        manifest = video_project.normalize_manifest("u_one", "m_one", PROJECT_ID, digest, payload())
        with patch.object(video_project, "_script", return_value=SCRIPT):
            video_project.approve_script("u_one", "m_one", PROJECT_ID)
        video_project._write_json(
            video_project._manifest_path("u_one", "m_one", PROJECT_ID), manifest
        )
        state_path = video_project._state_path("u_one", "m_one", PROJECT_ID)
        state = video_project._read_json(state_path, {})
        state["manifest_status"] = "ready"
        video_project._write_json(state_path, state)
        return manifest

    def test_fresh_project_reuses_script_but_not_manifest_or_clip_cache(self):
        self.ready_manifest()
        old_manifest = video_project._manifest_path("u_one", "m_one", PROJECT_ID)
        self.assertTrue(old_manifest.exists())

        with patch.object(video_project, "_script", return_value=SCRIPT):
            fresh = video_project.create_fresh_project_from_script(
                "u_one", "m_one", PROJECT_ID
            )

        fresh_id = fresh["project_id"]
        self.assertNotEqual(fresh_id, PROJECT_ID)
        self.assertEqual(fresh["source_project_id"], PROJECT_ID)
        self.assertFalse(video_project._manifest_path("u_one", "m_one", fresh_id).exists())
        state = video_project._read_json(
            video_project._state_path("u_one", "m_one", fresh_id), {}
        )
        self.assertEqual(state["manifest_status"], "missing")
        self.assertEqual(state["workspace_mode"], "fresh_material_selection")

    def test_compiler_agent_prompt_and_output_are_grounded_in_owned_asset(self):
        captured = {}
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload(), ensure_ascii=False)))]
        )

        def create(**kwargs):
            captured.update(kwargs)
            return completion

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with patch.object(video_project, "_script", return_value=SCRIPT), \
             patch.object(video_project, "_client", return_value=client), \
             patch.object(video_project.director_script, "_source_bundle", return_value={"asset_catalog": self.assets}):
            video_project.approve_script("u_one", "m_one", PROJECT_ID)
            result = video_project.compile_project("u_one", "m_one", PROJECT_ID)

        self.assertEqual(result["clips"][0]["asset_id"], "a_one")
        self.assertIn("缓慢地向人物推进", result["clips"][0]["motion_prompt"])
        prompt_text = "\n".join(item["content"] for item in captured["messages"])
        self.assertIn("a_one", prompt_text)
        self.assertIn("已确认导演脚本", prompt_text)
        self.assertIn("保持人物身份", prompt_text)
        self.assertIn("真实照片动态化执行导演", captured["messages"][0]["content"])

    def test_foreign_asset_id_is_rejected(self):
        with self.assertRaises(video_project.VideoProjectError) as raised:
            video_project.normalize_manifest(
                "u_one", "m_one", PROJECT_ID, "hash", payload("a_other_person")
            )
        self.assertIn("不属于当前人物", str(raised.exception))

    def test_prompt_edit_invalidates_old_result_and_persists_after_refresh(self):
        self.ready_manifest()
        with patch.object(video_project, "_script", return_value=SCRIPT):
            updated = video_project.update_prompt(
                "u_one", "m_one", PROJECT_ID, "clip_001",
                "只做极其缓慢的镜头推进，人物五官、年龄、服装、人数与院子背景保持完全不变。",
            )
            refreshed = video_project.get_project("u_one", "m_one", PROJECT_ID)
        clip = updated["clips"][0]
        self.assertEqual(clip["status"], "pending")
        self.assertEqual(clip["prompt_revision"], 2)
        self.assertEqual(refreshed["clips"][0]["motion_prompt"], clip["motion_prompt"])

    def test_script_edit_marks_manifest_stale_without_deleting_it(self):
        self.ready_manifest()
        video_project.invalidate_after_script_edit(
            "u_one", "m_one", PROJECT_ID, SCRIPT + "\n用户新补充了一条事实。"
        )
        state = video_project._read_json(
            video_project._state_path("u_one", "m_one", PROJECT_ID), {}
        )
        self.assertEqual(state["script_status"], "draft")
        self.assertEqual(state["manifest_status"], "stale")
        self.assertTrue(video_project._manifest_path("u_one", "m_one", PROJECT_ID).exists())

    def test_generation_is_idempotent_and_failure_can_fallback_to_static(self):
        self.ready_manifest()
        failed_result = {
            "error": "TokenStar Seedance 提交失败：HTTP 429；rate_limit_exceeded",
            "source": "tokenstar",
        }
        with patch.object(video_project, "_script", return_value=SCRIPT), \
             patch.object(video_project, "generate_video_tokenstar_seedance_asset", return_value=failed_result):
            first_job, created = video_project.queue_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001"
            )
            second_job, created_again = video_project.queue_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001"
            )
            video_project.run_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001", first_job,
            )
            failed = video_project.get_project("u_one", "m_one", PROJECT_ID)
            fallback = video_project.fallback_clip(
                "u_one", "m_one", PROJECT_ID, "clip_001"
            )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first_job, second_job)
        self.assertEqual(failed["clips"][0]["status"], "failed")
        self.assertIn("rate_limit_exceeded", failed["clips"][0]["error"])
        self.assertEqual(fallback["clips"][0]["render_mode"], "static")
        self.assertTrue(fallback["can_render"])

    def test_seedance_generation_uses_local_asset_and_persists_provider_ids(self):
        self.ready_manifest()

        def fake_generate(**kwargs):
            self.assertEqual(kwargs["image_bytes"], b"image-bytes")
            self.assertEqual(kwargs["model"], "seedance-2.0-asset-fast")
            self.assertEqual(
                kwargs["image_url"],
                "https://nian.example/api/video-projects/public-frame/frame.jpg",
            )
            kwargs["progress"]({
                "asset_group_id": "group-1",
                "asset_id": "remote-asset-1",
                "task_id": "task-1",
                "model": "seedance-2.0-asset-fast",
                "provider_status": "generating",
            })
            return {
                "url": "https://cdn.example/generated.mp4",
                "task_id": "task-1",
                "asset_group_id": "group-1",
                "asset_id": "remote-asset-1",
                "model": "seedance-2.0-asset-fast",
            }

        response = SimpleNamespace(
            headers={"content-length": "9"},
            raise_for_status=lambda: None,
            iter_content=lambda _size: [b"video-mp4"],
        )
        with patch.object(video_project, "_script", return_value=SCRIPT), \
             patch.object(video_project, "generate_video_tokenstar_seedance_asset", side_effect=fake_generate), \
             patch.object(video_project, "_public_frame_url", return_value="https://nian.example/api/video-projects/public-frame/frame.jpg"), \
             patch.object(video_project.requests, "get", return_value=response):
            job_id, _ = video_project.queue_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001"
            )
            video_project.run_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001", job_id
            )
            refreshed = video_project.get_project("u_one", "m_one", PROJECT_ID)

        clip = refreshed["clips"][0]
        self.assertEqual(clip["status"], "needs_review")
        self.assertEqual(clip["task_id"], "task-1")
        self.assertEqual(clip["provider_asset_id"], "remote-asset-1")
        self.assertEqual(clip["provider_status"], "succeeded")
        self.assertTrue(clip["preview_url"].endswith("/clips/clip_001/file"))

    def test_seedance_uses_bunny_cdn_and_deletes_temporary_object(self):
        self.ready_manifest()
        captured = {}

        def fake_generate(**kwargs):
            captured.update(kwargs)
            return {"error": "provider diagnostic stop", "source": "tokenstar"}

        with patch.object(video_project, "_script", return_value=SCRIPT), \
             patch.object(video_project.bunny_storage, "is_configured", return_value=True), \
             patch.object(video_project.bunny_storage, "upload_bytes", return_value={
                 "cdn_url": "https://nian-cdn.example/temp/frame.jpg",
                 "storage_key": "niannian/tokenstar/scope/job/frame.jpg",
             }) as upload, \
             patch.object(video_project.bunny_storage, "delete_file") as delete, \
             patch.object(video_project, "_public_frame_url") as public_frame, \
             patch.object(video_project, "generate_video_tokenstar_seedance_asset", side_effect=fake_generate):
            job_id, _ = video_project.queue_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001"
            )
            video_project.run_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001", job_id
            )

        self.assertEqual(captured["image_url"], "https://nian-cdn.example/temp/frame.jpg")
        upload.assert_called_once()
        delete.assert_called_once_with("niannian/tokenstar/scope/job/frame.jpg")
        public_frame.assert_not_called()

    def test_project_level_asset_group_is_persisted_and_reused(self):
        self.ready_manifest()
        captured = {}
        with patch.object(video_project, "_script", return_value=SCRIPT), \
             patch.object(video_project, "generate_video_tokenstar_seedance_asset", side_effect=lambda **kwargs: captured.update(kwargs) or {"error": "stop"}):
            job_id, _ = video_project.queue_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001"
            )
            video_project._persist_clip_result(
                "u_one", "m_one", PROJECT_ID, "clip_001", job_id,
                {"provider_asset_group_id": "ag-project-shared"},
            )
            manifest_path = video_project._manifest_path(
                "u_one", "m_one", PROJECT_ID
            )
            manifest = video_project._read_json(manifest_path, {})
            self.assertEqual(manifest["provider_asset_group_id"], "ag-project-shared")
            # Simulate another clip which has no clip-level copy of the ID.
            manifest["clips"][0]["provider_asset_group_id"] = ""
            video_project._write_json(manifest_path, manifest)
            video_project.run_clip_generation(
                "u_one", "m_one", PROJECT_ID, "clip_001", job_id
            )

        self.assertEqual(captured["group_id"], "ag-project-shared")

    def test_render_is_blocked_until_every_clip_is_approved(self):
        self.ready_manifest()
        with patch.object(video_project, "_script", return_value=SCRIPT):
            with self.assertRaises(video_project.VideoProjectError):
                video_project.queue_render("u_one", "m_one", PROJECT_ID)
            video_project.fallback_clip("u_one", "m_one", PROJECT_ID, "clip_001")
            job_id, created = video_project.queue_render("u_one", "m_one", PROJECT_ID)
            same_job, created_again = video_project.queue_render("u_one", "m_one", PROJECT_ID)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(job_id, same_job)

    def test_abandoned_generation_becomes_retryable_after_refresh(self):
        self.ready_manifest()
        with patch.object(video_project, "_script", return_value=SCRIPT):
            video_project.queue_clip_generation("u_one", "m_one", PROJECT_ID, "clip_001")
            path = video_project._manifest_path("u_one", "m_one", PROJECT_ID)
            manifest = video_project._read_json(path, {})
            manifest["clips"][0]["updated_at"] = "2000-01-01T00:00:00"
            video_project._write_json(path, manifest)
            refreshed = video_project.get_project("u_one", "m_one", PROJECT_ID)
        self.assertEqual(refreshed["clips"][0]["status"], "failed")
        self.assertIn("服务重启或超时", refreshed["clips"][0]["error"])

    def test_one_time_public_frame_is_removed_after_provider_ingestion(self):
        public_root = self.root / "public-data"
        frame_dir = public_root / "public_video_frames"
        frame_dir.mkdir(parents=True)
        name = "a" * 32 + ".jpg"
        frame = frame_dir / name
        frame.write_bytes(b"private-photo")

        with patch.object(video_project.storage, "DATA_DIR", public_root):
            video_project._cleanup_public_frame_url(
                f"https://nian.example/api/video-projects/public-frame/{name}"
            )

        self.assertFalse(frame.exists())


class VideoRendererTests(unittest.TestCase):
    def test_ffmpeg_is_called_with_argument_lists_and_shell_false(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            memorial = root / "u" / "memorials" / "m"
            assets = memorial / "assets"
            project_dir = memorial / "video_projects" / PROJECT_ID
            assets.mkdir(parents=True)
            project_dir.mkdir(parents=True)
            (assets / "photo.jpg").write_bytes(b"image")
            stored = [{"asset_id": "a_one", "kind": "image", "stored_name": "photo.jpg"}]
            manifest = {
                "project_id": PROJECT_ID,
                "memorial_id": "m",
                "script_sha256": "hash",
                "aspect_ratio": "16:9",
                "fps": 25,
                "clips": [{
                    "clip_id": "clip_001", "asset_id": "a_one", "asset_kind": "image",
                    "render_mode": "static", "status": "approved", "start_sec": 0,
                    "end_sec": 1, "duration_sec": 1, "subtitle": "", "narration": "",
                    "transition": {"type": "cut", "duration_sec": 0.04},
                    "use_source_audio": False,
                    "narration_audio_asset_id": None, "original_audio_asset_id": None,
                    "bgm_audio_asset_id": None,
                }],
            }
            calls = []

            def fake_run(command, **kwargs):
                calls.append((command, kwargs))
                Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(command[-1]).write_bytes(b"mp4")
                return SimpleNamespace(returncode=0, stderr="", stdout="")

            with patch.object(video_renderer.storage, "memorial_dir", return_value=memorial), \
                 patch.object(video_renderer.storage, "list_assets", return_value=stored), \
                 patch.object(video_renderer, "_ffmpeg", return_value="ffmpeg-safe"), \
                 patch.object(video_renderer.shutil, "which", return_value="C:/ffmpeg-safe.exe"), \
                 patch.object(video_renderer.subprocess, "run", side_effect=fake_run):
                result = video_renderer.render_project("u", "m", project_dir, manifest)

            self.assertEqual(result["render_manifest"]["status"], "completed")
            self.assertTrue((project_dir / result["relative_output"]).exists())
            self.assertTrue(calls)
            self.assertTrue(all(isinstance(call[0], list) for call in calls))
            self.assertTrue(all(call[1].get("shell") is False for call in calls))
            self.assertTrue(any("-loop" in call[0] for call in calls))


if __name__ == "__main__":
    unittest.main()
