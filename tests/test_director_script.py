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

from backend.services import director_script


SCRIPT = """# 念念导演剪辑脚本

项目编号：vp_123456789abc

## 一、导演构思
从父亲在院子里的真实照片开始，以克制的镜头回到家人确认的记忆。

## 二、时间轴剪辑脚本
### 0—5 秒｜开场
- 叙事作用：建立人物与地点。
- 使用素材：院子.jpg（asset_id：a_one）
- 画面与动态化：缓慢推进，不改变人物面貌、服装和背景。
- 旁白：这是父亲在老家院子里的照片。
- 字幕：老家院子
- 原声：无。
- 配乐：待用户确认。
- 转场：交叉淡化。
- 事实依据：用户素材描述。

## 三、声音设计
旁白保持平静，配乐只作低音量铺陈。

## 四、素材取舍说明
使用院子.jpg（a_one），因为它有用户确认的地点和人物信息。

## 五、素材缺口与风险
配乐仍待用户确认。当前没有其他可确认的视觉素材，不虚构补充。
"""


class DirectorScriptTests(unittest.TestCase):
    def test_source_bundle_contains_all_persisted_conversations_and_assets(self):
        conversations = [
            {"role": "user", "content": "第一段真实讲述"},
            {"role": "assistant", "content": "我记住了"},
            {"role": "user", "content": "第二段真实讲述"},
        ]
        assets = [
            {"asset_id": "a_one", "kind": "image", "description": "院子照片"},
            {"asset_id": "a_two", "kind": "audio", "transcript": "采访原声"},
        ]
        with patch.object(director_script.storage, "get_memorial", return_value={"name": "父亲"}), \
             patch.object(director_script.storage, "get_dossier", return_value={"memories": [{"content": "种花"}]}), \
             patch.object(director_script.storage, "read_conversations", return_value=conversations) as read, \
             patch.object(director_script.storage, "list_assets", return_value=assets):
            bundle = director_script._source_bundle("u_one", "m_one", {"aspect_ratio": "16:9"})

        read.assert_called_once_with("u_one", "m_one", limit=1_000_000)
        self.assertEqual(bundle["agent_conversation_history"], conversations)
        self.assertEqual([a["asset_id"] for a in bundle["asset_catalog"]], ["a_one", "a_two"])

    def test_agent_writes_script_instead_of_hardcoded_timeline(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=SCRIPT))]
        )
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return completion

        completions = SimpleNamespace(create=create)
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        bundle = {
            "memorial": {"name": "父亲"},
            "dossier": {},
            "agent_conversation_history": [],
            "asset_catalog": [{"asset_id": "a_one", "kind": "image"}],
        }
        with patch.object(director_script, "evaluate_readiness", return_value={"can_generate_director_script": True}), \
             patch.object(director_script, "_source_bundle", return_value=bundle), \
             patch.object(director_script, "_client", return_value=client), \
             patch.object(director_script.storage, "list_assets", return_value=[{"asset_id": "a_one"}]):
            result = director_script.generate_director_script("u_one", "m_one")

        self.assertEqual(result["script"], SCRIPT.strip())
        self.assertIn("a_one", result["script"])
        self.assertNotIn('"clips"', result["script"])
        prompt = captured["messages"][0]["content"]
        self.assertIn("asset_catalog", prompt)
        self.assertIn("a_one", prompt)
        self.assertIn("自主完成导演判断", prompt)

    def test_validation_rejects_foreign_asset_id(self):
        bad_script = SCRIPT.replace("a_one", "a_from_other_person")
        with patch.object(director_script.storage, "list_assets", return_value=[{"asset_id": "a_one"}]):
            with self.assertRaises(director_script.DirectorScriptError):
                director_script.validate_script("u_one", "m_one", bad_script)

    def test_saved_output_is_markdown_under_current_memorial(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def memorial_dir(user_id, memorial_id):
                return root / user_id / "memorials" / memorial_id

            with patch.object(director_script.storage, "memorial_dir", side_effect=memorial_dir), \
                 patch.object(director_script.storage, "get_memorial", return_value={"memorial_id": "m_one"}), \
                 patch.object(director_script.storage, "list_assets", return_value=[{"asset_id": "a_one"}]), \
                 patch.object(director_script.oss_sync, "push_path"):
                saved = director_script.save_director_script(
                    "u_one", "m_one", "vp_123456789abc", SCRIPT
                )
                path = director_script.director_script_path(
                    "u_one", "m_one", "vp_123456789abc"
                )
                latest = director_script.get_latest_director_script("u_one", "m_one")

            self.assertEqual(saved, SCRIPT.strip())
            self.assertEqual(path.suffix, ".md")
            self.assertEqual(path.parent.parent.parent, root / "u_one" / "memorials" / "m_one")
            self.assertEqual(latest["script"], SCRIPT.strip())


if __name__ == "__main__":
    unittest.main()
