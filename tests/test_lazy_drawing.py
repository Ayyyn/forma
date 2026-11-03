from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from crate_studio import workspace_server as ws


class LazyDrawingTests(unittest.TestCase):
    def document(self):
        return {
            "name": "Lazy drawing control",
            "features": [
                {
                    "id": "box",
                    "type": "box",
                    "params": {"width": 20, "depth": 12, "height": 4},
                }
            ],
        }

    def test_model_snapshot_does_not_compute_or_claim_a_drawing(self):
        with patch.object(
            ws, "projected", side_effect=AssertionError("HLR must stay deferred")
        ):
            result = ws.snapshot(
                self.document(), threading.RLock(), include_drawing=False
            )
        self.assertTrue(result["document_valid"])
        self.assertTrue(result["drawing_pending"])
        self.assertIsNone(result["drawing_svg"])
        self.assertEqual(result["metrics"]["size_mm"], [20, 12, 4])

    def test_lazy_save_and_requested_overview_match_full_native_drawing(self):
        lock = threading.RLock()
        ws._revision_snapshot.cache_clear()
        with (
            tempfile.TemporaryDirectory(dir="output") as tmp,
            patch.object(ws, "DOCS", Path(tmp) / "documents"),
            patch.object(ws, "DATA", Path(tmp)),
        ):
            routes = {r.path: r.endpoint for r in ws.create_router(lock).routes}
            with patch.object(
                ws, "projected", side_effect=AssertionError("Save must not project")
            ):
                saved = routes["/api/studio/documents"](
                    ws.SaveBody(document=self.document(), include_drawing=False)
                )
            self.assertTrue(saved["document_valid"])
            self.assertTrue(saved["drawing_pending"])
            self.assertTrue((ws.DOCS / (saved["id"] + ".json")).is_file())
            overview = routes["/api/studio/drawing/overview"](
                ws.DrawingBody(document=saved["document"], revision_id=saved["id"])
            )
            full = ws.snapshot(saved["document"], lock, {"revision_id": saved["id"]})
            self.assertEqual(overview["svg"], full["drawing_svg"])
            self.assertIn(saved["id"], overview["svg"])
            changed = self.document()
            changed["features"][0]["params"]["width"] = 24
            draft = routes["/api/studio/drawing/overview"](
                ws.DrawingBody(document=changed, revision_id=saved["id"])
            )
            self.assertIn("WORKING DRAFT", draft["svg"])
            self.assertNotIn(saved["id"], draft["svg"])
