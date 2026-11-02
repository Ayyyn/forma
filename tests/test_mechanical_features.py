import math
import tempfile
import unittest
from pathlib import Path

import cadquery as cq
from crate_studio.mechanical_features import gear, threaded_body, socket_screw
from crate_studio.workspace_geometry import _bounds, build_document, export_document
from crate_studio.workspace_agent import apply_plan, PARAMS


class MechanicalFeaturesTests(unittest.TestCase):
    def test_spur_dimensions_bore_and_rebuild(self):
        p = dict(module=1.2, teeth=20, thickness=4, bore_diameter=5, z=-4)
        body = gear("spur_gear", p)
        self.assertTrue(body.isValid())
        bounds = _bounds(body)
        self.assertAlmostEqual(bounds[1][0] - bounds[0][0], 26.4, places=5)
        self.assertAlmostEqual(bounds[0][2], -4, places=5)
        self.assertAlmostEqual(bounds[1][2], 0, places=5)
        hole = cq.Solid.makeCylinder(2.49, 4, cq.Vector(0, 0, -4))
        self.assertLess(abs(body.intersect(hole).Volume()), 1e-6)
        self.assertGreater(
            gear("spur_gear", {**p, "thickness": 8}).Volume(), body.Volume() * 1.99
        )

    def test_d_bore_independent_of_tooth_phase(self):
        p = dict(
            module=1, teeth=20, thickness=4, bore_diameter=4, bore_flat=1.5, phase=9
        )
        body = gear("spur_gear", p)
        self.assertLess(
            body.intersect(cq.Solid.makeCylinder(0.1, 4, cq.Vector(1, 0, 0))).Volume(),
            1e-8,
        )
        self.assertAlmostEqual(
            body.intersect(
                cq.Solid.makeCylinder(0.1, 4, cq.Vector(1.8, 0, 0))
            ).Volume(),
            math.pi * 0.1**2 * 4,
            places=6,
        )

    def test_bevel_step_roundtrip_and_axis_apex(self):
        p = dict(
            module=1,
            teeth=18,
            cone_angle=45,
            face_width=4,
            bore_diameter=4,
            cx=25,
            axis="+X",
        )
        body = gear("bevel_gear", p)
        self.assertLess(_bounds(body)[1][0], 25)
        doc = {"features": [{"id": "gear", "type": "bevel_gear", "params": p}]}
        temporary_root = Path(__file__).resolve().parents[1] / "output"
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as temp:
            exported = export_document(doc, None, temp)
            self.assertTrue(exported["checks"]["passed"], exported["checks"])
            proof = exported["checks"]["step_roundtrip"]
            if proof["symmetric_difference_mm3"] is not None:
                self.assertLessEqual(
                    proof["symmetric_difference_mm3"], proof["volume_tolerance_mm3"]
                )

    def test_two_start_thread_is_trimmed_and_internal_clearance(self):
        p = dict(
            major_diameter=7.6,
            root_diameter=6.2,
            pitch=1.4,
            starts=2,
            length=8,
            profile="buttress",
        )
        bolt = threaded_body(p)
        nut = threaded_body(
            {**p, "external": False, "outer_diameter": 14, "radial_clearance": 0.05}
        )
        self.assertTrue(bolt.isValid() and nut.isValid())
        self.assertEqual(len(bolt.Solids()), 1)
        self.assertAlmostEqual(_bounds(bolt)[0][2], 0, places=5)
        self.assertAlmostEqual(_bounds(bolt)[1][2], 8, places=5)
        self.assertLess(abs(bolt.intersect(nut).Volume()), 1e-5)
        left = threaded_body({**p, "hand": "left"})
        self.assertGreater(abs(bolt.cut(left).Volume()), 1)

    def test_socket_underhead_length_and_negative_z(self):
        body = socket_screw(
            dict(
                major_diameter=4,
                pitch=0.7,
                length=6,
                head_height=4,
                head_diameter=7,
                socket_af=3,
                socket_depth=2,
            )
        )
        bounds = _bounds(body)
        self.assertTrue(body.isValid())
        self.assertAlmostEqual(bounds[0][2], -10, places=5)
        self.assertAlmostEqual(bounds[1][2], 0, places=5)
        self.assertLess(
            body.intersect(
                cq.Solid.makeCylinder(1, 1.9, cq.Vector(0, 0, -1.9))
            ).Volume(),
            1e-7,
        )

    def test_small_single_start_threads_retain_crests_and_core(self):
        # Regression: a valid Boolean result can still drop the entire ridge,
        # or retain only the ridge while losing the cylindrical core.
        for diameter, pitch, length in ((3, 0.5, 6), (4, 0.7, 6), (6, 1, 10)):
            with self.subTest(diameter=diameter):
                root = diameter - 1.226869 * pitch
                body = threaded_body(
                    dict(major_diameter=diameter, pitch=pitch, length=length)
                )
                core = cq.Solid.makeCylinder(root / 2, length)
                self.assertGreater(body.Volume(), core.Volume() * 1.1)
                self.assertLess(abs(core.cut(body).Volume()), 1e-5)
                self.assertAlmostEqual(
                    _bounds(body)[1][0] - _bounds(body)[0][0], diameter, places=3
                )

    def test_invalid_parameters_and_bounded_plans(self):
        for patch in ({"teeth": True}, {"teeth": 161}, {"backlash": -1}, {"axis": "Q"}):
            with self.assertRaises(ValueError):
                gear("spur_gear", {"module": 1, "teeth": 18, "thickness": 4, **patch})
        for patch in ({"starts": 0}, {"root_diameter": 8}, {"apex_offset": 4}):
            with self.assertRaises(ValueError):
                threaded_body(dict(major_diameter=6, pitch=1, length=5, **patch))
        self.assertIn("bevel_gear", PARAMS)
        plan = {
            "summary": "Gear",
            "status": "ready",
            "questions": [],
            "evidence": [{"quote": "a gear"}],
            "operations": [
                {
                    "action": "add",
                    "feature": {
                        "id": "g",
                        "type": "spur_gear",
                        "name": "Gear",
                        "params": {"module": 1, "teeth": 20, "thickness": 4},
                        "suppressed": False,
                    },
                }
            ],
        }
        result = apply_plan({"features": []}, plan, "Make a gear")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["document"]["features"][0]["type"], "spur_gear")


if __name__ == "__main__":
    unittest.main()
