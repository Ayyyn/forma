"""Avoid discarding a paid valid tool batch merely because it has nine calls."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from crate_studio import design_agent as da, workspace_agent as wa


class ToolBatchTests(unittest.TestCase):
    def run_batch(self, count):
        phase = 0

        def provider(base, key, route, payload, timeout):
            nonlocal phase
            phase += 1
            strategy = {
                "alternatives": [
                    {
                        "name": "Native check",
                        "benefit": "Bounded inspection",
                        "risk": "No physical proof",
                    }
                ],
                "selected": "Native check",
                "assumptions": [],
                "steps": ["Inspect references", "Report remaining work"],
            }
            calls = [("record_strategy", strategy)] + [("feature_reference", {})] * (
                count - 1
            )
            message = (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"batch-{i}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)},
                        }
                        for i, (name, args) in enumerate(calls)
                    ],
                }
                if phase == 1
                else {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "status": "incomplete",
                            "summary": "Inspection retained; no geometry selected.",
                            "questions": [],
                        }
                    ),
                }
            )
            return {
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            }, {"id": f"batch-response-{phase}", "choices": [{"message": message}]}

        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(wa, "RUNS", Path(folder)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-secret"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", side_effect=provider),
        ):
            return da.propose_design(
                {"name": "Batch control", "features": []},
                "Inspect supported native tools",
                run_id="batch-control",
                max_turns=2,
            )

    def test_nine_valid_calls_execute_and_hard_limit_still_rejects_seventeen(self):
        accepted = self.run_batch(9)
        self.assertEqual(accepted["tool_calls"], 9)
        self.assertEqual(accepted["calls"], 2)
        self.assertEqual(
            accepted["summary"], "Inspection retained; no geometry selected."
        )
        rejected = self.run_batch(17)
        self.assertEqual(rejected["tool_calls"], 0)
        self.assertEqual(rejected["calls"], 1)
        self.assertIn("sixteen", rejected["summary"])
