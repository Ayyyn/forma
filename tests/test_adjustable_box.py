"""Geometric controls for an ideal research candidate, not print qualification."""

import unittest

import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from research.adjustable_box import (
    TARGETS,
    dimensions,
    mapped,
    pattern,
    pose_checks,
    solve_tuck_azimuth,
    surface_crossings,
    _kind,
)


class AdjustableBoxGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = pattern()

    def test_fixed_uncut_graph_covers_the_original_sheet(self):
        graph = self.graph
        self.assertFalse(graph["cuts"])
        polygons = [Polygon(face) for face in graph["faces"]]
        self.assertTrue(
            all(
                p.is_valid and p.area > 0 and abs(p.area - p.convex_hull.area) < 1e-8
                for p in polygons
            )
        )
        combined = unary_union(polygons)
        self.assertAlmostEqual(sum(p.area for p in polygons), 40000)
        self.assertLess(
            combined.symmetric_difference(box(-100, -100, 100, 100)).area, 1e-8
        )
        self.assertTrue(all(len(edge["faces"]) in (1, 2) for edge in graph["edges"]))

    def test_four_states_preserve_facets_shared_hinges_and_usable_floors(self):
        for target in TARGETS:
            a, b = dimensions(target)
            poses = [(angle, 0, (45,) * 4) for angle in (0, 17, 53, 89, 90)]
            for index in range(4):
                poses.append((90, 0, (180,) * index + (112,) + (45,) * (3 - index)))
            poses.extend(
                (90, angle, (180,) * 4)
                for angle in ((0, 43, 91, 143, 180) if b > a else (0,))
            )
            for wall, band, gussets in poses:
                result = pose_checks(self.graph, target, wall, band, gussets=gussets)
                self.assertLess(result["max_facet_distance_error_mm"], 1e-8)
                self.assertLess(result["max_uncut_edge_closure_error_mm"], 1e-8)
                self.assertLess(result["max_panel_planarity_error_mm"], 1e-8)
                self.assertGreaterEqual(result["min_surface_z_mm"], -1e-8)
            floor = [
                mapped(face, target, 90, 180 if b > a else 0, gussets=(180,) * 4)
                for face in self.graph["faces"]
                if _kind(face, target, 200) == "floor"
            ]
            self.assertTrue(all(np.max(np.abs(face[:, 2])) < 1e-8 for face in floor))
            outline = unary_union([Polygon(face[:, :2]) for face in floor])
            expected = box(
                -target.length / 2,
                -target.width / 2,
                target.length / 2,
                target.width / 2,
            )
            self.assertLess(outline.symmetric_difference(expected).area, 1e-8)

    def test_uncut_upper_band_failure_and_searched_compatible_sequence(self):
        wrong = pose_checks(self.graph, TARGETS[-1], 90, 90)
        self.assertGreater(wrong["max_uncut_edge_closure_error_mm"], 50)
        search = solve_tuck_azimuth(self.graph)
        self.assertEqual(len(search["candidates"]), 136)
        self.assertLess(search["best"]["closure_error_mm"], 1e-8)
        for phi in (15, 45, 90, 130, 180):
            check = pose_checks(
                self.graph,
                TARGETS[-1],
                90,
                phi,
                gussets=(search["best"]["angle_deg"],) * 4,
            )
            self.assertLess(check["max_uncut_edge_closure_error_mm"], 1e-8)

    def test_surface_intersection_checker_rejects_real_crossing_but_allows_contacts(
        self,
    ):
        flat = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], float)
        crossing = np.array([[0, -1, -1], [0, 1, -1], [0, 1, 1], [0, -1, 1]], float)
        self.assertEqual(surface_crossings([flat, crossing]), [[0, 1]])
        self.assertFalse(surface_crossings([flat, crossing + [1, 0, 0]]))
        self.assertFalse(surface_crossings([flat, crossing + [0, 4, 0]]))
        self.assertFalse(
            surface_crossings([flat, flat.copy()])
        )  # ideal layered contact only

    def test_invalid_band_geometry_is_rejected_instead_of_projecting_through_floor(
        self,
    ):
        from research.adjustable_box import Target

        with self.assertRaises(ValueError):
            dimensions(Target("too-narrow", 130, 30))


if __name__ == "__main__":
    unittest.main()
