"""Native-solid controls for general, model-declared mechanism paths."""

from copy import deepcopy
import unittest

from crate_studio.mechanism_study import mechanism_study, validate_spec
from crate_studio.workspace_cache import cached_build


def document():
    return {
        "name": "Motion control",
        "features": [
            {
                "id": "fixed",
                "type": "box",
                "params": {"width": 4, "depth": 4, "height": 2},
            },
            {
                "id": "moving",
                "type": "box",
                "params": {
                    "width": 4,
                    "depth": 4,
                    "height": 2,
                    "cx": -20,
                    "operation": "new_body",
                },
            },
        ],
    }


def specification(end=40):
    return {
        "root": "body_001",
        "joints": [
            {
                "id": "slide",
                "parent": "body_001",
                "child": "body_002",
                "type": "prismatic",
                "axis": [1, 0, 0],
                "origin": [0, 0, 0],
                "limits": [0, 40],
            }
        ],
        "states": [
            {"name": "start", "values": {"slide": 0}},
            {"name": "end", "values": {"slide": end}},
        ],
        "connections": [],
        "samples_per_segment": 9,
    }


class MechanismStudyTests(unittest.TestCase):
    def test_finite_solids_catch_intermediate_collision_with_clear_endpoints(self):
        doc = document()
        built = cached_build(doc)
        result = mechanism_study(doc, built, specification())
        self.assertFalse(result["passed"])
        self.assertEqual(result["frames"][0]["overlaps"], [])
        self.assertEqual(result["frames"][-1]["overlaps"], [])
        middle = result["frames"][4]["overlaps"]
        self.assertEqual(middle[0]["parts"], ["body_001", "body_002"])
        self.assertAlmostEqual(middle[0]["volume_mm3"], 32)
        safe = mechanism_study(doc, built, specification(10))
        self.assertTrue(safe["passed"])
        self.assertFalse(safe["locking_verified"])

    def test_arbitrary_axis_rotation_and_declared_loop_failure(self):
        doc = document()
        doc["features"][0]["params"]["cx"] = 100
        built = cached_build(doc)
        spec = specification()
        spec["joints"][0].update(type="revolute", axis=[0, 0, 2], limits=[0, 90])
        spec["states"][-1]["values"]["slide"] = 90
        result = mechanism_study(doc, built, spec)
        self.assertTrue(result["passed"])
        matrix = result["frames"][-1]["pose_matrices"]["body_002"]
        self.assertAlmostEqual(matrix[0][0], 0, places=12)
        self.assertAlmostEqual(matrix[1][0], 1, places=12)
        self.assertAlmostEqual(result["frames"][-1]["bounds_mm"][0][1], -22)
        spec["connections"] = [
            {
                "type": "point",
                "a": "body_001",
                "b": "body_002",
                "anchor_a": [-20, 0, 0],
                "anchor_b": [-20, 0, 0],
            }
        ]
        bad = mechanism_study(doc, built, spec)
        self.assertFalse(bad["passed"])
        self.assertGreater(bad["max_loop_position_error_mm"], 28)

    def test_reject_disconnected_tree_missing_state_values_and_nonfinite_inputs(self):
        original = specification()
        variants = []
        bad = deepcopy(original)
        bad["joints"][0]["parent"] = "body_002"
        variants.append(bad)
        bad = deepcopy(original)
        bad["states"][1]["values"] = {}
        variants.append(bad)
        bad = deepcopy(original)
        bad["joints"][0]["axis"] = [0, 0, 0]
        variants.append(bad)
        bad = deepcopy(original)
        bad["states"][1]["values"]["slide"] = float("nan")
        variants.append(bad)
        bad = deepcopy(original)
        bad["joints"][0]["limits"] = [0, 3]
        variants.append(bad)
        for spec in variants:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                validate_spec(spec, ["body_001", "body_002"])

    def test_generic_playback_uses_actual_native_mesh_and_rechecks_geometry(self):
        from crate_studio.workspace_workflow import motion_study

        doc = document()
        doc["metadata"] = {"design_mechanism": specification(10)}
        result = motion_study(doc)
        self.assertEqual(result["family"], "general_mechanism")
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["parts"]), 2)
        self.assertEqual(result["frames"][-1]["progress_pct"], 100)
        changed = deepcopy(doc)
        changed["features"][1]["params"]["cx"] = -10
        self.assertFalse(motion_study(changed)["passed"])
        with self.assertRaises(ValueError):
            motion_study(
                doc, {"family": "general_mechanism", "samples_per_segment": 999}
            )


if __name__ == "__main__":
    unittest.main()
