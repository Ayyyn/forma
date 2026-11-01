"""Compare cached and uncached execution of retained plans; no provider calls."""

from copy import deepcopy
import json
import statistics
import time
from unittest.mock import patch

from crate_studio import workspace_agent as wa
from crate_studio.workspace_geometry import build_document, export_document
from crate_studio.workspace_cache import cached_build, cache_clear
from .run_forma_eval import ROOT, FROZEN, load, dump, verify_freeze, revision_score


def main():
    verify_freeze()
    folder = ROOT / "output/forma/evaluation/performance/replay"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for group in ["revision", "public"]:
        for task in load(FROZEN / (group + "-tasks.json")):
            source = ROOT / "output/forma/evaluation/v1" / task["id"] / "proposal.json"
            if task["id"] == "r15_nonstock":
                source = (
                    ROOT
                    / "output/forma/evaluation/v2-repair/r15_nonstock/proposal.json"
                )
            old = load(source)
            events = [
                json.loads(s)
                for s in (wa.RUNS / old["run_id"] / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            event = next(e for e in reversed(events) if e.get("kind") == "response")
            plan = wa.parse_plan(event["public_response"])
            with patch.object(wa, "cached_build", build_document):
                start = time.perf_counter()
                reference = wa.apply_plan(task["document"], plan, task["prompt"])
                uncached = time.perf_counter() - start
            cache_clear()
            cold = wa.apply_plan(task["document"], plan, task["prompt"])
            start = time.perf_counter()
            warm = wa.apply_plan(task["document"], plan, task["prompt"])
            warm_time = time.perf_counter() - start
            checks = {
                "document_exact": reference["document"]
                == cold["document"]
                == warm["document"]
                == old["document"],
                "result_exact": reference["result"] == cold["result"] == warm["result"],
                "disposition_exact": reference["status"]
                == cold["status"]
                == warm["status"]
                == old["status"],
            }
            if warm["status"] == "ready":
                checks["native_export_readback"] = export_document(
                    warm["document"], None, folder / task["id"]
                )["checks"]["passed"]
            if group == "revision":
                checks["frozen_revision_contract"] = revision_score(task, warm, None)[
                    "passed"
                ]
            row = {
                "id": task["id"],
                "group": group,
                "passed": all(checks.values()),
                "checks": checks,
                "uncached_apply_s": uncached,
                "warm_apply_s": warm_time,
                "source_run_id": old["run_id"],
            }
            rows.append(row)
    report = {
        "passed": all(r["passed"] for r in rows),
        "count": len(rows),
        "rows": rows,
        "model_calls": 0,
        "uncached_apply_median_s": statistics.median(
            r["uncached_apply_s"] for r in rows
        ),
        "warm_apply_median_s": statistics.median(r["warm_apply_s"] for r in rows),
        "scope": "Retained-plan execution equivalence, not new model quality evaluation. Uses the separately verified r15 repair. Public slot interpretation remains the original retained geometry; native readback is not a new upstream score.",
    }
    dump(folder / "results.json", report)
    assert report["passed"], [r for r in rows if not r["passed"]]
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
