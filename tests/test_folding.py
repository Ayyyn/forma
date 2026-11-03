import itertools
import math
import unittest

import numpy as np
import trimesh

from crate_studio.folding import (
    specification,
    pattern,
    transforms,
    assembly,
    closure,
    collisions,
    DEFAULT_LIMITS,
)
from crate_studio.folding_study import folding_study, folding_feature
from continuum.audit import reference_vertices


class FoldingTests(unittest.TestCase):
    def test_all_graphs_are_connected_and_hinges_close_at_three_states(self):
        for family, limit in DEFAULT_LIMITS.items():
            p = specification({"family": family})
            graph = pattern(p)
            for angle in (0, limit / 2, limit):
                matrices = transforms(p, graph, angle)
                self.assertLess(closure(graph, matrices, p["hinge_radius"]), 1e-8)
                for matrix in matrices:
                    np.testing.assert_allclose(
                        matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-12
                    )
                    self.assertAlmostEqual(np.linalg.det(matrix[:3, :3]), 1)

    def test_miura_against_independent_unsimplified_reference(self):
        for gamma in (40, 60, 78):
            p = specification(
                {"family": "miura", "rows": 3, "columns": 4, "sector_angle": gamma}
            )
            graph = pattern(p)
            flat = np.asarray(graph["vertices"])
            flat[:, 2] = p["hinge_radius"]
            for angle in (0, 25, 65):
                poses = transforms(p, graph, angle)
                expected = reference_vertices(
                    {
                        "a_mm": p["panel_width"],
                        "b_mm": p["panel_height"],
                        "gamma_deg": gamma,
                        "columns": p["columns"],
                        "rows": p["rows"],
                    },
                    angle,
                )
                for face, matrix in zip(graph["faces"], poses):
                    for vertex in face:
                        x, y, z = flat[vertex]
                        j = round(
                            y / (p["panel_height"] * math.sin(math.radians(gamma)))
                        )
                        i = round(
                            (
                                x
                                - (j % 2)
                                * p["panel_height"]
                                * math.cos(math.radians(gamma))
                            )
                            / p["panel_width"]
                        )
                        observed = (matrix @ np.array([x, y, z, 1.0]))[:3]
                        wanted = expected[j * (p["columns"] + 1) + i] + np.array(
                            [0, 0, p["hinge_radius"]]
                        )
                        np.testing.assert_allclose(observed, wanted, atol=1e-8)

    def test_hardware_is_separate_positive_valid_solids_and_bad_original_pose_is_rejected(
        self,
    ):
        good = assembly({"family": "concertina", "count": 2}, 110)
        self.assertEqual(len(good["parts"]), 3)
        self.assertTrue(
            all(
                p["shape"].isValid()
                and len(p["shape"].Solids()) == 1
                and p["shape"].Volume() > 0
                for p in good["parts"]
            )
        )
        self.assertFalse(collisions(good["parts"])["overlaps"])
        bad = assembly(
            {
                "family": "miura",
                "columns": 2,
                "rows": 2,
                "panel_width": 32,
                "panel_height": 36,
                "hinge_radius": 2.6,
                "panel_inset": 3.1,
            },
            65,
        )
        self.assertTrue(collisions(bad["parts"])["overlaps"])

    def test_reuse_matches_uncached_native_checks_for_all_five_families(self):
        for family, limit in DEFAULT_LIMITS.items():
            p = specification({"family": family, "columns": 2, "rows": 2, "count": 3})
            cache = {}
            for angle in (0, limit * 0.31, limit * 0.67, limit):
                parts = assembly(p, angle)["parts"]
                fresh = collisions(parts)
                reused = collisions(parts, pair_cache=cache)
                self.assertEqual(fresh["overlaps"], reused["overlaps"])
                self.assertFalse(reused["overlaps"])

    def test_mixed_history_cannot_keep_a_folding_qualification(self):
        with self.assertRaises(ValueError):
            folding_feature(
                {"features": [{"type": "folding_assembly"}, {"type": "box"}]}
            )

    def test_trajectory_reuses_hardware_but_binds_current_geometry_signature(self):
        doc = {
            "features": [
                {
                    "id": "f",
                    "type": "folding_assembly",
                    "params": {"family": "cube_net"},
                }
            ]
        }
        config = {"family": "panel_hinges", "max_angle_deg": 90, "samples": 5}
        a = folding_study(doc, config)
        doc["features"][0]["params"]["fold_angle"] = 45
        b = folding_study(doc, config)
        self.assertTrue(a["passed"] and b["passed"])
        self.assertNotEqual(a["geometry_signature"], b["geometry_signature"])
        self.assertEqual(a["frames"], b["frames"])
        self.assertGreater(sum(f["reused_invariant_pairs"] for f in b["frames"]), 0)

    def test_invalid_geometry_settings_do_not_silently_resize(self):
        for changes in (
            {"pin_diameter": 8},
            {"hinge_radius": 1},
            {"panel_inset": 1},
            {"rows": 2.2},
            {"family": "kresling"},
            {"fold_angle": 89},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                specification(changes)

    def test_display_mesh_is_closed_and_agrees_with_posed_native_geometry(self):
        from crate_studio.folding import _native_bounds

        for family in ("miura", "cube_net"):
            params = specification({"family": family, "columns": 2, "rows": 2})
            doc = {"features": [{"type": "folding_assembly", "params": params}]}
            study = folding_study(
                doc,
                {
                    "family": "panel_hinges",
                    "max_angle_deg": DEFAULT_LIMITS[family],
                    "samples": 5,
                },
            )
            frame = study["frames"][2]
            native = assembly(params, frame["angle_deg"])
            for part, solid in zip(study["parts"], native["parts"]):
                mesh = trimesh.Trimesh(
                    vertices=np.asarray(part["vertices"]).reshape(-1, 3),
                    faces=np.asarray(part["triangles"]).reshape(-1, 3),
                    process=True,
                )
                self.assertTrue(mesh.is_watertight and mesh.is_winding_consistent)
                mesh.apply_transform(frame["pose_matrices"][part["face"]])
                np.testing.assert_allclose(
                    mesh.bounds, _native_bounds(solid["shape"]), atol=0.05
                )
                self.assertLess(
                    abs(mesh.volume - solid["shape"].Volume())
                    / solid["shape"].Volume(),
                    0.005,
                )
