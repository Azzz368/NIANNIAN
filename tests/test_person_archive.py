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

from backend.core import storage
from backend.routers import agent as agent_router
from backend.routers import agent_realtime


class PersonArchiveIsolationTests(unittest.TestCase):
    def test_conversations_are_stored_under_the_selected_person_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def scoped_dir(user_id, memorial_id):
                return root / user_id / "memorials" / memorial_id

            with patch.object(storage, "memorial_dir", side_effect=scoped_dir):
                storage.append_conversation(
                    "user-1",
                    "person-a",
                    [{"role": "user", "content": "只属于人物 A"}],
                )
                storage.append_conversation(
                    "user-1",
                    "person-b",
                    [{"role": "user", "content": "只属于人物 B"}],
                )

                person_a = storage.read_conversations("user-1", "person-a")
                person_b = storage.read_conversations("user-1", "person-b")

        self.assertEqual([item["content"] for item in person_a], ["只属于人物 A"])
        self.assertEqual([item["content"] for item in person_b], ["只属于人物 B"])

    def test_realtime_archive_does_not_append_the_last_turn_twice(self):
        turns = [
            {"role": "user", "content": "人物 A 的故事"},
            {"role": "assistant", "content": "我记住了"},
        ]
        with patch.object(agent_realtime.storage, "append_conversation") as append, \
             patch.object(agent_router, "_persist_and_extract") as extract, \
             patch.object(agent_realtime.memory_mod, "maybe_refresh"):
            agent_realtime._persist_realtime_turns("user-1", "person-a", turns)

        append.assert_called_once_with("user-1", "person-a", turns)
        extract.assert_called_once_with(
            "user-1",
            "person-a",
            "人物 A 的故事",
            "我记住了",
            append_turns=False,
        )


if __name__ == "__main__":
    unittest.main()
