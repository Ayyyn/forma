"""Offline boundary checks for model proposals. No model/API calls."""

from copy import deepcopy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from crate_studio.agent import parse_plan, apply_plan
from crate_studio import agent
from crate_studio.engine import DEFAULT_SPEC, DEFAULT_REQUIREMENTS


def plan(**updates):
    return {
        **dict(
            summary="Proposed revision",
            status="ready",
            spec_patch={},
            requirements_patch={},
            optimize=False,
            questions=[],
            assumptions=[],
            evidence=[],
        ),
        **updates,
    }


class CrateAgentBoundaryTests(unittest.TestCase):
    def setUp(self):
        (Path(__file__).resolve().parents[1] / "output").mkdir(
            parents=True, exist_ok=True
        )
        self.project = {
            "spec": deepcopy(DEFAULT_SPEC),
            "requirements": deepcopy(DEFAULT_REQUIREMENTS),
        }

    def test_parse_rejects_duplicate_keys_nonfinite_and_extra_fields(self):
        raw = json.dumps(plan())
        for bad in (
            raw.replace('"ready"', '"ready", "status": "clarify"'),
            json.dumps(plan(spec_patch={"thickness_mm": float("nan")})),
            json.dumps({**plan(), "execute": "arbitrary code"}),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_plan(bad)

    def test_parse_rejects_unsupported_design_and_requirements(self):
        for candidate in (
            plan(spec_patch={"holes": 4}),
            plan(requirements_patch={"ignore_failures": True}),
            plan(optimize="true"),
            plan(status="clarify", questions=[]),
        ):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                parse_plan(json.dumps(candidate))

    def test_fenced_valid_json_can_parse(self):
        self.assertEqual(
            parse_plan("```json\n" + json.dumps(plan()) + "\n```")["status"], "ready"
        )

    def test_patch_requires_evidence_and_quote_must_exist(self):
        for evidence in (
            [],
            [{"field": "material", "quote": "steel"}],
            [{"field": "material", "quote": ""}],
        ):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                apply_plan(
                    self.project,
                    plan(spec_patch={"material": "polypropylene"}, evidence=evidence),
                    "Use polypropylene",
                )

    def test_material_revision_preserves_dimensions_and_requirements(self):
        prompt = "Use polypropylene with 8 mm sheet"
        candidate = plan(
            spec_patch={"material": "polypropylene", "thickness_mm": 8},
            evidence=[
                {"field": "material", "quote": "polypropylene"},
                {"field": "thickness_mm", "quote": "8 mm"},
            ],
        )
        before = deepcopy(self.project)
        output = apply_plan(self.project, candidate, prompt)
        for key in ("inner_width_mm", "inner_depth_mm", "inner_height_mm"):
            self.assertEqual(output["spec"][key], self.project["spec"][key])
        self.assertEqual(output["requirements"], self.project["requirements"])
        self.assertEqual(self.project, before)

    def test_clarify_never_applies_a_suggested_change(self):
        candidate = plan(
            status="clarify",
            questions=["Which plastic?"],
            spec_patch={"material": "polypropylene"},
            evidence=[{"field": "material", "quote": "plastic"}],
        )
        output = apply_plan(self.project, candidate, "Use plastic")
        self.assertEqual(output["status"], "clarify")
        self.assertEqual(output["spec"], self.project["spec"])
        self.assertEqual(output["changes"], [])

    def test_constraint_violation_is_not_ready(self):
        prompt = "Use 21 mm plywood"
        candidate = plan(
            spec_patch={"thickness_mm": 21},
            evidence=[{"field": "thickness_mm", "quote": "21 mm"}],
        )
        output = apply_plan(self.project, candidate, prompt)
        self.assertEqual(output["status"], "infeasible")
        self.assertFalse(output["result"]["passed"])

    def test_optimizer_cannot_override_explicit_thickness_patch(self):
        candidate = plan(
            spec_patch={"thickness_mm": 9},
            optimize=True,
            evidence=[{"field": "thickness_mm", "quote": "exactly 9 mm"}],
        )
        with self.assertRaises(ValueError):
            apply_plan(self.project, candidate, "Use exactly 9 mm plywood")

    def test_explicit_dimension_cannot_be_resized_away(self):
        candidate = plan(
            spec_patch={"inner_width_mm": 500},
            requirements_patch={"lock_inner_dimensions": False},
            optimize=True,
            evidence=[
                {"field": "inner_width_mm", "quote": "width 500 mm"},
                {"field": "lock_inner_dimensions", "quote": "resize"},
            ],
        )
        with self.assertRaises(ValueError):
            apply_plan(self.project, candidate, "Use width 500 mm and resize the rest")

    def test_followup_can_quote_actual_prior_user_instruction(self):
        candidate = plan(
            spec_patch={"material": "birch_plywood"},
            requirements_patch={"payload_kg": 20, "max_floor_deflection_mm": 2},
            optimize=True,
            evidence=[
                {"field": "material", "quote": "birch plywood"},
                {"field": "payload_kg", "quote": "payload 20 kg"},
                {"field": "max_floor_deflection_mm", "quote": "deflection 2 mm"},
            ],
        )
        response = {
            "id": "offline-fixture-not-live",
            "model": agent.MODEL,
            "choices": [{"message": {"content": json.dumps(candidate)}}],
        }
        transport = {
            "http_status": 200,
            "usage": {"prompt_tokens": 100, "completion_tokens": 100},
        }
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as folder, patch.object(agent, "RUNS", Path(folder)), patch.object(
            agent, "configured", return_value=True
        ), patch.object(
            agent, "request", return_value=(transport, response)
        ) as request:
            result = agent.propose(
                self.project,
                "Try birch plywood",
                context_instructions=["Screen payload 20 kg with deflection 2 mm"],
            )
            self.assertEqual(result["requirements"]["payload_kg"], 20)
            self.assertEqual(result["requirements"]["max_floor_deflection_mm"], 2)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(len(result["verification_history"]), 1)
            self.assertEqual(
                result["diagnostic_result"]["requirements"]["payload_kg"], 20
            )
            payload = request.call_args.args[3]
            self.assertEqual(
                json.loads(payload["messages"][1]["content"])[
                    "earlier_user_instructions"
                ],
                ["Screen payload 20 kg with deflection 2 mm"],
            )

    def test_rejected_stock_checks_reach_feedback_and_audit(self):
        project = {
            "spec": {**DEFAULT_SPEC, "material": "polypropylene", "thickness_mm": 8},
            "requirements": deepcopy(DEFAULT_REQUIREMENTS),
        }
        first = plan(
            requirements_patch={"payload_kg": 20, "max_floor_deflection_mm": 2},
            optimize=True,
            evidence=[
                {"field": "payload_kg", "quote": "20 kg"},
                {"field": "max_floor_deflection_mm", "quote": "2 mm"},
            ],
        )
        second = plan(status="clarify", questions=["May the material change?"])
        transport = {
            "http_status": 200,
            "usage": {"prompt_tokens": 100, "completion_tokens": 100},
        }
        responses = [
            (
                transport,
                {
                    "id": "offline-fixture-" + str(i),
                    "model": agent.MODEL,
                    "choices": [{"message": {"content": json.dumps(p)}}],
                },
            )
            for i, p in enumerate([first, second])
        ]
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1] / "output"
        ) as folder, patch.object(agent, "RUNS", Path(folder)), patch.object(
            agent, "configured", return_value=True
        ), patch.object(
            agent, "request", side_effect=responses
        ) as request:
            result = agent.propose(project, "Screen 20 kg at 2 mm")
            self.assertEqual(result["status"], "clarify")
            self.assertEqual(
                result["diagnostic_result"]["requirements"]["payload_kg"], 20
            )
            self.assertEqual(result["spec"], project["spec"])
            self.assertEqual(len(result["verification_history"]), 2)
            feedback = json.loads(
                request.call_args_list[1].args[3]["messages"][-1]["content"]
            )
            self.assertEqual(feedback["stock_search"]["status"], "infeasible")
            self.assertEqual(feedback["stock_search"]["evaluated_count"], 9)


if __name__ == "__main__":
    unittest.main()
