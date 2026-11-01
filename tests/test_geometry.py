import math
import unittest
import xml.etree.ElementTree as ET
import numpy as np
from pydantic import ValidationError
from continuum.geometry import Design, Requirements, cell, dimensions, evaluate, export_fold, export_svg, fold_assignments, mesh, validate_geometry
from continuum.search import baseline_design, search


class ReferenceGeometryTests(unittest.TestCase):
    def test_flat_analytic_reference(self):
        d = Design(columns=4, rows=2, a_mm=30, b_mm=20, gamma_deg=60)
        m = mesh(d, 0)
        self.assertEqual(m["vertices"][0], [0, 0, 0])
        np.testing.assert_allclose(m["vertices"][6], [40, math.sqrt(300), 0])
        dims = dimensions(d, 0)
        self.assertAlmostEqual(dims["x_mm"], 130)
        self.assertAlmostEqual(dims["y_mm"], math.sqrt(1200))

    def test_independent_edge_tilt_construction(self):
        for gamma in (25, 45, 60, 85):
            d = Design(gamma_deg=gamma)
            for theta in (0, 12, 49, 80, 88):
                psi = math.asin(math.sin(math.radians(theta)) * math.sin(math.radians(gamma)))
                l = d.a_mm * math.cos(psi)
                h = d.a_mm * math.sin(psi)
                v = d.b_mm * math.cos(math.radians(gamma)) / math.cos(psi)
                s = math.sqrt(max(0, d.b_mm ** 2 - v ** 2))
                vertices = np.asarray(mesh(d, theta)["vertices"])
                np.testing.assert_allclose(np.ptp(vertices, axis=0), [d.columns*l+v, d.rows*s, h], rtol=1e-10, atol=1e-10)

    def test_accordion_known_45_degree_state(self):
        d = Design(family="accordion", columns=4, rows=1, a_mm=20, b_mm=150, gamma_deg=90)
        dims = dimensions(d, 45)
        self.assertAlmostEqual(dims["x_mm"], 40 * math.sqrt(2))
        self.assertAlmostEqual(dims["y_mm"], 150)
        self.assertAlmostEqual(dims["z_mm"], 10 * math.sqrt(2))
        self.assertEqual(evaluate(d, Requirements())["metrics"]["crease_segments"], 3)

    def test_rigid_facet_distances_diagonals_area_planarity(self):
        for d in (Design(), Design(gamma_deg=25, packed_theta_deg=88), baseline_design()):
            result = validate_geometry(d, samples=31)
            self.assertTrue(result["passed"], result)

    def test_projected_coverage_independent_triangle_sum(self):
        d = Design()
        data = mesh(d, 61)
        points = np.asarray(data["vertices"])[:, :2]
        area = 0
        for face in data["faces"]:
            q = points[face]
            area += abs(np.dot(q[:, 0], np.roll(q[:, 1], -1)) - np.dot(q[:, 1], np.roll(q[:, 0], -1))) / 2
        expected = d.rows * d.columns * d.a_mm * d.b_mm * math.sin(math.radians(d.gamma_deg)) * math.cos(math.radians(61))
        self.assertAlmostEqual(area, expected, places=7)

    def test_mesh_is_connected_disk(self):
        d = Design()
        m = mesh(d, 40)
        self.assertEqual(len(m["vertices"]) - len(m["edges"]) + len(m["faces"]), 1)
        self.assertTrue(all(1 <= len(e["faces"]) <= 2 for e in m["edges"]))
        self.assertEqual(sum(e["boundary"] for e in m["edges"]), 2*(d.columns+d.rows))

    def test_mountain_valley_maekawa_at_interior_vertices(self):
        d = Design()
        m, assignments = mesh(d, 10), fold_assignments(d)
        for j in range(1, d.rows):
            for i in range(1, d.columns):
                vertex = j * (d.columns+1) + i
                creases = [a for e, a in zip(m["edges"], assignments) if vertex in e["vertices"]]
                self.assertEqual(len(creases), 4)
                self.assertEqual(abs(creases.count("M") - creases.count("V")), 2)

    def test_invalid_and_singular_parameters_rejected(self):
        for kwargs in ({"a_mm": float("nan")}, {"gamma_deg": 90}, {"packed_theta_deg": 90}, {"rows": 1},
                       {"family": "accordion", "gamma_deg": 90, "rows": 2}, {"packed_theta_deg": 5}):
            with self.assertRaises(ValidationError):
                Design(**kwargs)
        for angle in (89, float("nan"), -1):
            with self.assertRaises(ValueError):
                cell(Design(), angle)

    def test_crease_sign_matches_known_accordion_ridges(self):
        d = Design(family="accordion", columns=4, rows=1, a_mm=20, b_mm=150, gamma_deg=90)
        data = mesh(d, 30)
        for edge, assignment in zip(data['edges'], fold_assignments(d)):
            if not edge['boundary']:
                column = edge['vertices'][0] % (d.columns+1)
                # Printed side is +Z. Odd columns are upward ridges, hence mountains.
                self.assertEqual(assignment, 'M' if column % 2 else 'V')

    def test_default_feasible_and_baseline_rejected(self):
        r = Requirements()
        self.assertTrue(evaluate(Design(), r)["feasible"])
        b = evaluate(baseline_design(), r)
        self.assertFalse(b["feasible"])
        self.assertTrue(any(c["name"] == "Packed long side" and not c["passed"] for c in b["constraints"]))

    def test_impossible_blank_target_has_no_false_feasibility(self):
        r = Requirements(deployed_x_min_mm=500, blank_x_max_mm=200)
        s = search(r, count=64)
        self.assertEqual(s["feasible_count"], 0)
        self.assertTrue(all(not c["feasible"] for c in s["candidates"]))

    def test_search_reproducibility_and_pareto(self):
        r = Requirements()
        a, b = search(r), search(r)
        self.assertEqual(a, b)
        self.assertGreater(a["feasible_count"], 0)
        self.assertTrue(a["pareto_ids"])
        self.assertLessEqual(a["evaluated_count"], a["requested_budget"])

    def test_exports_match_source_and_print_units(self):
        d = Design()
        flat, deployed = export_fold(d), export_fold(d, folded=True)
        self.assertEqual(flat["frame_unit"], "mm")
        self.assertEqual(flat["faces_vertices"], deployed["faces_vertices"])
        self.assertEqual(flat["vertices_coords"], mesh(d, 0)["vertices"])
        self.assertEqual(deployed["vertices_coords"], mesh(d, d.deployed_theta_deg)["vertices"])
        self.assertEqual(len(flat["edges_assignment"]), len(flat["edges_vertices"]))
        svg = ET.fromstring(export_svg(d))
        self.assertTrue(svg.attrib["width"].endswith("mm"))
        self.assertLessEqual(float(svg.attrib["width"][:-2]), 297)
        self.assertLessEqual(float(svg.attrib["height"][:-2]), 210)
        lines = svg.findall(".//{http://www.w3.org/2000/svg}line")
        self.assertEqual(len(lines), len(flat["edges_vertices"]))
        for line, edge in zip(lines, flat["edges_vertices"]):
            p, q = [flat["vertices_coords"][i] for i in edge]
            self.assertAlmostEqual(float(line.attrib["x1"]), p[0], places=5)
            self.assertAlmostEqual(float(line.attrib["y2"]), q[1], places=5)


if __name__ == "__main__":
    unittest.main()
