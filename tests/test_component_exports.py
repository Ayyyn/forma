import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from crate_studio.component_exports import export_components
from crate_studio.workspace_geometry import build_document


class ComponentExportTests(unittest.TestCase):
    def test_open_mesh_reports_specific_boundary_coordinates(self):
        import trimesh
        from crate_studio.workspace_geometry import mesh_topology_diagnostics

        mesh = trimesh.creation.box(extents=[10, 8, 2])
        self.assertEqual(mesh_topology_diagnostics(mesh)["boundary_edge_count"], 0)
        mesh.update_faces([False] + [True] * (len(mesh.faces) - 1))
        report = mesh_topology_diagnostics(mesh)
        self.assertEqual(report["boundary_edge_count"], 3)
        self.assertEqual(len(report["sample_edges"]), 3)
        self.assertIsNotNone(report["bounds_mm"])

    def test_touching_movable_bodies_stay_separate_and_bytes_repeat(self):
        built = build_document(
            {
                "features": [
                    {
                        "id": "a",
                        "type": "box",
                        "params": {"width": 10, "depth": 10, "height": 2},
                    },
                    {
                        "id": "b",
                        "type": "box",
                        "params": {
                            "width": 10,
                            "depth": 10,
                            "height": 2,
                            "cx": 10,
                            "operation": "new_body",
                        },
                    },
                ]
            }
        )
        with tempfile.TemporaryDirectory(dir="output") as root:
            folder = Path(root)
            report = export_components(built, folder)
            self.assertTrue(report["passed"])
            self.assertFalse(report["print_ready"])
            self.assertEqual(len(report["parts"]), 2)
            self.assertTrue(
                all(abs(p["native_volume_mm3"] - 200) < 1e-6 for p in report["parts"])
            )
            self.assertEqual(report["parts"][1]["bounds_mm"][0][0], 5)
            original = (folder / "components.zip").read_bytes()
            export_components(built, folder)
            self.assertEqual(original, (folder / "components.zip").read_bytes())
            with zipfile.ZipFile(folder / "components.zip") as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"body-001.stl", "body-002.stl", "components.json"},
                )
                self.assertEqual(json.loads(archive.read("components.json")), report)

    def test_serialized_mesh_shift_is_rejected_against_native_bounds(self):
        built = build_document(
            {
                "features": [
                    {
                        "id": "a",
                        "type": "box",
                        "params": {"width": 10, "depth": 10, "height": 2},
                    }
                ]
            }
        )
        built["mesh"][0]["vertices"] = [
            v + 8 if i % 3 == 0 else v
            for i, v in enumerate(built["mesh"][0]["vertices"])
        ]
        with tempfile.TemporaryDirectory(dir="output") as root:
            with self.assertRaisesRegex(ValueError, "read-back"):
                export_components(built, root)


if __name__ == "__main__":
    unittest.main()
