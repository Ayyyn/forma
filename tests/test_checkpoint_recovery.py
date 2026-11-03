import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from crate_studio import workspace_server as ws, workspace_agent as wa


class CheckpointRecoveryTests(unittest.TestCase):
    def test_reopens_only_matching_retained_context_without_model_calls(self):
        doc = {
            "name": "Recovery control",
            "features": [
                {
                    "id": "box",
                    "type": "box",
                    "params": {"width": 10, "depth": 12, "height": 4},
                }
            ],
        }
        lock = threading.RLock()
        with (
            tempfile.TemporaryDirectory(dir="output") as tmp,
            patch.object(ws, "DATA", Path(tmp)),
            patch.object(ws, "DOCS", Path(tmp) / "documents"),
            patch.object(wa, "RUNS", Path(tmp) / "runs"),
            patch.object(
                wa,
                "request",
                side_effect=AssertionError("Recovery must not call a model"),
            ),
        ):
            saved = ws.save_document(doc, lock, include_drawing=False)
            folder = wa.RUNS / "retained-control"
            folder.mkdir(parents=True)
            proposal = {
                "status": "incomplete",
                "run_id": "retained-control",
                "has_checkpoint": True,
                "summary": "A native repair remains incomplete.",
                "questions": [],
            }
            (folder / "proposal.json").write_text(
                json.dumps(proposal), encoding="utf-8"
            )
            context = {
                "original_instruction": "Repair native geometry",
                "project": saved["document"],
                "selection": {"feature_id": "box", "topology_ids": []},
            }

            def write_context():
                event = {
                    "kind": "reservation",
                    "request": {
                        "messages": [{"role": "user", "content": json.dumps(context)}]
                    },
                }
                (folder / "events.jsonl").write_text(
                    json.dumps(event) + "\n", encoding="utf-8"
                )

            write_context()
            endpoint = next(
                r.endpoint
                for r in ws.create_router(lock).routes
                if r.path == "/api/studio/checkpoints/{id}"
            )
            recovered = endpoint("retained-control", saved["id"])
            self.assertEqual(recovered["proposal"], proposal)
            self.assertEqual(recovered["prompt"], "Repair native geometry")
            self.assertEqual(recovered["selection"]["feature_id"], "box")
            failed = wa.RUNS / "failed-before-request"
            failed.mkdir()
            failed_proposal = {
                **proposal,
                "run_id": failed.name,
                "continuation": {"source_run_id": folder.name},
            }
            (failed / "proposal.json").write_text(
                json.dumps(failed_proposal), encoding="utf-8"
            )
            (failed / "events.jsonl").write_text(
                json.dumps({"kind": "tool_replay"}) + "\n", encoding="utf-8"
            )
            self.assertEqual(
                endpoint(failed.name, saved["id"])["prompt"],
                context["original_instruction"],
            )
            failed_proposal["continuation"]["source_run_id"] = failed.name
            (failed / "proposal.json").write_text(
                json.dumps(failed_proposal), encoding="utf-8"
            )
            with self.assertRaises(HTTPException) as error:
                endpoint(failed.name, saved["id"])
            self.assertEqual(error.exception.status_code, 409)
            changed = {**doc, "name": "Changed source"}
            child = ws.save_document(changed, lock, saved["id"], include_drawing=False)
            with self.assertRaises(HTTPException) as error:
                endpoint("retained-control", child["id"])
            self.assertEqual(error.exception.status_code, 409)
            context["selection"]["topology_ids"] = ["face-1"]
            write_context()
            with self.assertRaises(HTTPException) as error:
                endpoint("retained-control", saved["id"])
            self.assertEqual(error.exception.status_code, 409)
