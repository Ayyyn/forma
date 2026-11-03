from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import cadquery as cq
from pypdf import PdfReader

from crate_studio.mechanical_print import orient_part, export_print_pack
from tests.test_assembly_study import fixture, path


class MechanicalPrintTests(unittest.TestCase):
    def test_real_bed_contact_and_volume_preserved(self):
        shape = cq.Workplane("XY").box(3, 8, 30).val()
        oriented = orient_part({"id": "test", "shape": shape})
        self.assertAlmostEqual(oriented["shape"].Volume(), shape.Volume(), places=7)
        self.assertAlmostEqual(oriented["shape"].BoundingBox().zmin, 0, places=7)
        self.assertAlmostEqual(
            oriented["orientation"]["planar_bed_contact_mm2"], 240, places=7
        )
        with self.assertRaisesRegex(ValueError, "no planar supporting"):
            orient_part({"id": "ball", "shape": cq.Workplane("XY").sphere(3).val()})

    def test_complete_archive_readback_source_and_assembly_pages(self):
        doc, _ = fixture()
        doc["metadata"] = {
            "assembly_plan": path(True),
            "print_settings": {"bed_width_mm": 180},
        }
        original = deepcopy(doc)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "private-receipts.json").write_text("must not enter archive")
            result = export_print_pack(
                doc, folder, context={"revision_id": "test-revision", "pose": "source"}
            )
            manifest = result["manifest"]
            self.assertTrue(manifest["geometric_print_preflight_passed"])
            self.assertTrue(manifest["initial_assembly_verified"])
            self.assertFalse(manifest["physical_fit_verified"])
            self.assertEqual(manifest["settings"]["bed_width_mm"], 180)
            reader = PdfReader(folder / "assembly-drawings.pdf")
            self.assertEqual(len(reader.pages), 9)
            self.assertIn("test-revision", reader.pages[3].extract_text())
            self.assertIn("BUILD PLATE 1", reader.pages[2].extract_text())
            self.assertIn("Assembly 03", reader.pages[-1].extract_text())
            self.assertEqual(
                json.loads((folder / "source-project.json").read_text()), doc
            )
            with zipfile.ZipFile(folder / "print-pack.zip") as archive:
                self.assertNotIn("private-receipts.json", archive.namelist())
                hashes = json.loads(archive.read("sha256.json"))
                self.assertTrue(
                    all(
                        hashlib.sha256(archive.read(k)).hexdigest() == v
                        for k, v in hashes.items()
                    )
                )
                self.assertEqual(manifest["checks"]["plate-1.stl"]["components"], 2)
        self.assertEqual(doc, original)

    def test_failed_initial_assembly_cannot_be_packaged(self):
        doc, _ = fixture()
        doc["metadata"] = {"assembly_plan": path(False)}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "assembly plan fails"):
                export_print_pack(doc, tmp)
