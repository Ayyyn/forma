import tempfile
import unittest
from pathlib import Path
import math
import threading
from unittest.mock import patch
from pypdf import PdfReader
from shapely.geometry import Point
import cadquery as cq

from crate_studio.drawing_sections import section_data, specifications
from crate_studio.workspace_drawing import drawing_data, export_drawings


class SectionTests(unittest.TestCase):
    def test_saved_revision_and_edited_plane_do_not_share_a_false_revision_label(self):
        from crate_studio import workspace_server as ws
        from copy import deepcopy

        doc = {
            "name": "Plane revision",
            "features": [
                {
                    "id": "plate",
                    "type": "box",
                    "params": {"width": 20, "depth": 12, "height": 4},
                }
            ],
            "metadata": {
                "drawing_sections": [{"name": "Cut", "axis": "Z", "offset_mm": 2}]
            },
        }
        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(ws, "DATA", Path(folder)),
            patch.object(ws, "DOCS", Path(folder) / "documents"),
        ):
            routes = {
                r.path: r.endpoint for r in ws.create_router(threading.RLock()).routes
            }
            saved = ws.save_document(doc, threading.RLock())
            view = routes["/api/studio/drawing/section"]
            original = view(
                ws.SectionBody(
                    document=saved["document"], revision_id=saved["id"], section_index=0
                )
            )
            self.assertIn(saved["id"], original["svg"])
            changed = deepcopy(saved["document"])
            changed["metadata"]["drawing_sections"][0]["offset_mm"] = 1
            self.assertNotEqual(
                ws.drawing_key(changed), ws.drawing_key(saved["document"])
            )
            draft = view(
                ws.SectionBody(
                    document=changed, revision_id=saved["id"], section_index=0
                )
            )
            self.assertNotIn(saved["id"], draft["svg"])
            self.assertIn("WORKING DRAFT", draft["svg"])
            self.assertEqual(draft["measurements"]["plane"]["offset_mm"], 1)

    def parts(self):
        solid = (
            cq.Workplane("XY")
            .box(20, 12, 4, centered=(True, True, False))
            .faces(">Z")
            .workplane()
            .hole(4)
            .val()
        )
        return [{"id": "body_001", "shape": solid}]

    def test_native_bore_void_is_not_hatched_and_extents_are_exact(self):
        result = section_data(
            self.parts(), {"name": "Bore", "axis": "Z", "offset_mm": 2}
        )
        self.assertEqual(result["size_mm"], [20, 12])
        self.assertTrue(result["regions"])
        self.assertFalse(
            any(row["polygon"].contains(Point(0, 0)) for row in result["regions"])
        )
        self.assertAlmostEqual(
            sum(row["polygon"].area for row in result["regions"]),
            240 - math.pi * 4,
            delta=0.4,
        )
        with self.assertRaisesRegex(ValueError, "No closed material"):
            section_data(self.parts(), {"name": "Outside", "axis": "Z", "offset_mm": 9})

    def test_pdf_section_identity_scale_and_source_plane_survive_export(self):
        doc = {
            "name": "Section control",
            "features": [],
            "annotations": [],
            "metadata": {
                "drawing_sections": [{"name": "Bore", "axis": "Z", "offset_mm": 2}]
            },
        }
        data = drawing_data(doc, self.parts(), {"revision_id": "cad-section-control"})
        self.assertEqual(len(data["section_pages"]), 1)
        self.assertEqual(data["section_pages"][0]["measurements"]["tag"], "A-A")
        from crate_studio.workspace_drawing import section_page
        from unittest.mock import patch

        with patch(
            "crate_studio.workspace_drawing._project",
            side_effect=AssertionError("Unrelated HLR must not run"),
        ):
            fast = section_page(
                doc, self.parts(), 0, {"revision_id": "cad-section-control"}
            )
        self.assertEqual(fast, data["section_pages"][0])
        self.assertTrue(
            any(
                item.get("role") == "cutting-plane"
                for item in __import__(
                    "crate_studio.workspace_drawing", fromlist=["_scene"]
                )._scene(data)
            )
        )
        with tempfile.TemporaryDirectory(dir="output") as folder:
            result = export_drawings(
                doc,
                self.parts(),
                Path(folder),
                context={"revision_id": "cad-section-control"},
            )
            pdf = PdfReader(Path(folder) / "drawing.pdf")
            self.assertEqual(len(pdf.pages), 2)
            text = pdf.pages[1].extract_text()
            self.assertIn("SECTION A-A / Bore", text)
            self.assertIn("cad-section-control", text)
            self.assertIn("2 / 2", text)
            self.assertEqual(
                result["measurements"]["section_pages"][0]["size_mm"], [20, 12]
            )
            import ezdxf
            from ezdxf import bbox

            model = ezdxf.readfile(Path(folder) / "drawing.dxf").modelspace()
            contours = model.query('LWPOLYLINE[layer=="SECTION_1_CONTOUR"]')
            extents = bbox.extents(contours)
            self.assertAlmostEqual(extents.size.x, 20, places=6)
            self.assertAlmostEqual(extents.size.y, 12, places=6)
            self.assertTrue(model.query('LWPOLYLINE[layer=="SECTION_1_HATCH"]'))
            self.assertIn("section-1.svg", result["files"])

    def test_bad_and_missing_body_references_fail_explicitly(self):
        for row in (
            {"name": "A", "axis": "U", "offset_mm": 1},
            {"name": "A", "axis": "Z", "offset_mm": True},
            {"name": "A", "axis": "Z", "offset_mm": 1, "part_ids": [{}]},
        ):
            with self.assertRaises(ValueError):
                specifications([row])
        with self.assertRaisesRegex(ValueError, "missing body"):
            section_data(
                self.parts(),
                {"name": "A", "axis": "Z", "offset_mm": 1, "part_ids": ["body_002"]},
            )


if __name__ == "__main__":
    unittest.main()
