"""Exact native trajectories: equivalent results, invalidation and ownership."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cadquery as cq

from crate_studio import mechanism_study as ms
from crate_studio.workspace_cache import cached_build, cache_clear
from crate_studio.motion_cache import native_motion_cache, ExactMotionCache
from crate_studio.workspace_geometry import build_document
from tests.test_mechanism_study import document, specification


class MotionCacheTests(unittest.TestCase):
    def setUp(self):
        cache_clear()
        native_motion_cache.clear()

    def test_identical_concurrent_requests_share_native_work_and_copy_reports(self):
        doc, spec = document(), specification()
        built = cached_build(doc)
        with patch.object(ms, "collisions", wraps=ms.collisions) as native:
            with ThreadPoolExecutor(max_workers=2) as pool:
                a, b = list(
                    pool.map(lambda _: ms.mechanism_study(doc, built, spec), range(2))
                )
            self.assertEqual(native.call_count, 9)
            self.assertEqual(a, b)
            self.assertFalse(a["passed"])
            a["frames"][4]["overlaps"].clear()
            c = ms.mechanism_study(doc, built, spec)
            self.assertTrue(c["frames"][4]["overlaps"])
            self.assertEqual(native.call_count, 9)
        self.assertEqual(native_motion_cache.info().hits, 2)

    def test_changed_sampling_pose_geometry_and_asset_bytes_miss(self):
        doc, spec = document(), specification(10)
        ms.mechanism_study(doc, cached_build(doc), spec)
        for key, value in (
            ("samples_per_segment", 5),
            ("states", specification()["states"]),
        ):
            changed = deepcopy(spec)
            changed[key] = value
            ms.mechanism_study(doc, cached_build(doc), changed)
        doc["features"][1]["params"]["cx"] = -30
        ms.mechanism_study(doc, cached_build(doc), spec)
        self.assertEqual(native_motion_cache.info().misses, 4)
        with tempfile.TemporaryDirectory(dir="output") as root:
            path = Path(root) / "shape.step"
            imported = deepcopy(doc)
            imported["features"][0] = {
                "id": "import",
                "type": "import_step",
                "params": {"asset_id": "same"},
            }
            for size in (4, 8):
                cq.exporters.export(cq.Workplane("XY").box(size, 4, 2), str(path))
                ms.mechanism_study(
                    imported, cached_build(imported, lambda _: path), spec
                )
        self.assertEqual(native_motion_cache.info().misses, 6)

    def test_direct_unowned_build_bypasses_and_large_reports_obey_memory_bound(self):
        doc = document()
        built = build_document(doc)
        for _ in range(2):
            ms.mechanism_study(doc, built, specification())
        self.assertEqual(native_motion_cache.info().entries, 0)
        small = ExactMotionCache(max_entries=1, max_bytes=40)
        small.compute("a", lambda: {"value": 1})
        small.compute("b", lambda: {"value": 2})
        self.assertEqual(small.info().entries, 1)
        small.compute("large", lambda: {"value": "x" * 100})
        self.assertEqual(small.info().entries, 1)
        self.assertLessEqual(small.info().bytes, 40)


if __name__ == "__main__":
    unittest.main()
