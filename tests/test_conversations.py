import json
from pathlib import Path
import tempfile
import unittest
from crate_studio.conversations import Conversations
from crate_studio.workspace_geometry import build_document
from tests.test_workspace_geometry import feature


class ConversationTests(unittest.TestCase):
    def test_restored_job_does_not_hold_progress_lock_during_native_work(self):
        from unittest.mock import patch, MagicMock
        import threading
        from crate_studio import workspace_server as ws, workspace_agent as wa

        with tempfile.TemporaryDirectory(dir="output") as folder:
            root = Path(folder)
            run = root / "studio-test"
            run.mkdir()
            (run / "proposal.json").write_text(
                json.dumps({"status": "ready", "document": {"features": []}}),
                encoding="utf-8",
            )
            store = MagicMock()
            store.read_job.return_value = {
                "id": "studio-test",
                "document_id": "cad-111111111111",
            }

            def native(*args, **kwargs):
                self.assertFalse(ws.JOBS_LOCK._is_owned())
                return {"passed": True}

            with (
                patch("crate_studio.conversations.Conversations", return_value=store),
                patch.object(wa, "RUNS", root),
                patch.dict(ws.JOBS, {}, clear=True),
                patch.object(ws, "snapshot", side_effect=native),
            ):
                router = ws.create_router(threading.RLock())
                get = next(
                    r.endpoint
                    for r in router.routes
                    if r.path == "/api/studio/jobs/{id}"
                )
                self.assertEqual(get("studio-test")["status"], "completed")

    def test_history_survives_reopen_revision_and_deduplicates(self):
        with tempfile.TemporaryDirectory(dir="output") as folder:
            root = Path(folder)
            docs = root / "documents"
            docs.mkdir()
            a, b, c = "cad-111111111111", "cad-222222222222", "cad-333333333333"
            for ident, parent in [(a, None), (b, a), (c, None)]:
                (docs / (ident + ".json")).write_text(
                    json.dumps({"parent_id": parent}), encoding="utf-8"
                )
            store = Conversations(root / "chat.sqlite3", docs)
            store.append(a, "r1", "user", {"text": "Make a box"})
            self.assertEqual(store.context(a), [])
            store.append(
                a,
                "r1",
                "assistant",
                {
                    "text": "What width?",
                    "questions": ["Width in mm?"],
                    "status": "clarify",
                },
            )
            store.append(a, "r1", "assistant", {"text": "Should not replace"})
            reopened = Conversations(root / "chat.sqlite3", docs)
            store.save_job(
                {
                    "id": "studio-example",
                    "document_id": a,
                    "status": "completed",
                    "applied_id": b,
                }
            )
            self.assertEqual(reopened.read_job("studio-example")["applied_id"], b)
            self.assertEqual(len(reopened.read(b)["messages"]), 2)
            self.assertIn("Width in mm?", reopened.context(b)[1]["content"])
            self.assertEqual(reopened.read(c)["messages"], [])
            (docs / (a + ".json")).write_text(
                json.dumps({"parent_id": b}), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                reopened.root(a)

    def test_conversation_is_given_to_planner_and_answer_does_not_edit(self):
        from unittest.mock import patch
        import os
        from crate_studio import workspace_agent as wa
        from tests.test_workspace_agent import base, response

        prior = [
            {"role": "user", "content": "Make a box"},
            {"role": "assistant", "content": "What height?"},
        ]
        answer = {
            "summary": "The height is measured along Z.",
            "status": "answer",
            "operations": [],
            "questions": [],
            "evidence": [],
        }
        with (
            tempfile.TemporaryDirectory(dir="output") as folder,
            patch.object(wa, "RUNS", Path(folder)),
            patch.object(wa, "load_env"),
            patch.dict(os.environ, {"MODEL_API_KEY": "offline"}),
            patch.object(wa.agent, "estimated_spend", return_value=0),
            patch.object(wa, "request", return_value=response(answer)) as model,
        ):
            result = wa.propose_document(
                base(),
                "What does height mean?",
                conversation_context=prior,
                use_cache=False,
            )
            self.assertEqual(result["status"], "answer")
            self.assertEqual(result["document"], base())
            self.assertEqual(
                json.loads(model.call_args.args[3]["messages"][1]["content"])[
                    "conversation"
                ],
                prior,
            )
        answer["operations"] = [{"action": "delete", "id": "box"}]
        with self.assertRaises(ValueError):
            wa.parse_plan(json.dumps(answer))

    def test_oblique_hole_is_targeted_and_through_all_tracks_size_changes(self):
        import math

        for width in (20, 30):
            features = [
                feature(
                    "a", "box", width=width, depth=20, height=20, operation="new_body"
                ),
                feature(
                    "b",
                    "box",
                    width=10,
                    depth=10,
                    height=10,
                    cx=80,
                    operation="new_body",
                ),
            ]
            original = build_document({"features": features})
            hole = feature(
                "h",
                "cut_hole",
                radius=2,
                x=0,
                y=0,
                z=10,
                direction=[1, 0, 0],
                end_condition="through_all",
                target_part_id="body_001",
            )
            result = build_document({"features": features + [hole]})
            self.assertTrue(result["checks"]["passed"])
            self.assertEqual(result["metrics"]["solid_count"], 2)
            self.assertAlmostEqual(
                original["metrics"]["volume_mm3"] - result["metrics"]["volume_mm3"],
                math.pi * 4 * width,
                places=5,
            )
            hole["params"]["direction"] = [0, 0, 0]
            self.assertFalse(
                build_document({"features": features + [hole]})["checks"]["passed"]
            )
        angled = build_document(
            {
                "features": [
                    feature("angled_plate", "box", width=80, depth=60, height=30),
                    feature(
                        "angled_hole",
                        "cut_hole",
                        radius=2,
                        x=0,
                        y=0,
                        z=15,
                        direction=[1, 0, 1],
                        end_condition="through_all",
                    ),
                ]
            }
        )
        self.assertTrue(angled["checks"]["passed"])
        self.assertAlmostEqual(
            80 * 60 * 30 - angled["metrics"]["volume_mm3"],
            math.pi * 4 * 30 * math.sqrt(2),
            places=5,
        )


if __name__ == "__main__":
    unittest.main()
