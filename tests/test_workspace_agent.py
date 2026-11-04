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
    def test_display_color_changes_appearance_only_and_validates_body_targets(self):
        from copy import deepcopy

        source = base()
        source["metadata"] = {"native_study_targets": {"keep": True}}
        source["display"] = {
            "color": "#aaaaaa",
            "colors": {"body_001": "#ff0000"},
            "hidden_parts": ["body_001"],
            "body_names": {"body_001": "Keep"},
        }
        original = deepcopy(source)
        prompt = "change the prototype color to blue"
        result = wa.apply_plan(
            source,
            plan([{"action": "display", "color": "#0000FF"}], quote=prompt),
            prompt,
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(source, original)
        expected = deepcopy(original)
        expected["display"].update(color="#0000ff", colors={})
        self.assertEqual(result["document"], expected)
        targeted = wa.apply_plan(
            source,
            plan(
                [{"action": "display", "color": "#0000ff", "part_ids": ["body_001"]}],
                quote=prompt,
            ),
            prompt,
        )
        self.assertEqual(targeted["document"]["display"]["color"], "#aaaaaa")
        self.assertEqual(
            targeted["document"]["display"]["colors"], {"body_001": "#0000ff"}
        )
        for operation in (
            {"action": "display", "color": "blue"},
            {"action": "display", "color": "#0000ff", "material": "PLA"},
            {"action": "display", "color": "#0000ff", "part_ids": []},
            {"action": "display", "color": "#0000ff", "part_ids": None},
            {"action": "display", "color": "#0000ff", "part_ids": ["body_999"]},
            {
                "action": "display",
                "color": "#0000ff",
                "part_ids": ["body_001", "body_001"],
            },
        ):
            with self.assertRaises(ValueError):
                wa.apply_plan(source, plan([operation], quote=prompt), prompt)

    def test_quick_edit_projects_large_history_before_input_guard_without_claiming_tools(
        self,
    ):
        from copy import deepcopy

        source = base()
        source["metadata"] = {
            "brief": "Keep the mechanism",
            "native_study_targets": {"keep": [12, 24]},
            "native_study_review": {
                "reports": {
                    "failed": {
                        "passed": False,
                        "frames": ["historical evidence"] * 20000,
                    }
                }
            },
        }
        original = deepcopy(source)
        prompt = "change the prototype color to blue, preserving the geometry"
        answer = plan([{"action": "display", "color": "#0000ff"}], quote=prompt)
        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(wa, "RUNS", Path(folder)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-secret"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", return_value=response(answer)) as transport,
        ):
            result = wa.propose_document(
                source, prompt, run_id="large-history", use_cache=False
            )
            self.assertEqual(result["status"], "ready")
            self.assertEqual(transport.call_count, 1)
            payload = transport.call_args.args[3]
            if isinstance(payload, bytes):
                payload = json.loads(payload)
            context = json.loads(payload["messages"][1]["content"])
            wire = context["document"]
            self.assertEqual(wire["features"], original["features"])
            self.assertEqual(
                wire["metadata"]["native_study_targets"],
                original["metadata"]["native_study_targets"],
            )
            reports = wire["metadata"]["native_study_review"]["reports"]
            self.assertFalse(reports["index"][0]["passed"])
            self.assertIn("no report retrieval tools", reports["retrieval"])
            self.assertLess(len(json.dumps(payload).encode()), 180000)
            local = json.loads(
                (Path(folder) / "large-history/context.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(local["document"], original)
        self.assertEqual(source, original)

    def test_color_profile_is_small_and_cannot_accept_geometry_operations(self):
        prompt = "change the prototype color to blue"
        with self.assertRaises(ValueError):
            wa.validate_appearance_plan(plan([None], quote=prompt))
        for mixed in (
            "change the prototype color to blue and height to 12 mm",
            "change material to blue PLA",
            "make it 40 mm tall",
        ):
            self.assertFalse(wa.appearance_request(mixed))
        good = plan([{"action": "display", "color": "#0000ff"}], quote=prompt)
        bad = plan(
            [{"action": "update", "id": "box", "params": {"height": 999}}], quote=prompt
        )
        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(wa, "RUNS", Path(folder)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-secret"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(
                wa, "request", side_effect=[response(bad), response(good)]
            ) as transport,
        ):
            result = wa.propose_document(
                base(), prompt, run_id="appearance", use_cache=False
            )
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["document"]["features"], base()["features"])
            self.assertEqual(transport.call_count, 2)
            payload = transport.call_args_list[0].args[3]
            self.assertEqual(payload["messages"][0]["content"], wa.APPEARANCE_SYSTEM)
            self.assertLess(len(json.dumps(payload).encode()), 4000)
            events = [
                json.loads(line)
                for line in (Path(folder) / "appearance/events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            failed = [e for e in events if e["kind"] == "verification"][0]
            self.assertEqual(failed["status"], "invalid")
            self.assertIn("never geometry edits", failed["validation_error"])

    def test_long_response_deadline_reaches_transport_and_invalid_values_do_not(self):
        events = []
        with (
            patch.object(wa, "load_env"),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline-secret"}),
            patch.object(wa, "request", return_value=response(plan())) as transport,
        ):
            wa.paid_chat(
                {"max_tokens": 32768, "messages": []}, events.append, 1, timeout=600
            )
            self.assertEqual(transport.call_args.kwargs["timeout"], 600)
            self.assertEqual(
                [event["kind"] for event in events], ["reservation", "response"]
            )
            for invalid in (29, 601, True, 600.0):
                with self.assertRaisesRegex(ValueError, "bounded provider timeout"):
                    wa.paid_chat(
                        {"max_tokens": 32768}, events.append, 2, timeout=invalid
                    )
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(len(events), 2)

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
            with (
                patch.object(wa, "RUNS", Path(directory)),
                patch.object(wa, "load_env"),
                patch.dict(os.environ, {"MODEL_API_KEY": "offline-test-secret"}),
                patch.object(wa.agent, "estimated_spend", return_value=0),
                patch.object(wa, "request", side_effect=replies) as transport,
            ):
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
