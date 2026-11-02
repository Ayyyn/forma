import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cadquery as cq

from crate_studio.workspace_geometry import build_document, export_document


def feature(fid, kind, **params):
    return {"id": fid, "type": kind, "params": params}


class WorkspaceGeometryTests(unittest.TestCase):
    def test_step_translation_is_rejected_even_when_volume_is_identical(self):
        doc = {"features": [feature("plate", "box", width=10, depth=20, height=3)]}
        original_export = cq.exporters.export

        def shifted_export(shape, path, *args, **kwargs):
            if str(path).endswith(".step"):
                shape = shape.translate((12, 0, 0))
            return original_export(shape, path, *args, **kwargs)

        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as folder:
            with patch(
                "crate_studio.workspace_geometry.cq.exporters.export",
                side_effect=shifted_export,
            ):
                result = export_document(doc, None, folder)
        self.assertFalse(result["checks"]["passed"])
        self.assertFalse(result["checks"]["step_roundtrip"]["passed"])
        self.assertAlmostEqual(
            result["checks"]["step_roundtrip"]["bounds_difference_mm"], 12
        )
        self.assertEqual(result["files"], [])

    def test_through_all_hole_survives_thickness_and_z_revisions(self):
        for height, z in [(3, 0), (4, 0), (12, -7), (2, 40)]:
            with self.subTest(height=height, z=z):
                doc = {
                    "features": [
                        feature("plate", "box", width=80, depth=50, height=height, z=z),
                        feature(
                            "hole",
                            "cut_hole",
                            radius=3,
                            x=20,
                            y=10,
                            end_condition="through_all",
                            depth=3,
                            z=0,
                        ),
                    ]
                }
                result = build_document(doc)
                self.assertTrue(result["checks"]["passed"])
                shape = result["parts"][0]["shape"]
                self.assertAlmostEqual(
                    shape.Volume(), (80 * 50 - math.pi * 9) * height, places=6
                )
                for fraction in (0.01, 0.5, 0.99):
                    self.assertFalse(shape.isInside((20, 10, z + height * fraction)))

    def test_legacy_hole_remains_fixed_depth_and_invalid_end_conditions_fail(self):
        doc = {
            "features": [
                feature("plate", "box", width=80, depth=50, height=4),
                feature("hole", "cut_hole", radius=3, depth=3, x=20, y=10),
            ]
        }
        result = build_document(doc)
        self.assertTrue(result["parts"][0]["shape"].isInside((20, 10, 3.5)))
        doc["features"][1]["params"]["end_condition"] = "guess"
        self.assertFalse(build_document(doc)["checks"]["passed"])

    def test_explicit_edge_treatment_and_curve_polylines(self):
        first = feature("box", "box", width=30, depth=20, height=10)
        second = feature(
            "second", "box", width=10, depth=10, height=10, cx=100, operation="new_body"
        )
        initial = build_document({"features": [first, second]})
        edge = next(
            e
            for e in initial["edge_meta"]
            if e["part_id"] == "body_001" and abs(e["end"][2] - e["start"][2]) > 9.9
        )
        self.assertEqual(len(edge["polyline_points"]), 2)
        for kind, amount in [("fillet", {"radius": 2}), ("chamfer", {"distance": 2})]:
            doc = {
                "features": [
                    first,
                    second,
                    feature(
                        "edge-edit",
                        kind,
                        part_id="body_001",
                        edge_indices=[edge["edge_index"]],
                        **amount
                    ),
                ]
            }
            result = build_document(doc)
            self.assertTrue(result["checks"]["passed"], result["features"])
            self.assertLess(result["parts"][0]["shape"].Volume(), 6000)
            self.assertAlmostEqual(result["parts"][1]["shape"].Volume(), 1000)
            self.assertEqual(
                result["metrics"]["bounds_mm"], initial["metrics"]["bounds_mm"]
            )
        curved = build_document(
            {"features": [feature("c", "cylinder", radius=10, height=20)]}
        )
        circles = [e for e in curved["edge_meta"] if e["type"] == "CIRCLE"]
        self.assertTrue(circles)
        self.assertGreater(len(circles[0]["polyline_points"]), 8)
        self.assertEqual(
            circles[0]["polyline_points"][0], circles[0]["polyline_points"][-1]
        )
        self.assertAlmostEqual(circles[0]["length_mm"], 20 * math.pi, places=6)
        for indices in ([True], [999], [edge["edge_index"], edge["edge_index"]], []):
            result = build_document(
                {
                    "features": [
                        first,
                        feature(
                            "bad",
                            "fillet",
                            part_id="body_001",
                            edge_indices=indices,
                            radius=2,
                        ),
                    ]
                }
            )
            self.assertFalse(result["checks"]["passed"])

    def test_imported_filleted_plate_holes_face_offset_regression(self):
        doc = {
            "features": [
                feature("plate", "box", width=140, depth=80, height=10),
                feature("corners", "fillet", radius=4, selector="vertical"),
                feature("left", "cut_hole", radius=8, depth=14, x=-35, y=0, z=-2),
                feature("right", "cut_hole", radius=8, depth=14, x=35, y=0, z=-2),
            ]
        }
        original = build_document(doc)
        self.assertTrue(original["checks"]["passed"])
        expected_area = 140 * 80 - (4 - math.pi) * 4**2 - 2 * math.pi * 8**2
        self.assertAlmostEqual(
            original["metrics"]["volume_mm3"], expected_area * 10, places=5
        )
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as directory:
            source = Path(directory) / "source"
            exported = export_document(doc, None, source)
            self.assertTrue(exported["checks"]["passed"])
            loader = lambda aid: source / "workspace.step"
            imported = feature("import", "import_step", asset_id="plate-step")
            initial = build_document({"features": [imported]}, loader)
            top = next(
                f
                for f in initial["face_meshes"]
                if f["geom_type"] == "PLANE"
                and f["normal"][2] > 0.999
                and abs(f["center"][2] - 10) < 1e-7
            )
            for distance, height in ((2, 12), (-2, 8)):
                edited = {
                    "features": [
                        imported,
                        feature(
                            "push",
                            "face_offset",
                            part_id="body_001",
                            face_index=top["face_index"],
                            distance=distance,
                        ),
                    ]
                }
                result = build_document(edited, loader)
                self.assertTrue(result["checks"]["passed"], result["features"])
                self.assertAlmostEqual(
                    result["metrics"]["volume_mm3"], expected_area * height, places=5
                )
                self.assertAlmostEqual(
                    result["metrics"]["bounds_mm"][1][2], height, places=6
                )
                self.assertEqual(result["metrics"]["solid_count"], 1)
                roundtrip = export_document(
                    edited, loader, Path(directory) / str(height)
                )
                self.assertTrue(roundtrip["checks"]["passed"], roundtrip["checks"])

    def test_planar_face_push_pull_and_curved_rejection(self):
        first = feature("box", "box", width=10, depth=20, height=30)
        initial = build_document({"features": [first]})
        top = next(f for f in initial["face_meshes"] if f["normal"][2] > 0.99)
        for distance, height in ((5, 35), (-2, 28)):
            doc = {
                "features": [
                    first,
                    feature(
                        "offset",
                        "face_offset",
                        part_id="body_001",
                        face_index=top["face_index"],
                        distance=distance,
                    ),
                ]
            }
            result = build_document(doc)
            self.assertTrue(result["checks"]["passed"], result["features"])
            self.assertAlmostEqual(result["metrics"]["volume_mm3"], 10 * 20 * height)
            self.assertAlmostEqual(result["metrics"]["bounds_mm"][1][2], height)
        cylinder = feature("cylinder", "cylinder", radius=10, height=30)
        initial = build_document({"features": [cylinder]})
        curved = next(f for f in initial["face_meshes"] if f["geom_type"] == "CYLINDER")
        result = build_document(
            {
                "features": [
                    cylinder,
                    feature(
                        "offset",
                        "face_offset",
                        part_id="body_001",
                        face_index=curved["face_index"],
                        distance=5,
                    ),
                ]
            }
        )
        self.assertFalse(result["checks"]["passed"])
        self.assertIn("planar", result["features"][-1]["error"])

    def test_imported_step_face_offset_export_roundtrip(self):
        base_dir = Path(__file__).resolve().parents[1] / "output"
        with tempfile.TemporaryDirectory(dir=base_dir) as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "edited"
            export_document(
                {"features": [feature("box", "box", width=10, depth=20, height=30)]},
                None,
                source,
            )
            imported = feature("import", "import_step", asset_id="existing-step")
            loader = lambda aid: source / "workspace.step"
            initial = build_document({"features": [imported]}, loader)
            top = next(f for f in initial["face_meshes"] if f["normal"][2] > 0.99)
            doc = {
                "features": [
                    imported,
                    feature(
                        "push",
                        "face_offset",
                        part_id="body_001",
                        face_index=top["face_index"],
                        distance=5,
                    ),
                ]
            }
            result = export_document(doc, loader, target)
            self.assertTrue(result["checks"]["passed"], result["checks"])
            self.assertAlmostEqual(result["metrics"]["volume_mm3"], 7000)

    def test_missed_cut_tools_fail_without_committing_geometry(self):
        box = feature("base", "box", width=10, depth=10, height=10)
        for cut in [
            feature("cut", "cut_hole", radius=2, depth=10, x=100),
            feature(
                "cut",
                "sketch_extrude",
                shape="rectangle",
                width=2,
                depth=2,
                height=10,
                cx=100,
                operation="cut",
            ),
        ]:
            doc = {
                "features": [
                    box,
                    cut,
                    feature("later", "transform", translation=[10, 0, 0]),
                ]
            }
            result = build_document(doc)
            self.assertFalse(result["checks"]["passed"])
            self.assertIn("NoIntersection", result["features"][1]["error"])
            self.assertEqual(result["features"][2]["status"], "blocked")
            self.assertAlmostEqual(result["metrics"]["volume_mm3"], 1000)
            self.assertAlmostEqual(result["parts"][0]["shape"].Center().x, 0)
        doc = {
            "features": [
                box,
                feature(
                    "tool",
                    "box",
                    width=2,
                    depth=2,
                    height=10,
                    cx=100,
                    operation="new_body",
                ),
                feature("cut", "boolean_cut", target=0, tool=1),
            ]
        }
        result = build_document(doc)
        self.assertFalse(result["checks"]["passed"])
        self.assertIn("NoIntersection", result["features"][-1]["error"])
        self.assertEqual(result["metrics"]["solid_count"], 2)
        self.assertAlmostEqual(result["metrics"]["volume_mm3"], 1040)

    def test_hole_edit_suppress_and_topology(self):
        box = feature("base", "box", width=100, depth=80, height=40)
        hole = feature("bore", "cut_hole", radius=10, depth=40)
        doc = {"features": [box, hole]}
        r = build_document(doc)
        self.assertTrue(r["checks"]["passed"])
        self.assertAlmostEqual(
            r["metrics"]["volume_mm3"], 320000 - math.pi * 100 * 40, places=5
        )
        self.assertEqual(
            [f["id"] for f in r["face_meshes"]],
            [f["id"] for f in build_document(doc)["face_meshes"]],
        )
        self.assertTrue(all(len(f["vertices"]) > 0 for f in r["face_meshes"]))
        hole["suppressed"] = True
        self.assertAlmostEqual(build_document(doc)["metrics"]["volume_mm3"], 320000)
        hole["suppressed"] = False
        hole["params"]["radius"] = 5
        self.assertAlmostEqual(
            build_document(doc)["metrics"]["volume_mm3"],
            320000 - math.pi * 25 * 40,
            places=5,
        )

    def test_fillet_chamfer_and_structured_failure(self):
        for kind, amount in [("fillet", {"radius": 3}), ("chamfer", {"distance": 3})]:
            doc = {
                "features": [
                    feature("b", "box", width=100, depth=80, height=40),
                    feature("f", kind, selector="vertical", **amount),
                ]
            }
            r = build_document(doc)
            self.assertTrue(r["checks"]["passed"], r["features"])
            self.assertLess(r["metrics"]["volume_mm3"], 320000)
        doc = {
            "features": [
                feature("b", "box", width=100, depth=80, height=40),
                feature("f", "fillet", radius=1000),
                feature("later", "transform"),
            ]
        }
        r = build_document(doc)
        self.assertFalse(r["checks"]["passed"])
        self.assertEqual(r["features"][1]["status"], "error")
        self.assertEqual(r["features"][2]["status"], "blocked")

    def test_polyline_pattern_transform_mirror(self):
        doc = {
            "features": [
                feature(
                    "p",
                    "sketch_extrude",
                    shape="polyline",
                    points=[[0, 0], [10, 0], [10, 20], [0, 20]],
                    height=5,
                ),
                feature("repeat", "linear_pattern", count=3, spacing=[30, 0, 0]),
                feature(
                    "move",
                    "transform",
                    translation=[0, 0, 10],
                    target_part_id="body_002",
                ),
                feature("mirror", "mirror", plane="YZ", keep_original=False),
            ]
        }
        r = build_document(doc)
        self.assertTrue(r["checks"]["passed"], r["features"])
        self.assertEqual(r["metrics"]["solid_count"], 3)
        self.assertAlmostEqual(r["metrics"]["volume_mm3"], 3000)
        self.assertAlmostEqual(r["parts"][1]["shape"].Center().z, 12.5)

    def test_step_import_and_export_roundtrip(self):
        base = Path(__file__).resolve().parents[1] / "output"
        with tempfile.TemporaryDirectory(dir=base) as folder:
            doc = {
                "features": [
                    feature("b", "cylinder", radius=10, height=30),
                    feature("repeat", "linear_pattern", count=2, spacing=[30, 0, 0]),
                ]
            }
            result = export_document(doc, None, folder)
            self.assertTrue(result["checks"]["passed"], result["checks"])
            loaded = build_document(
                {"features": [feature("import", "import_step", asset_id="safe-asset")]},
                lambda aid: Path(folder) / "workspace.step",
            )
            self.assertTrue(loaded["checks"]["passed"])
            self.assertEqual(loaded["metrics"]["solid_count"], 2)

    def test_strict_values_and_limits(self):
        for value in (True, float("nan"), float("inf"), -1):
            r = build_document(
                {"features": [feature("b", "box", width=value, depth=10, height=10)]}
            )
            self.assertFalse(r["checks"]["passed"])
        r = build_document(
            {
                "features": [
                    feature(str(i), "box", width=1, depth=1, height=1)
                    for i in range(61)
                ]
            }
        )
        self.assertFalse(r["checks"]["passed"])

    def test_sequential_planar_mate(self):
        first = feature("b", "box", width=10, depth=10, height=10)
        second = feature(
            "c", "box", width=10, depth=10, height=10, cx=30, operation="new_body"
        )
        doc = {"features": [first, second]}
        r = build_document(doc)
        source = next(
            f
            for f in r["face_meshes"]
            if f["part_id"] == "body_002" and f["normal"][2] < -0.99
        )
        target = next(
            f
            for f in r["face_meshes"]
            if f["part_id"] == "body_001" and f["normal"][2] > 0.99
        )
        doc["features"].append(
            feature(
                "mate",
                "mate",
                source_part_id="body_002",
                source_face=source["face_index"],
                target_part_id="body_001",
                target_face=target["face_index"],
                offset=2,
            )
        )
        aligned = build_document(doc)
        self.assertTrue(aligned["checks"]["passed"], aligned["features"])
        self.assertAlmostEqual(aligned["parts"][1]["shape"].Center().x, 0)
        self.assertAlmostEqual(aligned["parts"][1]["shape"].Center().z, 17)
        r = build_document(
            {
                "features": [
                    feature("b", "box", width=1, depth=1, height=1),
                    feature("p", "linear_pattern", count=51, spacing=[2, 0, 0]),
                ]
            }
        )
        self.assertFalse(r["checks"]["passed"])


if __name__ == "__main__":
    unittest.main()
