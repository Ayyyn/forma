"""Requirements must never inherit a passing result after geometry changes."""

from copy import deepcopy
import threading
import unittest
from unittest.mock import patch

from crate_studio.engine import DEFAULT_SPEC, DEFAULT_REQUIREMENTS, evaluate
from crate_studio.workspace_requirements import enclosure_features, requirement_state
from crate_studio.workspace_server import DEFAULT_DOCUMENT, snapshot, projected, built


class RequirementBindingTests(unittest.TestCase):
    def setUp(self):
        self.doc = {
            "features": enclosure_features(evaluate(DEFAULT_SPEC)["panels"]),
            "metadata": {
                "source_crate_id": "fixture",
                "source_spec": dict(DEFAULT_SPEC),
                "source_requirements": dict(DEFAULT_REQUIREMENTS),
            },
        }

    def test_current_checks_are_recomputed(self):
        self.assertEqual(requirement_state(self.doc)["status"], "current")
        self.doc["metadata"]["source_requirements"]["max_mass_kg"] = 0.01
        actual = requirement_state(self.doc)
        self.assertEqual(actual["status"], "current")
        self.assertFalse(actual["passed"])

    def test_geometry_mutations_invalidate_and_restore(self):
        for mutation in ("resize", "suppress", "delete", "append", "move"):
            with self.subTest(mutation=mutation):
                doc = deepcopy(self.doc)
                if mutation == "resize":
                    doc["features"][0]["params"]["width"] += 1
                if mutation == "suppress":
                    doc["features"][0]["suppressed"] = True
                if mutation == "delete":
                    doc["features"].pop()
                if mutation == "append":
                    doc["features"].append(deepcopy(doc["features"][0]))
                if mutation == "move":
                    doc["features"][0]["params"]["cx"] += 1
                actual = requirement_state(doc)
                self.assertEqual(actual["status"], "stale")
                self.assertEqual(actual["checks"], [])
                self.assertNotIn("passed", actual)
        self.assertEqual(requirement_state(self.doc)["status"], "current")

    def test_presentation_edits_preserve_qualification(self):
        self.doc["features"][0]["name"] = "Renamed floor"
        self.doc["display"] = {"colors": {"body_001": "#ff0000"}}
        self.doc["annotations"] = [{"text": "Review note"}]
        self.assertEqual(requirement_state(self.doc)["status"], "current")

    def test_missing_or_invalid_contract_is_stale(self):
        del self.doc["metadata"]["source_spec"]
        self.assertEqual(requirement_state(self.doc)["status"], "stale")
        self.assertEqual(requirement_state({})["status"], "unbound")

    def test_snapshot_exposes_current_then_stale_contract(self):
        lock = threading.RLock()
        current = snapshot(self.doc, lock)
        self.assertEqual(current["requirements_state"]["status"], "current")
        self.assertTrue(
            any(c["id"] == "requirement_capacity" for c in current["checks"])
        )
        self.doc["features"][0]["params"]["width"] += 1
        changed = snapshot(self.doc, lock)
        self.assertTrue(changed["passed"])
        self.assertEqual(changed["requirements_state"]["status"], "stale")
        self.assertFalse(
            any(c["id"].startswith("requirement_") for c in changed["checks"])
        )
        self.assertEqual(
            next(c for c in changed["checks"] if c["id"] == "crate_scope")["status"],
            "stale",
        )

    def test_drawing_cache_reuses_projection_but_updates_notes(self):
        built.cache_clear()
        projected.cache_clear()
        doc = deepcopy(DEFAULT_DOCUMENT)
        lock = threading.RLock()
        from crate_studio.workspace_drawing import drawing_svg

        with patch(
            "crate_studio.workspace_server.drawing_svg", wraps=drawing_svg
        ) as render:
            a = snapshot(doc, lock)
            b = snapshot(doc, lock)
            self.assertEqual(render.call_count, 1)
            self.assertEqual(a["drawing_svg"], b["drawing_svg"])
            doc["annotations"] = [
                {
                    "id": "note1",
                    "type": "text",
                    "text": "Changed note",
                    "x": 50,
                    "y": 520,
                }
            ]
            updated = snapshot(doc, lock)
            self.assertEqual(render.call_count, 2)
            self.assertIn("Changed note", updated["drawing_svg"])

    def test_brief_and_display_edits_reuse_geometry_and_projection(self):
        built.cache_clear()
        projected.cache_clear()
        doc = deepcopy(DEFAULT_DOCUMENT)
        lock = threading.RLock()
        original = snapshot(doc, lock)
        misses = built.cache_info().misses
        drawing_misses = projected.cache_info().misses
        doc["metadata"]["brief"] = "New project context"
        doc["display"]["body_names"] = {"body_001": "Named body"}
        changed = snapshot(doc, lock)
        self.assertEqual(built.cache_info().misses, misses)
        self.assertEqual(projected.cache_info().misses, drawing_misses)
        self.assertEqual(changed["geometry"]["parts"][0]["name"], "Named body")
        self.assertNotEqual(original["geometry"]["parts"][0]["name"], "Named body")


if __name__ == "__main__":
    unittest.main()
