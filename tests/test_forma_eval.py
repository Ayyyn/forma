"""Scoring controls: right answers pass and preserved-state violations fail."""

from copy import deepcopy
import unittest
from research.run_forma_eval import FROZEN, load, revision_score, verify_freeze


class EvaluationControls(unittest.TestCase):
    def test_freeze_hashes_and_task_counts(self):
        verify_freeze()
        self.assertEqual(len(load(FROZEN / "revision-tasks.json")), 20)
        self.assertEqual(len(load(FROZEN / "public-tasks.json")), 11)

    def test_expected_answers_pass(self):
        for task in load(FROZEN / "revision-tasks.json"):
            with self.subTest(task=task["id"]):
                doc = deepcopy(task["expected"].get("document", task["document"]))
                if task["kind"] == "add_hole":
                    doc["features"].append(
                        {
                            "id": "generated",
                            "type": "cut_hole",
                            "name": "Center hole",
                            "params": {
                                "radius": 3,
                                "x": 0,
                                "y": 0,
                                "z": -1,
                                "depth": 12,
                            },
                            "suppressed": False,
                        }
                    )
                proposal = {
                    "status": task["expected"]["status"],
                    "document": doc,
                    "questions": ["Please clarify"],
                }
                self.assertTrue(revision_score(task, proposal, None)["passed"])

    def test_wrong_geometry_and_unrequested_change_fail(self):
        task = load(FROZEN / "revision-tasks.json")[0]
        doc = deepcopy(task["expected"]["document"])
        doc["features"][0]["params"]["width"] = 159
        self.assertFalse(
            revision_score(task, {"status": "ready", "document": doc}, None)["passed"]
        )
        doc = deepcopy(task["expected"]["document"])
        doc["features"][2]["params"]["radius"] = 9
        self.assertFalse(
            revision_score(task, {"status": "ready", "document": doc}, None)["passed"]
        )

    def test_clarification_cannot_mutate_document(self):
        task = next(
            t for t in load(FROZEN / "revision-tasks.json") if t["kind"] == "clarify"
        )
        doc = deepcopy(task["document"])
        doc["name"] = "Unexpected change"
        self.assertFalse(
            revision_score(
                task,
                {"status": "clarify", "document": doc, "questions": ["Why?"]},
                None,
            )["passed"]
        )


if __name__ == "__main__":
    unittest.main()
