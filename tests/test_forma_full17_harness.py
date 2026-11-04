"""Controls for empty provider output, receipts and the strict two-call limit."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.run_forma_full17 import baseline, BASELINE_SYSTEM, linux, ROOT


class BaselineHarnessTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows-to-WSL mount conversion")
    def test_mount_path_uses_current_repository_and_drive(self):
        source = ROOT / "output" / "mount conversion test"
        expected = "/mnt/" + source.drive[0].lower() + "/" + source.as_posix()[3:]
        self.assertEqual(linux(source), expected)

    def test_mount_path_rejects_root_and_outside_repository(self):
        for source in (ROOT, ROOT.parent / "other-project", ROOT / ".." / "outside"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "project"):
                linux(source)

    def transport(self, text, ident):
        return (
            {
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 200},
            },
            {
                "id": ident,
                "model": "muse-wonder-1.0",
                "choices": [{"message": {"content": text}}],
            },
        )

    def build(self, mode, source, output, **kwargs):
        output.mkdir(parents=True, exist_ok=True)
        if not (source / "final.py").read_text():
            return {"passed": False, "error": "'part'"}
        (output / "candidate.step").write_text("test fixture, not real CAD")
        return {"passed": True}

    def test_null_response_gets_build_feedback_and_exactly_one_repair(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as temp:
            root = Path(temp)
            folder = root / "task"
            folder.mkdir()
            with patch.dict(os.environ, {"MODEL_API_KEY": "fake-harness-key"}), patch(
                "research.run_forma_full17.load_env"
            ), patch("research.run_forma_full17.wa.RUNS", root / "receipts"), patch(
                "research.run_forma_full17.wa.estimated_spend", return_value=0
            ), patch(
                "research.run_forma_full17.request",
                side_effect=[
                    self.transport(None, "a"),
                    self.transport("part = Box(1,1,1)", "b"),
                ],
            ) as request, patch(
                "research.run_forma_full17.container", side_effect=self.build
            ):
                result = baseline("Make a cube", folder, "null-case")
            self.assertEqual(result["calls"], 2)
            self.assertEqual(result["response_ids"], ["a", "b"])
            self.assertAlmostEqual(result["estimated_cost_usd"], 0.0088)
            self.assertEqual(request.call_count, 2)
            second = request.call_args.args[3]["messages"]
            self.assertEqual(second[-2]["content"], "")
            self.assertIn("actual_build_error", second[-1]["content"])
            self.assertTrue((folder / "candidate.step").exists())

    def test_resume_preserves_original_receipt_and_prevents_third_call(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as temp:
            root = Path(temp)
            folder = root / "task"
            folder.mkdir()
            receipt = root / "receipts/resume-case"
            receipt.mkdir(parents=True)
            messages = [
                {"role": "system", "content": BASELINE_SYSTEM},
                {"role": "user", "content": "Make a cube"},
            ]
            events = [
                {"kind": "reservation", "request": {"messages": messages}},
                {
                    "kind": "response",
                    "public_response": None,
                    "transport": {"http_status": 200},
                    "response_id": "original",
                    "estimated_cost_usd": 0.1,
                },
            ]
            (receipt / "events.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in events), encoding="utf8"
            )
            with patch.dict(os.environ, {"MODEL_API_KEY": "fake-harness-key"}), patch(
                "research.run_forma_full17.load_env"
            ), patch("research.run_forma_full17.wa.RUNS", root / "receipts"), patch(
                "research.run_forma_full17.wa.estimated_spend", return_value=0
            ), patch(
                "research.run_forma_full17.request",
                return_value=self.transport("part = Box(1,1,1)", "repair"),
            ) as request, patch(
                "research.run_forma_full17.container", side_effect=self.build
            ):
                result = baseline(
                    "Make a cube", folder, "resume-case", resume_empty=True
                )
                self.assertEqual(result["calls"], 2)
                self.assertAlmostEqual(result["estimated_cost_usd"], 0.1044)
                self.assertEqual(request.call_count, 1)
                with self.assertRaises(ValueError):
                    baseline("Make a cube", folder, "resume-case", resume_empty=True)
                self.assertEqual(request.call_count, 1)
            self.assertEqual(
                json.loads((receipt / "events.jsonl").read_text().splitlines()[1])[
                    "response_id"
                ],
                "original",
            )

    def test_budget_guard_precedes_network(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as temp:
            with patch.dict(os.environ, {"MODEL_API_KEY": "fake-harness-key"}), patch(
                "research.run_forma_full17.load_env"
            ), patch(
                "research.run_forma_full17.wa.RUNS", Path(temp) / "receipts"
            ), patch(
                "research.run_forma_full17.agent.CAP_USD", 25
            ), patch(
                "research.run_forma_full17.wa.estimated_spend", return_value=25
            ), patch(
                "research.run_forma_full17.request"
            ) as request:
                with self.assertRaisesRegex(ValueError, "budget"):
                    baseline("Make a cube", Path(temp), "capped")
                request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
