import math
import unittest
from crate_studio.viewport_measurements import body_measurements
from crate_studio.workspace_cache import cached_build
from crate_studio.workspace_server import snapshot, normalize_document
from tests.test_workspace_geometry import feature
import threading
from unittest.mock import patch


class ViewportMeasuresTests(unittest.TestCase):
    def test_warm_snapshot_reuses_plain_measures_without_native_queries(self):
        doc = normalize_document(
            {"features": [feature("part", "box", width=23, depth=17, height=6)]}
        )
        first = snapshot(doc, threading.RLock(), include_drawing=False)
        with patch(
            "crate_studio.workspace_cache.body_measurements",
            side_effect=AssertionError("native query on warm hit"),
        ):
            warm = snapshot(doc, threading.RLock(), include_drawing=False)
        self.assertEqual(first["body_measurements"], warm["body_measurements"])
        warm["body_measurements"][0]["size_mm"][0] = -1
        again = snapshot(doc, threading.RLock(), include_drawing=False)
        self.assertEqual(again["body_measurements"][0]["size_mm"], [23, 17, 6])

    def test_native_envelopes_hole_diameters_and_separate_components(self):
        doc = {
            "features": [
                feature(
                    "plate", "box", width=50, depth=35, height=10, operation="new_body"
                ),
                feature(
                    "other",
                    "box",
                    width=12,
                    depth=12,
                    height=12,
                    cx=55,
                    operation="new_body",
                ),
                feature(
                    "hole",
                    "cut_hole",
                    x=0,
                    y=0,
                    radius=2,
                    end_condition="through_all",
                    target_part_id="body_001",
                ),
            ]
        }
        result = cached_build(doc)
        original = [p["shape"].Volume() for p in result["parts"]]
        rows = body_measurements(result["parts"])
        self.assertEqual(rows[0]["size_mm"], [50, 35, 10])
        self.assertEqual(rows[1]["size_mm"], [12, 12, 12])
        self.assertEqual(rows[1]["bounds_mm"][0][0], 49)
        self.assertTrue(rows[0]["circles"])
        self.assertTrue(
            all(abs(c["diameter_mm"] - 4) < 1e-8 for c in rows[0]["circles"])
        )
        self.assertAlmostEqual(rows[0]["volume_mm3"], 17500 - math.pi * 40, places=6)
        self.assertEqual(original, [p["shape"].Volume() for p in result["parts"]])
        response = snapshot(
            normalize_document(doc), threading.RLock(), include_drawing=False
        )
        self.assertEqual(response["body_measurements"], rows)

    def test_translated_rotated_body_uses_native_global_extent(self):
        doc = {
            "features": [
                feature("plate", "box", width=50, depth=35, height=10),
                feature(
                    "pose", "transform", rotation=[0, 0, 90], translation=[28, -18, 0]
                ),
            ]
        }
        rows = body_measurements(cached_build(doc)["parts"])
        for a, b in zip(rows[0]["size_mm"], [35, 50, 10]):
            self.assertAlmostEqual(a, b)
        for a, b in zip(rows[0]["bounds_mm"][0], [10.5, -43, 0]):
            self.assertAlmostEqual(a, b)


if __name__ == "__main__":
    unittest.main()
