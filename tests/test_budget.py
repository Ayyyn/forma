"""No provider calls: metered settlement, uncertain history and process exclusion."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from crate_studio.budget import ledger_summary, usage


class BudgetTests(unittest.TestCase):
    def ledger(self, root, events):
        path = Path(root) / "events.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        return path

    def test_completed_usage_settles_without_rewriting_history(self):
        with tempfile.TemporaryDirectory(dir="output") as root:
            path = self.ledger(
                root,
                [
                    {"kind": "reservation", "attempt": 1, "budget_charge_usd": 10},
                    {
                        "kind": "response",
                        "attempt": 1,
                        "estimated_cost_usd": 0.12,
                        "usage_complete": True,
                    },
                ],
            )
            before = path.read_bytes()
            r = ledger_summary(path)
            self.assertEqual(float(r["guard"]), 0.12)
            self.assertEqual(float(r["historical_debits"]), 10)
            self.assertEqual(r["open_request_count"], 0)
            self.assertEqual(before, path.read_bytes())

    def test_open_uncertain_and_ambiguous_requests_keep_reservations(self):
        with tempfile.TemporaryDirectory(dir="output") as root:
            p = self.ledger(
                root,
                [
                    {"kind": "reservation", "attempt": 1, "budget_charge_usd": 3},
                    {
                        "kind": "response",
                        "attempt": 1,
                        "usage_complete": False,
                        "estimated_cost_usd": 0.01,
                    },
                    {"kind": "reservation", "attempt": 2, "budget_charge_usd": 4},
                ],
            )
            r = ledger_summary(p)
            self.assertEqual(float(r["guard"]), 7)
            self.assertEqual(r["open_request_count"], 1)
            self.assertEqual(r["uncertain_response_count"], 1)
            p = self.ledger(
                root,
                [
                    {"kind": "reservation", "attempt": 1, "budget_charge_usd": 3},
                    {"kind": "reservation", "attempt": 1, "budget_charge_usd": 4},
                    {
                        "kind": "response",
                        "attempt": 1,
                        "usage_complete": True,
                        "estimated_cost_usd": 1,
                    },
                ],
            )
            self.assertEqual(float(ledger_summary(p)["guard"]), 8)

    def test_ids_support_out_of_order_settlements_and_reject_duplicates(self):
        rows = [
            {"kind": "reservation", "budget_request_id": key, "budget_charge_usd": 8}
            for key in ("a", "b")
        ]
        rows += [
            {
                "kind": "response",
                "budget_request_id": key,
                "usage_complete": True,
                "estimated_cost_usd": cost,
            }
            for key, cost in (("b", 1), ("a", 2))
        ]
        with tempfile.TemporaryDirectory(dir="output") as root:
            self.assertEqual(float(ledger_summary(self.ledger(root, rows))["guard"]), 3)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                ledger_summary(self.ledger(root, rows + [rows[-1]]))
            with self.assertRaises(FileNotFoundError):
                usage([Path(root) / "missing"], require_roots=True)
            with self.assertRaises(ValueError):
                ledger_summary(self.ledger(root, [{"budget_charge_usd": -1}]))

    def test_two_processes_cannot_both_reserve_beyond_cap(self):
        with tempfile.TemporaryDirectory(dir="output") as root:
            script = """
import json,sys,time
from pathlib import Path
from crate_studio.budget import BudgetLock,usage
root=Path(sys.argv[1]);ident=sys.argv[2]
with BudgetLock(lambda:root/'guard.lock'):
    if float(usage([root])['guard'])+8>10:print('denied')
    else:
        folder=root/ident;folder.mkdir()
        (folder/'events.jsonl').write_text(json.dumps({'kind':'reservation','budget_request_id':ident,'budget_charge_usd':8}))
        time.sleep(.1);print('reserved')
"""
            jobs = [
                subprocess.Popen(
                    [sys.executable, "-c", script, str(Path(root).resolve()), str(i)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for i in range(2)
            ]
            results = [job.communicate(timeout=20) for job in jobs]
            self.assertTrue(all(job.returncode == 0 for job in jobs), results)
            self.assertEqual(
                sorted(out.strip() for out, _ in results), ["denied", "reserved"]
            )
            self.assertEqual(float(usage([root])["guard"]), 8)
