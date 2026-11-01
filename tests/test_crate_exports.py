import tempfile
import unittest
from pathlib import Path
import zipfile
import json
import subprocess
import sys
import cadquery as cq
import ezdxf
import trimesh

from crate_studio.cad import build_parts, mesh_data, normalize_spec, verify_geometry
from crate_studio.exports import export_bundle


class CrateExportsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path(__file__).resolve().parents[1] / "output").mkdir(
            parents=True, exist_ok=True
        )

    def spec(self, **changes):
        result = dict(
            inner_width_mm=400,
            inner_depth_mm=300,
            inner_height_mm=250,
            thickness_mm=8,
            material="Plywood",
            lid=False,
            name="Test",
        )
        result.update(changes)
        return result

    def test_material_thickness_change_preserves_cavity(self):
        for t in (4, 8, 12.7):
            for lid in (False, True):
                s = self.spec(thickness_mm=t, lid=lid)
                parts = build_parts(s)
                check = verify_geometry(s, parts)
                self.assertTrue(check["passed"])
                self.assertEqual(check["internal_clear_mm"], [400, 300, 250])
                self.assertEqual(
                    check["expected_outer_mm"],
                    [400 + 2 * t, 300 + 2 * t, 250 + t * (1 + int(lid))],
                )
                self.assertEqual(len(mesh_data(parts)), 5 + int(lid))

    def test_intruding_panel_is_detected(self):
        s = self.spec()
        parts = build_parts(s)
        parts[1]["shape"] = parts[1]["shape"].translate((0, 4, 0))
        result = verify_geometry(s, parts)
        self.assertFalse(result["passed"])
        self.assertGreater(result["cavity_intrusion_mm3"], 0)

    def test_export_roundtrip_and_mm_profiles(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as directory:
            result = export_bundle(self.spec(lid=True), directory)
            self.assertTrue(result["verification"]["step_roundtrip"]["passed"])
            self.assertTrue(result["verification"]["stl_roundtrip"]["passed"])
            path = Path(directory)
            for row in result["cut_list"]:
                doc = ezdxf.readfile(path / f'panel-{row["part"]}.dxf')
                self.assertEqual(doc.units, 4)
                line = list(doc.modelspace())[0]
                self.assertTrue(line.closed)
                points = list(line.get_points())
                self.assertEqual(max(p[0] for p in points), row["width_mm"])
                self.assertEqual(max(p[1] for p in points), row["height_mm"])
            with zipfile.ZipFile(path / "crate-bundle.zip") as z:
                self.assertIn("parametric_model.py", z.namelist())
                self.assertIn("drawing.pdf", z.namelist())

    def test_stl_union_open_and_closed_noninteger_dimensions(self):
        for lid in (False, True):
            with tempfile.TemporaryDirectory(
                dir=Path(__file__).resolve().parents[1] / "output"
            ) as directory:
                spec = self.spec(
                    inner_width_mm=401.3,
                    inner_depth_mm=297.6,
                    inner_height_mm=252.2,
                    thickness_mm=6.7,
                    lid=lid,
                )
                result = export_bundle(spec, directory)
                mesh = trimesh.load(
                    str(Path(directory) / "assembly.stl"), force="mesh", process=True
                )
                self.assertTrue(mesh.is_watertight)
                self.assertTrue(mesh.is_winding_consistent)
                self.assertTrue(mesh.is_volume)
                self.assertAlmostEqual(
                    mesh.volume,
                    result["verification"]["expected_volume_mm3"],
                    delta=result["verification"]["stl_roundtrip"][
                        "volume_tolerance_mm3"
                    ],
                )
                self.assertTrue(result["verification"]["stl_roundtrip"]["passed"])

    def test_invalid_dimensions(self):
        for value in (0, -1, float("nan"), float("inf"), True, "oops"):
            with self.assertRaises(ValueError):
                normalize_spec(self.spec(thickness_mm=value))

    def test_exported_source_regenerates_an_edited_design(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as directory:
            folder = Path(directory)
            export_bundle(self.spec(), folder)
            changed = self.spec(inner_width_mm=425.4, thickness_mm=6, lid=True)
            (folder / "spec.json").write_text(json.dumps(changed), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(folder / "parametric_model.py")],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            restored = cq.importers.importStep(str(folder / "regenerated.step"))
            self.assertEqual(len(restored.solids().vals()), 6)
            bounds = restored.val().BoundingBox()
            self.assertAlmostEqual(bounds.xlen, 437.4, places=6)
            self.assertAlmostEqual(bounds.ylen, 312, places=6)
            self.assertAlmostEqual(bounds.zlen, 262, places=6)


if __name__ == "__main__":
    unittest.main()
