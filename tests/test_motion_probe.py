"""Controls for native obstruction diagnostics, independent of virtual joints."""

import unittest
import cadquery as cq

from crate_studio.motion_probe import translation_probe


class TranslationProbeTests(unittest.TestCase):
    def fixture(self):
        # Rigid U-guide holds a sliding block between two cheeks. Open above:
        # transverse blockage must not be misreported as globally captive.
        guide = cq.Workplane("XY").box(20, 10, 2, centered=(True, True, False)).val()
        for y in (-4, 4):
            cheek = (
                cq.Workplane("XY")
                .box(20, 2, 6, centered=(True, True, False))
                .translate((0, y, 1))
                .val()
            )
            guide = guide.fuse(cheek)
        slider = (
            cq.Workplane("XY")
            .box(4, 5.4, 2, centered=(True, True, False))
            .translate((0, 0, 2.3))
            .val()
        )
        return [{"id": "guide", "shape": guide}, {"id": "slider", "shape": slider}]

    def test_free_axis_blocked_transverse_and_unretained_upward(self):
        parts = self.fixture()
        axial = translation_probe(parts, ["slider"], [1, 0, 0], 5, 11)
        self.assertTrue(axial["path_clear_at_samples"])
        cross = translation_probe(parts, ["slider"], [0, 1, 0], 2, 21)
        self.assertTrue(cross["initial_pose_clear"])
        self.assertAlmostEqual(cross["first_blocked_sample_mm"], 0.4)
        self.assertIn("bounds_mm", cross["frames"][-1]["overlaps"][0])
        upward = translation_probe(parts, ["slider"], [0, 0, 1], 10, 21)
        self.assertTrue(upward["path_clear_at_samples"])
        self.assertFalse(cross["global_retention_verified"])

    def test_named_pose_and_rigid_group_preserve_internal_clearance(self):
        parts = self.fixture()
        spec = {
            "root": "guide",
            "joints": [
                {
                    "id": "slide",
                    "parent": "guide",
                    "child": "slider",
                    "type": "prismatic",
                    "axis": [1, 0, 0],
                    "origin": [0, 0, 0],
                    "limits": [0, 20],
                }
            ],
            "states": [
                {"name": "inside", "values": {"slide": 0}},
                {"name": "outside", "values": {"slide": 20}},
            ],
            "connections": [],
            "samples_per_segment": 2,
        }
        inside = translation_probe(parts, ["slider"], [0, 1, 0], 2, 21, spec, "inside")
        outside = translation_probe(
            parts, ["slider"], [0, 1, 0], 2, 21, spec, "outside"
        )
        self.assertFalse(inside["path_clear_at_samples"])
        self.assertTrue(outside["path_clear_at_samples"])
        parts.append({"id": "attached", "shape": parts[-1]["shape"]})
        self.assertTrue(
            translation_probe(parts, ["slider", "attached"], [1, 0, 0], 2, 3)[
                "path_clear_at_samples"
            ]
        )

    def test_initial_interference_and_invalid_probes_are_explicit(self):
        parts = self.fixture()
        parts[-1]["shape"] = parts[-1]["shape"].translate((0, 2, 0))
        self.assertFalse(
            translation_probe(parts, ["slider"], [1, 0, 0], 2, 3)["initial_pose_clear"]
        )
        for moving, axis, distance, n in [
            (["guide", "slider"], [1, 0, 0], 1, 3),
            (["slider"], [0, 0, 0], 1, 3),
            (["slider"], [1, 0, 0], float("nan"), 3),
            (["slider"], [1, 0, 0], 1, 100),
        ]:
            with self.assertRaises(ValueError):
                translation_probe(parts, moving, axis, distance, n)


if __name__ == "__main__":
    unittest.main()
