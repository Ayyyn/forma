"""Independent material/lead witnesses; no CAD-bench reference geometry."""

import unittest

from crate_studio.mechanical_features import threaded_body


class ThreadKinematicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = dict(
            major_diameter=6,
            root_diameter=4.8,
            pitch=1.2,
            starts=2,
            length=4.8,
            profile="buttress",
        )
        cls.bolt = threaded_body(cls.params)
        cls.nut = threaded_body(
            {
                **cls.params,
                "external": False,
                "outer_diameter": 10,
                "radial_clearance": 0.12,
            }
        )

    def test_two_starts_have_half_turn_symmetry_but_not_quarter_turn(self):
        half = self.bolt.rotate((0, 0, 0), (0, 0, 1), 180)
        quarter = self.bolt.rotate((0, 0, 0), (0, 0, 1), 90)
        self.assertLess(abs(self.bolt.cut(half).Volume()), 1e-5)
        self.assertGreater(abs(self.bolt.cut(quarter).Volume()), 1)

    def test_correct_lead_clears_nut_during_screw_motion(self):
        lead = self.params["pitch"] * self.params["starts"]
        for angle in (0, 45, 135):
            moved = self.bolt.rotate((0, 0, 0), (0, 0, 1), angle).translate(
                (0, 0, lead * angle / 360)
            )
            with self.subTest(angle=angle):
                self.assertLess(abs(moved.intersect(self.nut).Volume()), 1e-5)

    def test_wrong_axial_direction_is_detected_as_material_collision(self):
        angle = 45
        lead = self.params["pitch"] * self.params["starts"]
        moved = self.bolt.rotate((0, 0, 0), (0, 0, 1), angle).translate(
            (0, 0, -lead * angle / 360)
        )
        self.assertGreater(abs(moved.intersect(self.nut).Volume()), 0.1)


if __name__ == "__main__":
    unittest.main()
