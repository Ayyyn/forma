"""Controls for native obstruction diagnostics, independent of virtual joints."""

import unittest
import cadquery as cq

from crate_studio.motion_probe import translation_probe, prismatic_pair_probe


class TranslationProbeTests(unittest.TestCase):
    def test_pair_axes_follow_rotated_parent(self):
        import numpy as np

        parts = self.fixture()
        parts.append(
            {
                "id": "root",
                "shape": cq.Workplane("XY")
                .box(1, 1, 1)
                .translate((-100, -100, 0))
                .val(),
            }
        )
        spec = {
            "root": "root",
            "joints": [
                {
                    "id": "turn",
                    "parent": "root",
                    "child": "guide",
                    "type": "revolute",
                    "axis": [0, 0, 1],
                    "origin": [0, 0, 0],
                    "limits": [0, 90],
                },
                {
                    "id": "slide",
                    "parent": "guide",
                    "child": "slider",
                    "type": "prismatic",
                    "axis": [1, 0, 0],
                    "origin": [0, 0, 0],
                    "limits": [0, 20],
                },
            ],
            "states": [
                {"name": "inside", "values": {"turn": 90, "slide": 0}},
                {"name": "outside", "values": {"turn": 90, "slide": 20}},
            ],
            "connections": [],
            "samples_per_segment": 2,
        }
        result = prismatic_pair_probe(parts, spec, "slide", "inside", 2, 5)
        axial = result["directions"]["axial_positive"]
        self.assertTrue(np.allclose(axial["direction_world"], [0, 1, 0], atol=1e-10))
        self.assertTrue(axial["path_clear_at_samples"])

    def test_six_direction_pair_probe_excludes_unrelated_obstruction(self):
        parts = self.fixture()
        parts.append(
            {
                "id": "ceiling",
                "shape": cq.Workplane("XY").box(20, 20, 2).translate((0, 0, 8)).val(),
            }
        )
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
                },
                {
                    "id": "roof",
                    "parent": "guide",
                    "child": "ceiling",
                    "type": "fixed",
                    "axis": [0, 0, 1],
                    "origin": [0, 0, 0],
                    "limits": [0, 0],
                },
            ],
            "states": [
                {"name": "inside", "values": {"slide": 0, "roof": 0}},
                {"name": "outside", "values": {"slide": 20, "roof": 0}},
            ],
            "connections": [],
            "samples_per_segment": 2,
        }
        whole = translation_probe(parts, ["slider"], [0, 0, 1], 10, 21)
        self.assertFalse(whole["path_clear_at_samples"])
        pair = prismatic_pair_probe(parts, spec, "slide", "inside", 10, 21)
        self.assertEqual(len(pair["directions"]), 6)
        upward = next(
            v for v in pair["directions"].values() if v["direction_world"] == [0, 0, 1]
        )
        self.assertTrue(upward["path_clear_at_samples"])
        self.assertFalse(pair["global_retention_verified"])
        with self.assertRaises(ValueError):
            prismatic_pair_probe(parts, spec, "roof", "inside", 2, 3)

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
