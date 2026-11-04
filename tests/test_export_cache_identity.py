import tempfile
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import cadquery as cq
from crate_studio import workspace_server as ws


class ExportCacheIdentityTests(unittest.TestCase):
    def test_geometry_export_does_not_implicitly_run_a_mechanism_study(self):
        from tests.test_mechanism_study import document, specification

        doc = document()
        doc["metadata"] = {"design_mechanism": specification(10)}
        lock = threading.RLock()
        with (
            tempfile.TemporaryDirectory(dir="output") as tmp,
            patch.object(ws, "DATA", Path(tmp)),
            patch.object(ws, "DOCS", Path(tmp) / "documents"),
            patch.object(
                ws,
                "motion_study",
                side_effect=AssertionError(
                    "Export must not start an unsolicited motion study"
                ),
            ),
        ):
            saved = ws.save_document(doc, lock, include_drawing=False)
            endpoint = next(
                r.endpoint
                for r in ws.create_router(lock).routes
                if r.path == "/api/studio/documents/{id}/export/{format}"
            )
            exported = endpoint(saved["id"], "step")
            folder = Path(exported.path).parent
            report = json.loads(
                (folder / "workflow-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["motion"]["status"], "not_rechecked_at_export")
            self.assertEqual(report["motion"]["declared_spec"], specification(10))
            self.assertEqual(report["geometry_signature"], saved["geometry_signature"])
            self.assertTrue(
                json.loads((folder / "verification.json").read_text())[
                    "step_roundtrip"
                ]["passed"]
            )
            self.assertTrue(
                json.loads((folder / "verification.json").read_text())["stl_roundtrip"][
                    "passed"
                ]
            )

    def test_actual_replaced_asset_invalidates_files_and_preserves_prior_export(self):
        lock = threading.RLock()
        with (
            tempfile.TemporaryDirectory(dir="output") as tmp,
            patch.object(ws, "DATA", Path(tmp)),
            patch.object(ws, "DOCS", Path(tmp) / "documents"),
        ):
            asset = Path(tmp) / "asset.step"
            cq.exporters.export(cq.Workplane("XY").box(8, 4, 2), str(asset))
            doc = {
                "name": "Export identity control",
                "features": [
                    {
                        "id": "import",
                        "type": "import_step",
                        "params": {"asset_id": "c" * 64},
                    }
                ],
            }
            with (
                patch.object(ws, "asset_path", return_value=asset),
                patch.object(ws, "export_document", wraps=ws.export_document) as native,
            ):
                saved = ws.save_document(doc, lock, include_drawing=False)
                endpoint = next(
                    r.endpoint
                    for r in ws.create_router(lock).routes
                    if r.path == "/api/studio/documents/{id}/export/{format}"
                )
                first = endpoint(saved["id"], "step")
                cq.exporters.export(cq.Workplane("XY").box(12, 4, 2), str(asset))
                second = endpoint(saved["id"], "step")
                again = endpoint(saved["id"], "step")
                self.assertNotEqual(Path(first.path).parent, Path(second.path).parent)
                self.assertEqual(second.path, again.path)
                self.assertEqual(native.call_count, 2)
                for response, width in [(first, 8), (second, 12)]:
                    shape = cq.importers.importStep(str(response.path)).val()
                    self.assertAlmostEqual(shape.BoundingBox().xlen, width, places=6)
