"""Actual CAD tools with mocked provider replies; no paid requests."""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crate_studio import design_agent as da, workspace_agent as wa
from crate_studio.design_tools import DesignSession, review_state, review_identity
from tests.test_mechanism_study import document, specification

BRIEF = "Create a 30 by 20 mm plate, 2 mm thick with a 4 mm through hole."


def plate_plan():
    return {
        "summary": "Editable plate",
        "status": "ready",
        "questions": [],
        "evidence": [{"quote": BRIEF}],
        "operations": [
            {
                "action": "add",
                "feature": {
                    "id": "plate",
                    "type": "box",
                    "params": {"width": 30, "depth": 20, "height": 2},
                },
            },
            {
                "action": "add",
                "feature": {
                    "id": "hole",
                    "type": "cut_hole",
                    "params": {"radius": 2, "end_condition": "through_all"},
                },
            },
        ],
    }


def finish(ident):
    return {
        "candidate_id": ident,
        "summary": "Native editable 2 mm plate with centered through hole; geometry proposal.",
        "alternatives": ["A solid plate would miss the requested hole."],
        "assumptions": ["Hole centred because its position was unspecified."],
        "unresolved": ["Material, printer fit and load capacity are not verified."],
        "visual_review": "The four views show a thin rectangular plate with a central circular opening and consistent proportions.",
    }


class DesignToolTests(unittest.TestCase):
    def test_draft_interference_is_computed_once_and_blocks_wasted_sweep(self):
        from crate_studio import folding

        doc = document()
        doc["features"][1]["params"]["cx"] = 0
        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            folding, "collisions", wraps=folding.collisions
        ) as intersections:
            session = DesignSession(doc, "Inspect", directory)
            draft = session.call(
                "draft_candidate",
                {
                    "base_candidate_id": "base",
                    "plan": {
                        "summary": "Retained diagnostic geometry",
                        "status": "ready",
                        "operations": [],
                        "questions": [],
                        "evidence": [],
                    },
                },
            )
            self.assertFalse(draft["interference_screen"]["passed"])
            self.assertTrue(draft["interference_screen"]["overlaps"][0]["bounds_mm"])
            before = intersections.call_count
            ident = draft["candidate_id"]
            check = session.call("check_interference", {"candidate_id": ident})
            self.assertFalse(check["passed"])
            self.assertTrue(check["native_work_reused"])
            self.assertEqual(intersections.call_count, before)
            swept = session.call(
                "check_motion", {"candidate_id": ident, "spec": specification()}
            )
            self.assertFalse(swept["ok"])
            self.assertIn("Default source pose", swept["error"])
            self.assertEqual(intersections.call_count, before)

    def test_review_identity_survives_numeric_roundtrip_and_fold_default_expansion(
        self,
    ):
        from crate_studio.workspace_server import normalize_document

        doc = {
            "name": "Fold",
            "features": [
                {
                    "id": "f",
                    "type": "folding_assembly",
                    "params": {"family": "cube_net", "panel_width": 40.0},
                }
            ],
        }
        normalized = normalize_document(doc)
        self.assertEqual(review_identity(doc), review_identity(normalized))
        normalized["features"][0]["params"]["panel_width"] = 40
        self.assertEqual(review_identity(doc), review_identity(normalized))
        normalized["features"][0]["params"]["panel_width"] = 41
        self.assertNotEqual(review_identity(doc), review_identity(normalized))

    def test_repeated_tools_reuse_exact_work_but_restore_failed_report(self):
        with tempfile.TemporaryDirectory(dir="output") as directory:
            session = DesignSession(document(), "inspect motion", directory)
            a = {"candidate_id": "base", "spec": specification()}
            b = {"candidate_id": "base", "spec": specification(10)}
            self.assertFalse(session.call("check_motion", a)["passed"])
            self.assertTrue(session.call("check_motion", b)["passed"])
            self.assertFalse(session.call("check_motion", a)["passed"])
            self.assertTrue(session.events[-1]["cache_hit"])
            self.assertFalse(session.reports["base"]["motion"]["passed"])
            self.assertFalse(session.call("shell", {"command": "anything"})["ok"])
            self.assertFalse(
                session.call("inspect_project", {"candidate_id": "base", "extra": 1})[
                    "ok"
                ]
            )

    def test_native_exports_and_image_delivery_gate_before_finish(self):
        doc = {"name": "New", "features": []}
        with tempfile.TemporaryDirectory(dir="output") as directory:
            session = DesignSession(doc, BRIEF, directory)
            draft = session.call(
                "draft_candidate", {"base_candidate_id": "base", "plan": plate_plan()}
            )
            self.assertEqual(draft["status"], "ready")
            ident = draft["candidate_id"]
            self.assertFalse(session.call("finish_design", finish(ident))["ok"])
            self.assertTrue(
                session.call("check_interference", {"candidate_id": ident})["passed"]
            )
            self.assertTrue(
                session.call("verify_exports", {"candidate_id": ident})["passed"]
            )
            self.assertTrue(
                session.call("render_views", {"candidate_id": ident})["rendered"]
            )
            self.assertFalse(session.call("finish_design", finish(ident))["ok"])
            session.acknowledge_views(ident)
            self.assertTrue(session.call("finish_design", finish(ident))["ok"])
            self.assertFalse(session.finished["design_review"]["physical_validation"])
            self.assertEqual(
                review_state(session.finished["document"])["status"], "current"
            )
            self.assertEqual(doc["features"], [])
            source = json.loads(
                (Path(directory) / ident / "exports/workspace.json").read_text()
            )
            self.assertEqual(
                source["features"], session.finished["document"]["features"]
            )
            session.finished["document"]["features"][0]["params"]["height"] = 3
            from crate_studio.workspace_workflow import geometry_signature

            self.assertNotEqual(
                geometry_signature(session.finished["document"]),
                session.finished["design_review"]["geometry_signature"],
            )
            self.assertEqual(
                review_state(session.finished["document"])["status"], "stale"
            )

    def test_targeted_rigid_component_operations_preserve_other_bodies(self):
        from crate_studio.workspace_cache import cached_build

        doc = {
            "features": [
                {
                    "id": "a",
                    "type": "box",
                    "params": {"width": 10, "depth": 10, "height": 2},
                },
                {
                    "id": "b",
                    "type": "box",
                    "params": {
                        "width": 10,
                        "depth": 10,
                        "height": 2,
                        "cx": 30,
                        "operation": "new_body",
                    },
                },
                {
                    "id": "wall",
                    "type": "box",
                    "params": {
                        "width": 2,
                        "depth": 10,
                        "height": 10,
                        "cx": 4,
                        "z": 1,
                        "operation": "add",
                        "target_part_id": "body_001",
                    },
                },
                {
                    "id": "hole",
                    "type": "cut_hole",
                    "params": {
                        "radius": 1,
                        "end_condition": "through_all",
                        "target_part_id": "body_002",
                        "x": 30,
                    },
                },
            ]
        }
        result = cached_build(doc)
        self.assertTrue(result["checks"]["passed"])
        self.assertEqual(len(result["parts"]), 2)
        self.assertAlmostEqual(result["parts"][0]["shape"].Volume(), 380)
        self.assertAlmostEqual(
            result["parts"][1]["shape"].Volume(), 200 - 2 * 3.141592653589793
        )
        self.assertTrue(result["parts"][0]["shape"].isInside((0, 0, 1)))
        self.assertFalse(result["parts"][1]["shape"].isInside((30, 0, 1)))
        doc["features"][2]["params"]["target_part_id"] = "body_099"
        self.assertFalse(cached_build(doc)["checks"]["passed"])

    def test_selected_union_does_not_fuse_unselected_body(self):
        from crate_studio.workspace_cache import cached_build

        doc = {
            "features": [
                {
                    "id": "a",
                    "type": "box",
                    "params": {"width": 10, "depth": 10, "height": 2},
                },
                {
                    "id": "b",
                    "type": "box",
                    "params": {
                        "width": 10,
                        "depth": 10,
                        "height": 2,
                        "cx": 30,
                        "operation": "new_body",
                    },
                },
                {
                    "id": "c",
                    "type": "box",
                    "params": {
                        "width": 2,
                        "depth": 10,
                        "height": 10,
                        "cx": 4,
                        "z": 1,
                        "operation": "new_body",
                    },
                },
                {
                    "id": "join",
                    "type": "union",
                    "params": {"part_ids": ["body_001", "body_003"]},
                },
            ]
        }
        result = cached_build(doc)
        self.assertTrue(result["checks"]["passed"])
        self.assertEqual(len(result["parts"]), 2)
        self.assertAlmostEqual(result["parts"][0]["shape"].Volume(), 380)
        self.assertAlmostEqual(result["parts"][1]["shape"].Volume(), 200)


class DesignAgentTests(unittest.TestCase):
    def test_inspection_only_run_gets_construction_hint_without_losing_tools(self):
        phase = 0

        def provider(base, key, route, payload, timeout):
            nonlocal phase
            phase += 1
            hints = [
                m
                for m in payload["messages"]
                if isinstance(m.get("content"), str)
                and m["content"].startswith("Progress check:")
            ]
            if phase == 1:
                calls = [
                    (
                        "record_strategy",
                        {
                            "alternatives": [
                                {
                                    "name": "Plate",
                                    "benefit": "Direct editable construction",
                                    "risk": "Unqualified fit",
                                }
                            ],
                            "selected": "Plate",
                            "assumptions": [],
                            "steps": ["Construct one plate", "Inspect native geometry"],
                        },
                    )
                ] + [("feature_reference", {}) for _ in range(5)]
            elif phase == 2:
                self.assertEqual(len(hints), 1)
                self.assertIn("2 model turns remaining", hints[0]["content"])
                names = {t["function"]["name"] for t in payload["tools"]}
                self.assertIn("probe_translation", names)
                self.assertIn("draft_candidate", names)
                self.assertIn(BRIEF, payload["messages"][1]["content"])
                calls = [
                    (
                        "draft_candidate",
                        {"base_candidate_id": "base", "plan": plate_plan()},
                    )
                ]
            else:
                self.assertEqual(hints, [])
                calls = []
            message = (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"progress-{phase}-{i}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)},
                        }
                        for i, (name, args) in enumerate(calls)
                    ],
                }
                if calls
                else {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "status": "incomplete",
                            "summary": "Partial CAD retained; export and visual checks remain.",
                            "questions": [],
                        }
                    ),
                }
            )
            return {
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            }, {"id": f"progress-model-{phase}", "choices": [{"message": message}]}

        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            wa, "RUNS", Path(directory)
        ), patch.object(wa, "load_env"), patch.dict(
            os.environ, {"MODEL_API_KEY": "offline-secret"}
        ), patch.object(
            wa.agent, "estimated_spend", return_value=0
        ), patch.object(
            wa, "request", side_effect=provider
        ):
            result = da.propose_design(
                {"name": "New", "features": []},
                BRIEF,
                run_id="progress-control",
                max_turns=3,
            )
            self.assertEqual(result["status"], "incomplete")
            candidates = json.loads(
                (Path(directory) / "progress-control/candidates.json").read_text()
            )
            self.assertEqual(len(candidates), 2)
            self.assertFalse(any(c.get("design_review") for c in candidates.values()))

    def test_checkpoint_revalidates_tools_and_finishes_with_one_new_model_response(
        self,
    ):
        phase, candidate_id = 0, None

        def provider(base, key, route, payload, timeout):
            nonlocal phase, candidate_id
            phase += 1
            if phase == 1:
                tools = [
                    (
                        "record_strategy",
                        {
                            "alternatives": [
                                {
                                    "name": "Plate",
                                    "benefit": "Direct editable geometry",
                                    "risk": "Fit unknown",
                                }
                            ],
                            "selected": "Plate",
                            "assumptions": [],
                            "steps": [
                                "Create plate and hole",
                                "Verify actual geometry",
                            ],
                        },
                    )
                ]
            elif phase == 2:
                tools = [
                    (
                        "draft_candidate",
                        {"base_candidate_id": "base", "plan": plate_plan()},
                    )
                ]
            elif phase == 3:
                outputs = [
                    json.loads(m["content"])
                    for m in payload["messages"]
                    if m["role"] == "tool"
                ]
                candidate_id = outputs[-1]["candidate_id"]
                tools = [
                    (name, {"candidate_id": candidate_id})
                    for name in ("check_interference", "render_views", "verify_exports")
                ]
            elif phase == 4:
                self.assertTrue(
                    any(
                        isinstance(m.get("content"), list)
                        and any(p.get("type") == "image_url" for p in m["content"])
                        for m in payload["messages"]
                    )
                )
                tools = [("finish_design", finish(candidate_id))]
            else:
                self.fail("Unexpected provider request")
            return {
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            }, {
                "id": f"checkpoint-model-{phase}",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"checkpoint-call-{phase}-{i}",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": json.dumps(args),
                                    },
                                }
                                for i, (name, args) in enumerate(tools)
                            ],
                        }
                    }
                ],
            }

        doc = {"name": "New", "features": []}
        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            wa, "RUNS", Path(directory)
        ), patch.object(wa, "load_env"), patch.dict(
            os.environ, {"MODEL_API_KEY": "offline-secret"}
        ), patch.object(
            wa.agent, "estimated_spend", return_value=0
        ), patch.object(
            wa, "request", side_effect=provider
        ):
            first = da.propose_design(
                doc, BRIEF, run_id="checkpoint-first", max_turns=3
            )
            self.assertEqual(first["status"], "incomplete")
            self.assertTrue(first["has_checkpoint"])
            with self.assertRaises(ValueError):
                da.propose_design(
                    {"name": "Changed source", "features": []},
                    BRIEF,
                    run_id="checkpoint-wrong",
                    resume_from="checkpoint-first",
                )
            second = da.propose_design(
                doc,
                BRIEF,
                run_id="checkpoint-second",
                max_turns=2,
                resume_from="checkpoint-first",
            )
            self.assertEqual(second["status"], "ready")
            self.assertEqual(second["calls"], 1)
            self.assertEqual(second["response_ids"], ["checkpoint-model-4"])
            self.assertEqual(
                second["continuation"]["source_response_ids"], first["response_ids"]
            )
            self.assertEqual(second["new_tool_calls"], 1)
            self.assertGreater(second["checkpoint_revalidation_s"], 0)
            self.assertGreaterEqual(
                second["elapsed_s"], second["checkpoint_revalidation_s"]
            )
            ledger = [
                json.loads(line)
                for line in (Path(directory) / "checkpoint-second/events.jsonl")
                .read_text()
                .splitlines()
            ]
            self.assertEqual(sum(e["kind"] == "response" for e in ledger), 1)
            replays = [e for e in ledger if e["kind"] == "tool_replay"]
            self.assertEqual(len(replays), 5)
            self.assertTrue(all(e["budget_charge_usd"] == 0 for e in replays))
            self.assertEqual(review_state(second["document"])["status"], "current")

    def test_studio_routes_tools_mode_separately_and_applies_idempotently(self):
        import threading
        import time
        from crate_studio import workspace_server as ws
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            ws.PromptBody(document_id="fake", prompt="test", agent_mode="invented")

        def proposal(doc, prompt, **kwargs):
            value = wa.apply_plan(doc, plate_plan(), prompt)
            value.update(
                model=wa.MODEL,
                run_id=kwargs["run_id"],
                response_ids=["offline-mode"],
                calls=1,
                estimated_cost_usd=0,
            )
            return value

        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            ws, "DATA", Path(directory)
        ), patch.object(ws, "DOCS", Path(directory) / "documents"), patch.object(
            ws, "JOBS", {}
        ), patch.object(
            wa.agent, "configured", return_value=True
        ), patch.object(
            da, "propose_design", side_effect=proposal
        ) as design, patch.object(
            wa,
            "propose_document",
            return_value={
                "status": "clarify",
                "summary": "Fixture clarification",
                "questions": ["Which dimension?"],
                "document": {"name": "New", "features": []},
            },
        ) as quick:
            routes = {
                r.path: r.endpoint for r in ws.create_router(threading.RLock()).routes
            }
            original = routes["/api/studio/documents"](
                ws.SaveBody(document={"name": "New", "features": []})
            )
            args = {"document_id": original["id"], "prompt": BRIEF}
            first = routes["/api/studio/agent"](
                ws.PromptBody(**args, agent_mode="tools")
            )
            get = routes["/api/studio/jobs/{id}"]
            for _ in range(100):
                if get(first["id"])["status"] in ("completed", "failed"):
                    break
                time.sleep(0.01)
            self.assertEqual(get(first["id"])["status"], "completed")
            duplicate = routes["/api/studio/agent"](
                ws.PromptBody(**args, agent_mode="tools")
            )
            self.assertEqual(first["id"], duplicate["id"])
            apply = routes["/api/studio/proposals/{id}/apply"]
            a, b = apply(first["id"]), apply(first["id"])
            self.assertEqual(a["id"], b["id"])
            self.assertEqual(a["metrics"]["size_mm"], [30, 20, 2])
            other = routes["/api/studio/agent"](
                ws.PromptBody(**args, agent_mode="standard")
            )
            self.assertNotEqual(other["id"], first["id"])
            for _ in range(100):
                if get(other["id"])["status"] in ("completed", "failed"):
                    break
                time.sleep(0.01)
            self.assertEqual(design.call_count, 1)
            self.assertEqual(quick.call_count, 1)

    def test_actual_tools_repair_failure_then_review_image_and_finish(self):
        stage, ids = 0, []
        payloads = []

        def provider(base, key, route, payload, timeout):
            nonlocal stage
            payloads.append(deepcopy(payload))
            stage += 1
            tools = []
            if stage == 1:
                tools = [
                    ("inspect_project", {"candidate_id": "base"}),
                    (
                        "record_strategy",
                        {
                            "alternatives": [
                                {
                                    "name": "Extruded plate",
                                    "benefit": "Direct editable dimensions",
                                    "risk": "Physical load unknown",
                                }
                            ],
                            "selected": "Extruded plate",
                            "assumptions": [],
                            "steps": [
                                "Build plate and bore",
                                "Inspect, verify and review",
                            ],
                        },
                    ),
                ]
            elif stage == 2:
                bad = plate_plan()
                bad["operations"].append(
                    {
                        "action": "add",
                        "feature": {
                            "id": "bad",
                            "type": "fillet",
                            "params": {"radius": 1000},
                        },
                    }
                )
                tools = [
                    ("draft_candidate", {"base_candidate_id": "base", "plan": bad})
                ]
            elif stage == 3:
                tools = [
                    (
                        "draft_candidate",
                        {"base_candidate_id": "base", "plan": plate_plan()},
                    )
                ]
            elif stage == 4:
                results = [
                    json.loads(m["content"])
                    for m in payload["messages"]
                    if m["role"] == "tool"
                ]
                ids.append(results[-1]["candidate_id"])
                tools = [
                    (name, {"candidate_id": ids[-1]})
                    for name in ("check_interference", "verify_exports", "render_views")
                ]
            elif stage == 5:
                self.assertTrue(
                    any(
                        isinstance(m.get("content"), list)
                        and any(p.get("type") == "image_url" for p in m["content"])
                        for m in payload["messages"]
                    )
                )
                tools = [("finish_design", finish(ids[-1]))]
            else:
                self.fail("Unexpected extra provider request")
            calls = [
                {
                    "id": f"call-{stage}-{i}",
                    "type": "function",
                    "function": {"name": n, "arguments": json.dumps(a)},
                }
                for i, (n, a) in enumerate(tools)
            ]
            return {
                "status": "received",
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            }, {
                "id": f"mock-{stage}",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": calls,
                        }
                    }
                ],
            }

        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            wa, "RUNS", Path(directory)
        ), patch.object(wa, "load_env"), patch.dict(
            os.environ, {"MODEL_API_KEY": "offline-secret"}
        ), patch.object(
            wa.agent, "estimated_spend", return_value=0
        ), patch.object(
            wa, "request", side_effect=provider
        ):
            result = da.propose_design(
                {"name": "New", "features": []},
                BRIEF,
                run_id="mock-design",
                max_turns=6,
            )
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["calls"], 5)
            self.assertEqual(result["tool_calls"], 8)
            self.assertEqual(result["result"]["metrics"]["size_mm"], [30, 20, 2])
            self.assertTrue(result["design_review"]["reports"]["exports"]["passed"])
            self.assertFalse(result["design_review"]["locking_verified"])
            ledger = (Path(directory) / "mock-design/events.jsonl").read_text()
            self.assertNotIn("offline-secret", ledger)
            self.assertIn('"status": "invalid"', ledger)
            self.assertEqual(ledger.count('"kind": "reservation"'), 5)

    def test_budget_guard_stops_before_transport(self):
        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            wa, "RUNS", Path(directory)
        ), patch.object(wa, "load_env"), patch.dict(
            os.environ, {"MODEL_API_KEY": "offline-secret"}
        ), patch.object(
            wa.agent, "estimated_spend", return_value=wa.agent.CAP_USD
        ), patch.object(
            wa, "request"
        ) as transport:
            result = da.propose_design(
                {"name": "New", "features": []}, BRIEF, run_id="budget"
            )
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(result["calls"], 0)
            transport.assert_not_called()

    def test_reasoning_only_response_is_not_forwarded_as_invalid_assistant(self):
        payloads = []

        def provider(base, key, route, payload, timeout):
            payloads.append(deepcopy(payload))
            message = (
                {"role": "assistant", "content": None}
                if len(payloads) == 1
                else {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "status": "incomplete",
                            "summary": "Still unresolved; retain the design requirements.",
                            "questions": [],
                        }
                    ),
                }
            )
            return {
                "http_status": 200,
                "usage": {"prompt_tokens": 100, "completion_tokens": 4096},
            }, {
                "id": "mock-empty",
                "choices": [{"message": message, "finish_reason": "length"}],
            }

        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            wa, "RUNS", Path(directory)
        ), patch.object(wa, "load_env"), patch.dict(
            os.environ, {"MODEL_API_KEY": "offline-secret"}
        ), patch.object(
            wa.agent, "estimated_spend", return_value=0
        ), patch.object(
            wa, "request", side_effect=provider
        ):
            result = da.propose_design(
                {"name": "New", "features": []},
                BRIEF,
                run_id="empty-recovery",
                max_turns=3,
            )
            self.assertEqual(result["status"], "incomplete")
            self.assertEqual(len(payloads), 2)
            self.assertEqual(payloads[-1]["max_tokens"], 8192)
            self.assertFalse(
                any(
                    m["role"] == "assistant"
                    and not m.get("content")
                    and not m.get("tool_calls")
                    for m in payloads[-1]["messages"]
                )
            )

    def test_transient_provider_rejection_retries_once_without_replaying_tools(self):
        replies = [
            ({"http_status": 503, "status": "http_error"}, None),
            (
                {
                    "http_status": 200,
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                },
                {
                    "id": "recovered",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "status": "incomplete",
                                        "summary": "No geometry was selected in this offline fixture.",
                                        "questions": [],
                                    }
                                ),
                            }
                        }
                    ],
                },
            ),
        ]
        with tempfile.TemporaryDirectory(dir="output") as directory, patch.object(
            wa, "RUNS", Path(directory)
        ), patch.object(wa, "load_env"), patch.dict(
            os.environ, {"MODEL_API_KEY": "offline-secret"}
        ), patch.object(
            wa.agent, "estimated_spend", return_value=0
        ), patch.object(
            wa, "request", side_effect=replies
        ) as transport:
            result = da.propose_design(
                {"name": "New", "features": []},
                BRIEF,
                run_id="transient-recovery",
                max_turns=3,
            )
            self.assertEqual(result["calls"], 2)
            self.assertEqual(result["response_ids"], ["recovered"])
            payloads = [call.args[3] for call in transport.call_args_list]
            self.assertEqual(payloads[0]["messages"], payloads[1]["messages"])
            self.assertEqual(result["tool_calls"], 0)


if __name__ == "__main__":
    unittest.main()
