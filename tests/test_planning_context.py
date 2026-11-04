from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crate_studio import workspace_agent as wa
from crate_studio import design_agent as da
from crate_studio.design_tools import DesignSession


class PlanningContextTests(unittest.TestCase):
    def test_driver_logs_full_source_separately_from_exact_wire_receipt(self):
        doc = self.document()
        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(wa, "RUNS", Path(folder)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-secret"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(
                wa,
                "request",
                return_value=(
                    {
                        "status": "received",
                        "http_status": 200,
                        "usage": {"prompt_tokens": 100, "completion_tokens": 100},
                    },
                    {
                        "id": "offline-compact",
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": json.dumps(
                                        {
                                            "status": "incomplete",
                                            "summary": "No design accepted",
                                            "questions": [],
                                        }
                                    ),
                                }
                            }
                        ],
                    },
                ),
            ) as provider,
        ):
            da.propose_design(
                doc, "Preserve exact requirements", run_id="wire", max_turns=1
            )
            events = [
                json.loads(line)
                for line in (Path(folder) / "wire/events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            local = next(e["context"] for e in events if e["kind"] == "design_context")
            self.assertEqual(local["project"], doc)
            receipt = next(e["request"] for e in events if e["kind"] == "reservation")
            self.assertEqual(receipt, provider.call_args.args[3])
            wire = json.loads(receipt["messages"][1]["content"])["project"]
            self.assertEqual(wire["features"], doc["features"])
            self.assertEqual(
                wire["metadata"]["native_study_targets"],
                doc["metadata"]["native_study_targets"],
            )
            self.assertNotIn("frames", wire["metadata"]["design_review"]["reports"])
            from crate_studio.design_checkpoint import retained_context

            self.assertEqual(retained_context("wire"), local)

    def document(self):
        return {
            "name": "Full source retained",
            "features": [
                {
                    "id": "box",
                    "type": "box",
                    "params": {"width": 76.2, "depth": 40, "height": 3},
                }
            ],
            "metadata": {
                "brief": "Preserve requirements exactly",
                "native_study_targets": {"states": {"open": {"width": 72}}},
                "design_mechanism": {
                    "states": [{"name": "open", "values": {"slide": 24}}]
                },
                "unrecognized_user_data": {"must_remain": [1, 2, 3]},
                "design_review": {
                    "unresolved": ["Failed stop"],
                    "physical_validation": False,
                    "reports": {
                        "failed": {
                            "passed": False,
                            "scope": "Sampled only",
                            "frames": [
                                {"index": i, "overlaps": ["a", "b"]}
                                for i in range(1000)
                            ],
                        }
                    },
                },
            },
        }

    def test_wire_projection_preserves_source_targets_failures_and_raw_history(self):
        doc = self.document()
        history = [
            {
                "role": "user",
                "content": json.dumps(
                    {"original_instruction": "Keep the size", "project": doc}
                ),
            },
            {
                "role": "tool",
                "content": json.dumps({"document": doc, "parts": [{"width_mm": 76.2}]}),
            },
            {
                "role": "tool",
                "content": json.dumps(
                    {
                        "historical_only": True,
                        "report": doc["metadata"]["design_review"]["reports"]["failed"],
                    }
                ),
            },
        ]
        original = deepcopy(history)
        projected = wa.planning_messages(history)
        self.assertEqual(history, original)
        self.assertEqual(wa.planning_messages(projected), projected)
        self.assertEqual(projected[2], original[2])
        reference = json.loads(projected[1]["content"])["document"][
            "document_reference"
        ]
        self.assertEqual(reference["message_index"], 0)
        self.assertEqual(reference["field"], "project")
        self.assertEqual(len(reference["sha256"]), 64)
        self.assertEqual(
            json.loads(projected[1]["content"])["parts"], [{"width_mm": 76.2}]
        )
        for message, field in [(projected[0], "project")]:
            result = json.loads(message["content"])[field]
            self.assertEqual(result["features"], doc["features"])
            for key, value in doc["metadata"].items():
                if key != "design_review":
                    self.assertEqual(result["metadata"][key], value)
            self.assertEqual(
                result["metadata"]["design_review"]["unresolved"], ["Failed stop"]
            )
            index = result["metadata"]["design_review"]["reports"]
            self.assertFalse(index["index"][0]["passed"])
            self.assertEqual(len(index["sha256"]), 64)
            self.assertLess(len(message["content"]), len(original[0]["content"]) * 0.1)

    def test_exact_old_report_is_retrievable_without_promoting_it(self):
        doc = self.document()
        # The retrieval test does not require a declared motion contract.
        doc["metadata"].pop("design_mechanism")
        with tempfile.TemporaryDirectory(dir="output") as folder:
            session = DesignSession(doc, "Inspect history", folder)
            args = {
                "candidate_id": "base",
                "review_kind": "design_review",
                "report_key": "failed",
            }
            result = session.call("inspect_retained_report", args)
            self.assertTrue(result["ok"])
            self.assertTrue(result["historical_only"])
            self.assertEqual(
                result["report"], doc["metadata"]["design_review"]["reports"]["failed"]
            )
            self.assertEqual(session.candidates["base"]["document"], doc)
            self.assertIsNone(session.finished)
            self.assertFalse(
                session.call(
                    "inspect_retained_report", {**args, "report_key": "missing"}
                )["ok"]
            )
            self.assertFalse(
                session.call(
                    "inspect_retained_report", {**args, "review_kind": "invented"}
                )["ok"]
            )
