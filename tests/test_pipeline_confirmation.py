import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import service_manager


class PipelineConfirmationTests(unittest.TestCase):
    def test_completed_plan_has_one_summary_with_story_context(self):
        session = {"form_data": {"deceased_name": "Test Person"}, "mv_outputs": {
            "MV01": {"story": "memories"}, "MV02": {"ok": True}, "MV03": {"tone": "warm"}}}
        with patch.object(service_manager.session_store, "require", return_value=session), \
                patch.object(service_manager, "_safe_mv_summary", return_value="Final plan") as summary:
            for attempt in range(2):
                result = service_manager.run_pipeline_chain("session")
                self.assertTrue(result["ok"])
                self.assertEqual(result["bubbles"], [{"role": "ai", "content": "Final plan"}])
            self.assertEqual(summary.call_count, 2)
            self.assertEqual(summary.call_args.args[1]["story_context"], session["mv_outputs"]["MV01"])

    def test_failed_plan_does_not_emit_intermediate_summary(self):
        session = {"form_data": {}, "mv_outputs": {"MV01": {"story": "memories"}, "MV02": {"ok": True}}}
        with patch.object(service_manager.session_store, "require", return_value=session), \
                patch.object(service_manager, "run_pipeline_step", return_value={"error": True, "message": "failed"}), \
                patch.object(service_manager, "_safe_mv_summary") as summary:
            result = service_manager.run_pipeline_chain("session")
        self.assertFalse(result["ok"])
        self.assertEqual(result["bubbles"], [])
        summary.assert_not_called()


if __name__ == "__main__":
    unittest.main()