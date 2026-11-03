import json
import math
from pathlib import Path
import tempfile
import unittest
import io
from xml.etree import ElementTree as ET

import cadquery as cq
import ezdxf
from pypdf import PdfReader

from crate_studio.workspace_drawing import (
    _scene,
    PDF_POINTS_PER_UNIT,
    drawing_data,
    drawing_svg,
    export_drawings,
    validate_annotations,
)


class WorkspaceDrawingTests(unittest.TestCase):
    def document(self):
        return {
            "name": "Plate <review> & notes",
            "features": [{"type": "box", "width": 999}],
            "display": {},
            "annotations": [
                {
                    "id": "note",
                    "type": "text",
                    "view": "sheet",
                    "x": 60,
                    "y": 630,
                    "text": 'Check <hole> & finish "A"',
                },
                {
                    "id": "dim",
                    "type": "dimension",
                    "view": "front",
                    "x": 70,
                    "y": 600,
                    "x2": 240,
                    "y2": 600,
                    "value_mm": 999,
                    "text": "User estimate",
                },
                {
                    "id": "line",
                    "type": "line",
                    "view": "top",
                    "x": 460,
                    "y": 610,
                    "x2": 650,
                    "y2": 610,
                    "color": "#8a352a",
                },
            ],
        }

    def parts(self):
        return [
            {
                "id": "plate",
                "shape": cq.Workplane("XY")
                .box(100, 60, 40)
                .faces(">Z")
                .workplane()
                .hole(12)
                .val(),
            }
        ]

    def test_bounds_dimensions_come_from_brep_not_document_or_notes(self):
        data = drawing_data(self.document(), self.parts())
        self.assertEqual(data["bbox_mm"]["size"], [100, 60, 40])
        self.assertEqual(
            (data["views"]["front"]["width_mm"], data["views"]["front"]["height_mm"]),
            (100, 40),
        )
        self.assertEqual(
            (data["views"]["top"]["width_mm"], data["views"]["top"]["height_mm"]),
            (100, 60),
        )
        self.assertEqual(
            (data["views"]["right"]["width_mm"], data["views"]["right"]["height_mm"]),
            (60, 40),
        )
        svg = drawing_svg(self.document(), self.parts())
        self.assertIn("999 mm REF", svg)
        self.assertIn("Overall width: 100 mm", svg)
        self.assertNotIn("Overall width: 999", svg)

    def test_projection_includes_hole_curves_and_hidden_geometry(self):
        data = drawing_data(self.document(), self.parts())
        self.assertTrue(
            any(len(points) > 8 for points in data["views"]["top"]["visible"])
        )
        self.assertGreater(len(data["views"]["front"]["hidden"]), 0)
        for view in data["views"].values():
            xmin, ymin, xmax, ymax = view["bounds_mm"]
            for path in view["visible"] + view["hidden"]:
                for x, y in path:
                    self.assertTrue(math.isfinite(x) and math.isfinite(y))
                    self.assertTrue(xmin - 1e-6 <= x <= xmax + 1e-6)
                    self.assertTrue(ymin - 1e-6 <= y <= ymax + 1e-6)

    def test_translated_nonrectangular_solid_has_real_extents(self):
        shape = cq.Workplane("XY").cylinder(32, 17).translate((100, -55, 80)).val()
        data = drawing_data({"name": "Cylinder", "annotations": []}, [{"shape": shape}])
        self.assertEqual(data["bbox_mm"]["size"], [34, 34, 32])
        self.assertAlmostEqual(data["views"]["top"]["bounds_mm"][0], 83)

    def test_display_tessellation_cannot_inflate_drawing_dimensions(self):
        shape = (
            cq.Workplane("XY")
            .box(150, 80, 10)
            .edges("|Z")
            .fillet(4)
            .faces(">Z")
            .workplane()
            .pushPoints([(-35, 0), (35, 0)])
            .hole(16)
            .val()
        )
        shape.tessellate(0.15, 0.1)
        data = drawing_data(
            {"name": "Meshed filleted plate", "annotations": []}, [{"shape": shape}]
        )
        for got, want in zip(data["bbox_mm"]["size"], [150, 80, 10]):
            self.assertAlmostEqual(got, want, places=6)
        self.assertIn(
            "Overall width: 150 mm", drawing_svg({"name": "Plate"}, [{"shape": shape}])
        )

    def test_xml_text_is_escaped_and_source_is_not_mutated(self):
        doc = self.document()
        before = json.dumps(doc, sort_keys=True)
        svg = drawing_svg(doc, self.parts())
        root = ET.fromstring(svg)
        text = " ".join(root.itertext())
        self.assertIn('Check <hole> & finish "A"', text)
        self.assertIn("Plate <review> & notes", text)
        self.assertEqual(json.dumps(doc, sort_keys=True), before)
        self.assertIn('stroke-dasharray="5 4"', svg)

    def test_invalid_annotations_rejected(self):
        for changes in (
            {"x": float("nan")},
            {"color": 'red" onload="bad'},
            {"type": "script"},
            {"view": "invalid"},
            {"value_mm": -1},
        ):
            doc = self.document()
            doc["annotations"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_annotations(doc)
        doc = self.document()
        doc["annotations"].append(doc["annotations"][0])
        with self.assertRaises(ValueError):
            validate_annotations(doc)

    def test_exports_reopen_and_retain_editable_source(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as directory:
            folder = Path(directory)
            doc = self.document()
            manifest = export_drawings(doc, self.parts(), folder)
            for name in manifest["files"]:
                self.assertTrue((folder / name).is_file())
            self.assertEqual(
                json.loads(
                    (folder / "drawing-source.json").read_text(encoding="utf-8")
                ),
                doc,
            )
            ET.fromstring((folder / "drawing.svg").read_text(encoding="utf-8"))
            pdf = (folder / "drawing.pdf").read_bytes()
            self.assertTrue(pdf.startswith(b"%PDF-1.4"))
            parsed = PdfReader(io.BytesIO(pdf))
            # ReportLab serializes PDF numbers to finite decimal precision;
            # bound physical sheet error to one micron, below curve resolution.
            self.assertAlmostEqual(
                float(parsed.pages[0].mediabox.width) * 25.4 / 72, 420, delta=0.001
            )
            self.assertAlmostEqual(
                float(parsed.pages[0].mediabox.height) * 25.4 / 72, 297, delta=0.001
            )
            self.assertIn("999 mm REF", parsed.pages[0].extract_text())
            dxf = ezdxf.readfile(folder / "drawing.dxf")
            self.assertEqual(dxf.units, 4)
            model = dxf.modelspace()
            self.assertEqual(len(list(model.query("DIMENSION"))), 6)
            self.assertTrue(any("REF" in e.dxf.text for e in model.query("TEXT")))
            front = list(model.query('LWPOLYLINE[layer=="FRONT_VISIBLE"]'))
            points = [p for line in front for p in line.get_points()]
            self.assertAlmostEqual(
                max(p[0] for p in points) - min(p[0] for p in points), 100, places=6
            )
            self.assertAlmostEqual(
                max(p[1] for p in points) - min(p[1] for p in points), 40, places=6
            )
            self.assertFalse(dxf.audit().has_errors)

    def test_thin_part_views_share_print_scale_and_measured_dimension_bars(self):
        shape = cq.Workplane("XY").box(76.2, 31, 3).val()
        data = drawing_data({"name": "Thin print"}, [{"shape": shape}])
        scales = {v["scale_px_per_mm"] for v in data["views"].values()}
        self.assertEqual(len(scales), 1)
        self.assertEqual(data["sheet"]["scale_label"], "1:1")
        dimensions = [i for i in _scene(data) if i.get("role") == "native-dimension"]
        self.assertEqual(len(dimensions), 6)
        for dimension in dimensions:
            a, b = dimension["points"]
            paper_mm = math.dist(a, b) * PDF_POINTS_PER_UNIT * 25.4 / 72
            self.assertAlmostEqual(paper_mm, dimension["value_mm"], places=8)

    def test_pdf_retains_engineering_symbols_source_parameters_and_is_repeatable(self):
        doc = self.document()
        doc["name"] = "Crème Ø6 ±0.1 × 2 · Δ µ"
        doc["features"] = [
            {
                "id": "bore",
                "type": "cut_hole",
                "params": {
                    "radius": 3,
                    "depth": 3,
                    "z": 0,
                    "end_condition": "through_all",
                },
            }
        ]
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as temp:
            folder = Path(temp)
            export_drawings(doc, self.parts(), folder)
            pdf = (folder / "drawing.pdf").read_bytes()
            reader = PdfReader(io.BytesIO(pdf))
            self.assertIn(doc["name"], reader.pages[0].extract_text())
            text = "\n".join(page.extract_text() for page in reader.pages[1:])
            self.assertIn("radius", text)
            self.assertIn("inactive (through all)", text)
            export_drawings(doc, self.parts(), folder)
            self.assertEqual(pdf, (folder / "drawing.pdf").read_bytes())

    def test_right_view_preserves_depth_direction_for_asymmetric_part(self):
        # A distinct upright at the back (+Y) must appear on the right of the
        # right-side view, and at the top in plan; this catches reflected axes.
        base = cq.Workplane("XY").box(80, 40, 3, centered=(True, True, False))
        shape = base.union(
            cq.Workplane("XY")
            .box(8, 5, 9, centered=(True, True, False))
            .translate((20, 17.5, 3))
        ).val()
        data = drawing_data({"name": "Direction witness"}, [{"shape": shape}])
        right = data["views"]["right"]
        high = [p for line in right["visible"] for p in line if p[1] > 11.9]
        self.assertTrue(high)
        self.assertTrue(all(p[0] >= 15 - 1e-6 for p in high))
        top = data["views"]["top"]
        self.assertTrue(
            any(
                abs(x - 16) < 1e-6 and abs(y - 15) < 1e-6
                for line in top["visible"]
                for x, y in line
            )
        )


if __name__ == "__main__":
    unittest.main()
