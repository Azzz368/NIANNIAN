import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
for path in (ROOT_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.services import material_context, service_manager, session_store
from backend.routers import agent as agent_router


class MaterialContractTests(unittest.TestCase):
    def test_normalize_keeps_user_description_separate_from_ai_summary(self):
        value = material_context.normalize_asset({
            "asset_id": "asset-1",
            "kind": "image",
            "filename": "yard.jpg",
            "description": "这是父亲 2008 年在老家院子里的照片",
            "visual_summary": "一名男子站在院子里",
            "visual_tags": ["院子"],
        })

        self.assertEqual(value["user_description"], "这是父亲 2008 年在老家院子里的照片")
        self.assertEqual(value["ai_summary"], "一名男子站在院子里")
        self.assertIn("video_storyboard", value["usable_for"])

    def test_catalog_search_supports_chinese_scene_query(self):
        catalog = [
            material_context.normalize_asset({
                "asset_id": "asset-yard",
                "kind": "image",
                "description": "父亲年轻时在老家院子里拍的照片",
                "created_at": "2026-01-02",
            }),
            material_context.normalize_asset({
                "asset_id": "asset-office",
                "kind": "image",
                "description": "办公室合影",
                "created_at": "2026-01-01",
            }),
        ]

        result = material_context.search_asset_catalog("父亲年轻时院子里的照片", catalog)
        self.assertEqual(result[0]["asset_id"], "asset-yard")

    def test_inventory_query_lists_every_file_instead_of_two_selected_images(self):
        catalog = [
            material_context.normalize_asset({
                "asset_id": "image-1",
                "kind": "image",
                "filename": "自拍1.png",
                "vision_status": "succeeded",
            }),
            material_context.normalize_asset({
                "asset_id": "image-2",
                "kind": "image",
                "filename": "自拍2.png",
            }),
            material_context.normalize_asset({
                "asset_id": "audio-1",
                "kind": "audio",
                "filename": "日常录音.mp3",
            }),
        ]

        self.assertTrue(material_context.is_inventory_query("素材库有什么"))
        stats = material_context.catalog_analysis_stats(catalog)
        reply = agent_router._catalog_inventory_reply(
            catalog, stats["not_analyzed_asset_ids"]
        )

        self.assertIn("素材库共 3 项", reply)
        self.assertIn("自拍1.png", reply)
        self.assertIn("自拍2.png", reply)
        self.assertIn("日常录音.mp3", reply)
        self.assertIn("未完成深度识别不等于没有素材", reply)

    def test_agent_inventory_ignores_stale_selected_asset_ids(self):
        catalog = [
            material_context.normalize_asset({
                "asset_id": "image-1", "kind": "image", "filename": "自拍1.png",
            }),
            material_context.normalize_asset({
                "asset_id": "image-2", "kind": "image", "filename": "自拍2.png",
            }),
            material_context.normalize_asset({
                "asset_id": "audio-1", "kind": "audio", "filename": "录音.mp3",
            }),
        ]
        request = agent_router.AgentChatRequest(
            message="素材库有什么",
            memorial_id="m-1",
            asset_ids=["image-1"],
        )

        async def collect_response():
            response = await agent_router.agent_chat(
                request, user={"user_id": "u-1"}
            )
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(
                    chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                )
            return "".join(chunks)

        with patch.object(agent_router, "get_client", return_value=object()), \
             patch.object(agent_router.memory_mod, "get_memory_brief", return_value=""), \
             patch.object(agent_router.storage, "get_dossier", return_value={}), \
             patch.object(agent_router.storage, "get_memorial", return_value={"memorial_id": "m-1"}), \
             patch.object(agent_router.material_context, "build_asset_catalog", return_value=catalog), \
             patch.dict(agent_router.os.environ, {"DASHSCOPE_API_KEY": ""}, clear=False):
            body = asyncio.run(collect_response())

        self.assertIn("素材库共 3 项", body)
        self.assertIn("自拍2.png", body)
        self.assertIn("录音.mp3", body)

    def test_storyboard_skips_unanalysed_or_weak_real_photo_matches(self):
        catalog = [
            material_context.normalize_asset({
                "asset_id": "asset-yard",
                "kind": "image",
                "filename": "yard.jpg",
                "description": "父亲年轻时在老家院子里拍的照片",
                "url": "/api/memorials/m-1/assets/asset-yard",
            })
        ]
        result = material_context.attach_assets_to_storyboard(
            {"scenes": [{"scene_id": "S01", "description": "父亲年轻时站在老家院子里"}]},
            {"assets": catalog},
        )

        scene = result["scenes"][0]
        self.assertEqual(scene["source_asset_ids"], [])
        self.assertEqual(scene["media_strategy"], "ai_generated")
        self.assertEqual(result["material_usage"]["strict_min_score"], 3)
        self.assertEqual(len(result["material_usage"]["skipped_recommendations"]), 1)


class MemorialContextTests(unittest.TestCase):
    @patch.object(material_context.storage, "list_assets")
    @patch.object(material_context.storage, "read_conversations")
    @patch.object(material_context.storage, "get_dossier")
    @patch.object(material_context.storage, "get_memorial")
    def test_context_combines_dossier_agent_chat_session_chat_and_assets(
        self, get_memorial, get_dossier, read_conversations, list_assets
    ):
        get_memorial.return_value = {"memorial_id": "m-1"}
        get_dossier.return_value = {"subject": {"name": "父亲"}, "memories": [{"title": "院子"}]}
        read_conversations.return_value = [{"role": "user", "content": "他喜欢种花"}]
        list_assets.return_value = [{
            "asset_id": "asset-1",
            "kind": "image",
            "description": "院子里的照片",
        }]
        session = {
            "form_data": {"user_id": "u-1", "memorial_id": "m-1"},
            "chat_history": [{"role": "user", "content": "这是他年轻时"}],
            "assets": [],
        }

        context = material_context.build_memorial_context(session)

        self.assertEqual(context["subject"]["name"], "父亲")
        self.assertEqual(context["agent_conversation_history"][0]["content"], "他喜欢种花")
        self.assertEqual(context["session_chat_history"][0]["content"], "这是他年轻时")
        self.assertEqual(context["assets"][0]["asset_id"], "asset-1")

    def test_mv01_receives_memorial_context_and_chat_history(self):
        sid = session_store.create_session({
            "user_id": "u-1",
            "memorial_id": "m-1",
            "deceased_name": "父亲",
        })
        session_store.require(sid)["chat_history"] = [
            {"role": "user", "content": "父亲最喜欢院子里的桂花树"}
        ]
        context = {
            "session_chat_history": session_store.require(sid)["chat_history"],
            "agent_conversation_history": [{"role": "user", "content": "他喜欢种花"}],
            "assets": [{"asset_id": "asset-yard", "kind": "image"}],
        }
        captured = {}

        def fake_call(_skill, _prompt, payload):
            captured.update(payload)
            return {"interview_status": "completed"}

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(service_manager.material_context, "build_memorial_context", return_value=context), \
             patch.object(service_manager, "load_skill", return_value="prompt"), \
             patch.object(service_manager, "call_skill", side_effect=fake_call), \
             patch.object(service_manager, "OUTPUTS_DIR", Path(temp_dir)):
            result = service_manager.run_pipeline_step(sid, "MV01")

        self.assertTrue(result["ok"])
        self.assertEqual(captured["chat_history"][0]["content"], "父亲最喜欢院子里的桂花树")
        self.assertEqual(captured["assets"][0]["asset_id"], "asset-yard")
        self.assertIs(captured["memorial_context"], context)

    def test_scene_image_reuses_bound_real_photo_before_ai_generation(self):
        sid = session_store.create_session({
            "user_id": "u-1",
            "memorial_id": "m-1",
        })
        session = session_store.require(sid)
        session["mv_outputs"]["MV03"] = {}
        session["mv_outputs"]["MV04"] = {
            "scenes": [{
                "scene_id": "S01",
                "description": "院子里的父亲",
                "source_asset_ids": ["asset-yard"],
            }]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            memorial_dir = Path(temp_dir) / "memorial"
            asset_dir = memorial_dir / "assets"
            asset_dir.mkdir(parents=True)
            (asset_dir / "yard.jpg").write_bytes(b"real-photo-bytes")
            cache_dir = Path(temp_dir) / "cache"

            with patch.object(
                service_manager.core_storage,
                "list_assets",
                return_value=[{
                    "asset_id": "asset-yard",
                    "kind": "image",
                    "stored_name": "yard.jpg",
                    "mime": "image/jpeg",
                }],
            ), patch.object(
                service_manager.core_storage,
                "memorial_dir",
                return_value=memorial_dir,
            ), patch.object(
                service_manager,
                "UPLOADS_DIR",
                cache_dir,
            ), patch.object(
                service_manager,
                "generate_image_tokenstar",
                return_value=("generated-frame", None),
            ) as generate_image:
                result = service_manager.gen_scene_image(
                    sid,
                    0,
                    public_base_url="https://nian.example",
                )

        self.assertFalse(result["reused"])
        self.assertEqual(result["source_asset_id"], "asset-yard")
        self.assertTrue(result["url"].startswith("data:image/png;base64,"))
        generate_image.assert_called_once()
        self.assertEqual(generate_image.call_args.kwargs["reference_b64"], "cmVhbC1waG90by1ieXRlcw==")


if __name__ == "__main__":
    unittest.main()
