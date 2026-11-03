from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import numpy as np
from crate_studio.folding import specification, flat_assembly, _native_bounds
from crate_studio.folding_print import (
    arrange,
    print_settings,
    fold_interchange,
    export_print_pack,
)
from pypdf import PdfReader


class FoldingPrintTests(unittest.TestCase):
    def test_plates_ground_all_parts_and_fit_configured_volume(self):
        p = specification({"family": "miura", "rows": 4, "columns": 4})
        parts = flat_assembly(p)["parts"]
        settings = print_settings()
        plates = arrange(parts, settings)
        self.assertEqual(sum(len(plate["parts"]) for plate in plates), 40)
        for plate in plates:
            bounds = [_native_bounds(part["shape"]) for part in plate["parts"]]
            for lo, hi in bounds:
                self.assertAlmostEqual(lo[2], 0, places=6)
                self.assertTrue(np.all(lo >= -1e-7))
                self.assertLessEqual(hi[0], 220)
                self.assertLessEqual(hi[1], 220)
            for i in range(len(bounds)):
                for j in range(i):
                    self.assertTrue(
                        np.any(
                            np.minimum(bounds[i][1], bounds[j][1])
                            - np.maximum(bounds[i][0], bounds[j][0])
                            < 0
                        )
                    )

    def test_fold_interchange_has_matching_topology_and_signed_angles(self):
        p = specification({"family": "miura"})
        g = flat_assembly(p)["graph"]
        v = fold_interchange(p, g, 65)
        self.assertEqual(v["frame_unit"], "mm")
        self.assertEqual(len(v["edges_vertices"]), len(v["edges_assignment"]))
        for assigned, angle in zip(v["edges_assignment"], v["edges_foldAngle"]):
            if assigned == "M":
                self.assertLess(angle, 0)
            if assigned == "V":
                self.assertGreater(angle, 0)

    def test_verified_pack_contains_native_layout_coupon_and_readable_guide(self):
        doc = {
            "name": "Cube QA",
            "features": [
                {
                    "id": "fold",
                    "type": "folding_assembly",
                    "params": specification({"family": "cube_net"}),
                }
            ],
            "metadata": {},
        }
        original = deepcopy(doc)
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as tmp:
            result = export_print_pack(doc, tmp)
            self.assertTrue(result["manifest"]["geometric_print_preflight_passed"])
            self.assertFalse(result["manifest"]["physical_fit_verified"])
            self.assertIn(
                "HINGE",
                PdfReader(Path(tmp) / "assembly-guide.pdf").pages[0].extract_text(),
            )
            self.assertTrue((Path(tmp) / "hinge-coupon.stl").is_file())
        self.assertEqual(doc, original)
