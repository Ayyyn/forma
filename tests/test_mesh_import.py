import unittest
import numpy as np
import trimesh
from crate_studio.mesh_import import import_mesh


class MeshImportTests(unittest.TestCase):
    def test_stl_units_and_bounds_are_explicit_and_exact(self):
        mesh = trimesh.creation.box(extents=[2, 1, 0.5])
        shape, metadata = import_mesh(mesh.export(file_type="stl"), "stl", "inch")
        box = shape.BoundingBox()
        np.testing.assert_allclose(
            [box.xlen, box.ylen, box.zlen], [50.8, 25.4, 12.7], atol=1e-5
        )
        self.assertAlmostEqual(shape.Volume(), 25.4**3, places=5)
        self.assertEqual(metadata["conversion_to_mm"], 25.4)
        with self.assertRaises(ValueError):
            import_mesh(mesh.export(file_type="stl"), "stl", None)

    def test_obj_conversion_retains_two_disjoint_solids(self):
        a = trimesh.creation.box(extents=[20, 10, 5])
        b = a.copy()
        b.apply_translation([50, 0, 0])
        raw = trimesh.util.concatenate([a, b]).export(file_type="obj").encode()
        shape, metadata = import_mesh(raw, "obj", "mm")
        self.assertEqual(len(shape.Solids()), 2)
        self.assertAlmostEqual(shape.Volume(), 2000)

    def test_open_or_oversized_mesh_is_rejected_without_guessing_repairs(self):
        mesh = trimesh.creation.box()
        mesh.update_faces(np.arange(len(mesh.faces) - 1))
        with self.assertRaises(ValueError):
            import_mesh(mesh.export(file_type="stl"), "stl", "mm")
        dense = trimesh.creation.icosphere(subdivisions=4)
        with self.assertRaises(ValueError):
            import_mesh(dense.export(file_type="stl"), "stl", "mm")

    def test_overlapping_components_are_rejected(self):
        a = trimesh.creation.box(extents=[20, 10, 5])
        b = a.copy()
        b.apply_translation([5, 0, 0])
        raw = trimesh.util.concatenate([a, b]).export(file_type="stl")
        with self.assertRaisesRegex(ValueError, "overlap"):
            import_mesh(raw, "stl", "mm")
