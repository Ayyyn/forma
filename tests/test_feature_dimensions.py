from copy import deepcopy
from pathlib import Path
import math
import tempfile
import threading
import unittest
from unittest.mock import patch

from crate_studio.feature_dimensions import edit_dimension
from crate_studio.workspace_cache import cached_build
from crate_studio import workspace_server as ws
from tests.test_workspace_geometry import feature


class FeatureDimensionsTests(unittest.TestCase):
    def test_cylinder_and_polyline_dimensions_edit_actual_radius_and_extrusion(self):
        doc = {
            "features": [
                feature("tube", "cylinder", radius=8, height=22, operation="new_body"),
                feature(
                    "profile",
                    "sketch_extrude",
                    shape="polyline",
                    points=[[30, 0], [50, 0], [40, 15]],
                    height=4,
                    operation="new_body",
                ),
            ]
        }
        result = cached_build(doc)
        dims = {d["id"]: d for d in result["feature_dimensions"]}
        self.assertEqual(dims["tube:radius"]["value_mm"], 16)
        self.assertEqual(dims["profile:height"]["value_mm"], 4)
        edited, _ = edit_dimension(doc, list(dims.values()), "tube:radius", 20)
        changed = cached_build(edited)
        self.assertAlmostEqual(
            changed["parts"][0]["shape"].Volume(), math.pi * 100 * 22, places=6
        )
        self.assertEqual(edited["features"][1], doc["features"][1])

    def fixture(self):
        return {
            "features": [
                feature(
                    "plate", "box", width=50, depth=35, height=10, operation="new_body"
                ),
                feature(
                    "block",
                    "box",
                    width=12,
                    depth=12,
                    height=12,
                    cx=55,
                    operation="new_body",
                ),
                feature(
                    "pose", "transform", rotation=[0, 0, 90], translation=[28, -18, 0]
                ),
                feature(
                    "hole",
                    "cut_hole",
                    radius=2,
                    x=28,
                    y=-18,
                    z=10,
                    direction=[0, 0, -1],
                    end_condition="through_all",
                    target_part_id="body_001",
                ),
            ]
        }

    def test_rotated_feature_dimensions_follow_source_axes_not_global_envelope(self):
        doc = self.fixture()
        result = cached_build(doc)
        dims = {d["id"]: d for d in result["feature_dimensions"]}
        width = dims["plate:width"]
        self.assertEqual(width["part_id"], "body_001")
        self.assertAlmostEqual(math.dist(width["fromA"], width["fromB"]), 50)
        self.assertAlmostEqual(width["fromA"][0], width["fromB"][0])
        self.assertAlmostEqual(width["value_mm"], 50)
        self.assertEqual(dims["hole:radius"]["value_mm"], 4)
        self.assertAlmostEqual(
            math.dist(dims["hole:radius"]["a"], dims["hole:radius"]["b"]), 4
        )

    def test_exact_single_parameter_height_and_diameter_edits(self):
        doc = self.fixture()
        result = cached_build(doc)
        updated, row = edit_dimension(
            doc, result["feature_dimensions"], "plate:height", 11
        )
        expected = deepcopy(doc)
        expected["features"][0]["params"]["height"] = 11
        self.assertEqual(updated, expected)
        newer = cached_build(updated)
        self.assertTrue(newer["checks"]["passed"])
        self.assertAlmostEqual(
            newer["metrics"]["volume_mm3"] - result["metrics"]["volume_mm3"],
            50 * 35 - math.pi * 4,
            places=6,
        )
        hole, _ = edit_dimension(doc, result["feature_dimensions"], "hole:radius", 6)
        self.assertEqual(hole["features"][-1]["params"]["radius"], 3)
        self.assertEqual(doc["features"][-1]["params"]["radius"], 2)
        self.assertAlmostEqual(
            result["metrics"]["volume_mm3"]
            - cached_build(hole)["metrics"]["volume_mm3"],
            math.pi * 5 * 10,
            places=6,
        )

    def test_ambiguous_merge_discards_bindings_and_suppression_is_not_editable(self):
        doc = self.fixture()
        doc["features"].append(feature("union", "union"))
        result = cached_build(doc)
        self.assertFalse(result["feature_dimensions"])
        with self.assertRaises(ValueError):
            edit_dimension(doc, [], "plate:height", 11)
        doc = self.fixture()
        doc["features"][1]["suppressed"] = True
        dims = cached_build(doc)["feature_dimensions"]
        self.assertFalse(any(d["feature_id"] == "block" for d in dims))

    def test_targeted_pose_changes_only_bound_component_anchors(self):
        doc = self.fixture()
        first = cached_build(doc)["feature_dimensions"]
        doc["features"].append(
            feature(
                "move", "transform", target_part_id="body_002", translation=[7, 3, 2]
            )
        )
        after = cached_build(doc)["feature_dimensions"]
        for a, b in zip(first, after):
            if a["part_id"] == "body_001":
                self.assertEqual(a, b)
            else:
                for k in ("a", "b", "fromA", "fromB"):
                    for x, y, t in zip(a[k], b[k], [7, 3, 2]):
                        self.assertAlmostEqual(y - x, t)

    def test_nonfinite_negative_and_unknown_dimensions_rejected(self):
        doc = self.fixture()
        dims = cached_build(doc)["feature_dimensions"]
        for value in [float("nan"), float("inf"), -1, 0, True, 1e7]:
            with self.assertRaises(ValueError):
                edit_dimension(doc, dims, "plate:height", value)
        with self.assertRaises(ValueError):
            edit_dimension(doc, dims, "fake:width", 1)

    def test_route_revision_binding_undo_and_failed_regeneration(self):
        lock = threading.RLock()
        with (
            tempfile.TemporaryDirectory(dir="output") as tmp,
            patch.object(ws, "DOCS", Path(tmp) / "documents"),
            patch.object(ws, "DATA", Path(tmp)),
        ):
            routes = {r.path: r.endpoint for r in ws.create_router(lock).routes}
            saved = ws.save_document(self.fixture(), lock, include_drawing=False)
            endpoint = routes["/api/studio/dimensions/edit"]
            body = endpoint.__annotations__["body"]
            edited = endpoint(
                body(document_id=saved["id"], dimension_id="plate:height", value_mm=11)
            )
            self.assertEqual(edited["parent_id"], saved["id"])
            self.assertEqual(edited["document"]["features"][0]["params"]["height"], 11)
            doc = {
                "features": [
                    feature("plate", "box", width=30, depth=20, height=10),
                    feature(
                        "hole",
                        "cut_hole",
                        radius=2,
                        x=0,
                        y=0,
                        z=8,
                        depth=4,
                        end_condition="blind",
                        direction=[0, 0, 1],
                    ),
                ]
            }
            source = ws.save_document(doc, lock, include_drawing=False)
            before = set(ws.DOCS.glob("*.json"))
            with self.assertRaises(ValueError):
                endpoint(
                    body(
                        document_id=source["id"],
                        dimension_id="plate:height",
                        value_mm=5,
                    )
                )
            self.assertEqual(before, set(ws.DOCS.glob("*.json")))
            self.assertEqual(
                ws.read_document(source["id"], lock, include_drawing=False)["document"],
                source["document"],
            )


if __name__ == "__main__":
    unittest.main()
