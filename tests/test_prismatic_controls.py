from copy import deepcopy
import unittest
import cadquery as cq
from crate_studio.prismatic_controls import prismatic_controls


def fixture(end_stops=True):
    guide = cq.Workplane("XY").box(14, 6, 1).translate((0, 0, -2)).val()
    if end_stops:
        for x in (-6, 6):
            guide = guide.fuse(
                cq.Workplane("XY").box(1, 6, 6).translate((x, 0, 0)).val()
            )
    key = cq.Workplane("XY").box(10.8, 4, 2).val()
    for x in (-4, 0, 4):
        key = key.cut(cq.Workplane("XY").box(2.6, 6, 4).translate((x, 0, 0)).val())
    key = key.fuse(cq.Workplane("XY").box(10.8, 1, 2).translate((0, 2.5, 0)).val())
    parts = [
        {"id": "guide", "shape": guide},
        {"id": "slider", "shape": cq.Workplane("XY").box(2, 2, 2).val()},
        {"id": "key", "shape": key},
    ]
    states = []
    pairs = []
    for label, x in [("low", -4), ("mid", 0), ("high", 4)]:
        for mode, z in [("locked", 0), ("unlocked", 5)]:
            states.append(
                {"name": f"{label}_{mode}", "values": {"slide": x, "key_lift": z}}
            )
        pairs.append(
            {
                "locked": label + "_locked",
                "unlocked": label + "_unlocked",
                "position": [x],
            }
        )
    spec = {
        "root": "guide",
        "joints": [
            {
                "id": "slide",
                "parent": "guide",
                "child": "slider",
                "type": "prismatic",
                "axis": [1, 0, 0],
                "origin": [0, 0, 0],
                "limits": [-4, 4],
            },
            {
                "id": "key_lift",
                "parent": "guide",
                "child": "key",
                "type": "prismatic",
                "axis": [0, 0, 1],
                "origin": [0, 0, 0],
                "limits": [0, 5],
            },
        ],
        "states": states,
        "connections": [],
        "samples_per_segment": 2,
    }
    target = [
        {
            "joint_ids": ["slide"],
            "joint_limits": {"slide": [-4, 4]},
            "state_pairs": pairs,
            "distance_mm": 1,
            "samples": 21,
        }
    ]
    return (
        {"features": [], "metadata": {"design_mechanism": spec}},
        {"checks": {"passed": True}, "parts": parts},
        target,
    )


class PrismaticControlTests(unittest.TestCase):
    def test_actual_locks_unlocked_travel_and_end_stops(self):
        doc, built, target = fixture()
        report = prismatic_controls(doc, built, target)
        self.assertTrue(report["passed"], report["failed_cases"])
        self.assertEqual(report["case_count"], 6)
        doc, built, target = fixture(False)
        missing = prismatic_controls(doc, built, target)
        self.assertFalse(missing["passed"])
        self.assertEqual(len(missing["failed_cases"]), 2)
        self.assertTrue(
            all(not row["within_travel"] for row in missing["failed_cases"])
        )

    def test_virtual_limits_and_named_positions_cannot_be_weakened(self):
        doc, built, target = fixture()
        doc["metadata"]["design_mechanism"]["joints"][0]["limits"][1] = 20
        with self.assertRaisesRegex(ValueError, "Retained travel limits"):
            prismatic_controls(doc, built, target)
        doc, built, target = fixture()
        weakened = deepcopy(target)
        weakened[0]["state_pairs"][0]["position"] = [-3]
        with self.assertRaisesRegex(ValueError, "positions differ"):
            prismatic_controls(doc, built, weakened)
