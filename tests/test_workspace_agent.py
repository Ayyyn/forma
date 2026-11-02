"""Offline transport mocks only: these tests make no API requests."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crate_studio import workspace_agent as wa


def base():
    return {
        "name": "Fixture",
        "features": [
            {
                "id": "box",
                "type": "box",
                "params": {"width": 10, "depth": 20, "height": 30},
                "custom": "preserve",
            }
        ],
        "annotations": [{"note": "retained"}],
        "display": {"color": "blue"},
        "unknown": {"keep": True},
    }


def plan(operations=None, status="ready", quote="make it 40 mm tall"):
    return {
        "summary": "Proposed change",
        "status": status,
        "operations": operations or [],
        "questions": ["Which dimension?"] if status == "clarify" else [],
        "evidence": [{"quote": quote}],
    }


def response(p, rid="offline-fixture"):
    return (
        {
            "status": "received",
            "http_status": 200,
            "usage": {"prompt_tokens": 100, "completion_tokens": 100},
        },
        {
            "id": rid,
            "model": wa.MODEL,
            "choices": [{"message": {"content": json.dumps(p)}}],
        },
    )


class WorkspaceAgentTests(unittest.TestCase):
    def test_new_prompt_design_retains_brief_without_overwriting_existing_intent(self):
        instruction = "make it 40 mm tall"
        operation = {
            "action": "add",
            "feature": {
                "id": "new",
                "type": "box",
                "params": {"width": 10, "depth": 20, "height": 40},
            },
        }
        for metadata, expected in [
            ({}, instruction),
            ({"brief": "User-authored intent"}, "User-authored intent"),
        ]:
            doc = {"name": "New", "features": [], "metadata": metadata}
            result = wa.apply_plan(doc, plan([operation]), instruction)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["document"]["metadata"]["brief"], expected)
            self.assertEqual(doc["features"], [])

    def test_update_preserves_unknown_and_base(self):
        original = base()
        p = plan([{"action": "update", "id": "box", "params": {"height": 40}}])
        result = wa.apply_plan(original, p, "Please make it 40 mm tall")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["document"]["unknown"], original["unknown"])
        self.assertEqual(result["document"]["annotations"], original["annotations"])
        self.assertEqual(result["document"]["features"][0]["custom"], "preserve")
        self.assertEqual(original["features"][0]["params"]["height"], 30)
        self.assertAlmostEqual(result["result"]["metrics"]["volume_mm3"], 8000)

    def test_add_and_clarification(self):
        p = plan(
            [
                {
                    "action": "add",
                    "feature": {
                        "id": "bore",
                        "type": "cut_hole",
                        "params": {"radius": 2, "depth": 30},
                    },
                }
            ],
            quote="add a bore",
        )
        self.assertEqual(wa.apply_plan(base(), p, "add a bore")["status"], "ready")
        p = plan(status="clarify", quote="make it taller")
        self.assertEqual(wa.apply_plan(base(), p, "make it taller")["document"], base())
        p["operations"] = [{"action": "delete", "id": "box"}]
        with self.assertRaises(ValueError):
            wa.apply_plan(base(), p, "make it taller")

    def test_reject_fabricated_evidence_unsupported_params_and_asset_change(self):
        with self.assertRaises(ValueError):
            wa.apply_plan(
                base(),
                plan([{"action": "update", "id": "box", "params": {"height": 40}}]),
                "different instruction",
            )
        with self.assertRaises(ValueError):
            wa.apply_plan(
                base(),
                plan([{"action": "update", "id": "box", "params": {"exec": "bad"}}]),
                "make it 40 mm tall",
            )
        doc = base()
        doc["features"].append(
            {"id": "import", "type": "import_step", "params": {"asset_id": "original"}}
        )
        with self.assertRaises(ValueError):
            wa.apply_plan(
                doc,
                plan(
                    [
                        {
                            "action": "update",
                            "id": "import",
                            "params": {"asset_id": "other"},
                        }
                    ]
                ),
                "make it 40 mm tall",
            )

    def call_mock(self, replies, prompt="make it 40 mm tall", document=None):
        root = Path(__file__).resolve().parents[1] / "output"
        with tempfile.TemporaryDirectory(dir=root) as directory:
            with patch.object(wa, "RUNS", Path(directory)), patch.object(
                wa, "load_env"
            ), patch.dict(
                os.environ, {"MODEL_API_KEY": "offline-test-secret"}
            ), patch.object(
                wa.agent, "estimated_spend", return_value=0
            ), patch.object(
                wa, "request", side_effect=replies
            ) as transport:
                result = wa.propose_document(
                    document if document is not None else base(),
                    prompt,
                    run_id="offline-test",
                )
                ledger = (Path(directory) / "offline-test" / "events.jsonl").read_text()
                self.assertNotIn("offline-test-secret", ledger)
                return result, transport.call_args_list, ledger

    def test_one_mocked_response_and_separate_receipt(self):
        p = plan([{"action": "update", "id": "box", "params": {"height": 40}}])
        result, calls, ledger = self.call_mock([response(p)])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["response_ids"], ["offline-fixture"])
        self.assertIn("reservation", ledger)

    def test_actual_geometry_failure_feedback_then_repair(self):
        bad = plan(
            [
                {
                    "action": "add",
                    "feature": {
                        "id": "round",
                        "type": "fillet",
                        "params": {"radius": 1000},
                    },
                }
            ]
        )
        good = plan([{"action": "update", "id": "box", "params": {"height": 40}}])
        result, calls, ledger = self.call_mock(
            [response(bad, "mock-1"), response(good, "mock-2")]
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["calls"], 2)
        feedback = json.loads(calls[1].args[3]["messages"][-1]["content"])
        self.assertFalse(feedback["actual_result"]["checks"]["passed"])
        self.assertEqual(feedback["original_instruction"], "make it 40 mm tall")
        self.assertIn("never this validation feedback", feedback["evidence_rule"])
        self.assertEqual(feedback["actual_result"]["features"][-1]["status"], "error")

    def test_network_failure_is_not_success_or_retried(self):
        result, calls, _ = self.call_mock(
            [({"status": "network_or_response_error"}, None)]
        )
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["response_ids"], [])
        self.assertIn("failed", result["summary"])

    def test_enclosure_context_includes_retained_stock_for_clarification(self):
        from crate_studio.workspace_workflow import revise_enclosure

        doc = revise_enclosure(
            {"features": [], "metadata": {}},
            {
                "inner_width_mm": 90,
                "inner_depth_mm": 60,
                "inner_height_mm": 45,
                "material": "polypropylene",
                "thickness_mm": 3,
            },
            {"min_capacity_l": 0.2},
        )
        p = {
            "summary": "Stock conflict",
            "status": "clarify",
            "operations": [],
            "questions": ["Which listed stock thickness?"],
            "evidence": [],
        }
        result, calls, _ = self.call_mock(
            [response(p)],
            prompt="Use exactly 3.5 mm panels without changing stock requirements.",
            document=doc,
        )
        context = json.loads(calls[0].args[3]["messages"][1]["content"])
        self.assertNotIn(
            3.5, context["engineering_context"]["material_profile"]["stock_mm"]
        )
        self.assertIn(
            2, context["engineering_context"]["material_profiles"]["steel"]["stock_mm"]
        )
        self.assertNotIn(
            2,
            context["engineering_context"]["material_profiles"]["polypropylene"][
                "stock_mm"
            ],
        )
        self.assertEqual(
            context["engineering_context"]["requirement_binding"]["status"], "current"
        )
        self.assertEqual(result["document"], doc)
        self.assertEqual(result["status"], "clarify")


if __name__ == "__main__":
    unittest.main()
