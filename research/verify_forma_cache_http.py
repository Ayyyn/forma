"""One paid synthetic cold request; repeated requests must add zero model calls."""

from copy import deepcopy
import json
import time

from .build_batman_demo import ROOT, request, dump

DEST = ROOT / "output/forma/evaluation/performance/live-cache"


def api(path, payload=None):
    return json.loads(request("/api/studio" + path, payload))


def complete(job):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        row = api("/jobs/" + job["id"])
        if row["status"] in ("completed", "failed"):
            return row
        time.sleep(0.02)
    raise TimeoutError("Inspect existing job; do not repeat paid request")


def main():
    if (DEST / "results.json").exists():
        print((DEST / "results.json").read_text())
        return
    DEST.mkdir(parents=True, exist_ok=False)
    pointer = ROOT / "output/forma/studio/current.json"
    previous = pointer.read_bytes() if pointer.exists() else None
    owned = []
    try:
        doc = {
            "name": "Synthetic cache verification",
            "features": [
                {
                    "id": "box",
                    "type": "box",
                    "params": {"width": 10, "depth": 20, "height": 30},
                }
            ],
            "annotations": [],
            "display": {},
            "metadata": {
                "brief": "Synthetic efficiency check; preserve all unmentioned data."
            },
        }
        first = api("/documents", {"document": doc, "label": "Performance QA base A"})
        owned.append(first["id"])
        payload = {
            "document_id": first["id"],
            "prompt": "Set the box height to 40 mm. Preserve every other feature and project field.",
        }
        start = time.perf_counter()
        job = api("/agent", payload)
        dump(DEST / "first-job.json", job)
        duplicate = api("/agent", payload)
        cold = complete(job)
        cold_elapsed = time.perf_counter() - start
        dump(DEST / "cold.json", cold)
        assert (
            cold["status"] == "completed" and cold["proposal"]["status"] == "ready"
        ), cold
        assert (
            cold["proposal"]["calls"] == 1
        ), "The cold request must be a real single-response generation"
        start = time.perf_counter()
        same_job = api("/agent", payload)
        same_elapsed = time.perf_counter() - start
        second = api("/documents", {"document": doc, "label": "Performance QA base B"})
        owned.append(second["id"])
        assert first["document"] == second["document"]
        start = time.perf_counter()
        warm_job = api("/agent", {**payload, "document_id": second["id"]})
        dump(DEST / "warm-job.json", warm_job)
        warm = complete(warm_job)
        warm_elapsed = time.perf_counter() - start
        dump(DEST / "warm.json", warm)
        a, b = cold["proposal"], warm["proposal"]
        expected = deepcopy(first["document"])
        expected["features"][0]["params"]["height"] = 40
        checks = {
            "duplicate_active_job_coalesced": duplicate["id"] == job["id"],
            "duplicate_completed_job_reused": same_job["id"] == job["id"],
            "new_revision_exact_cache_hit": b.get("cache", {}).get("hit") is True,
            "warm_zero_model_calls": b["calls"] == 0 and b["response_ids"] == [],
            "warm_zero_estimated_model_cost": b["estimated_cost_usd"] == 0,
            "original_model_provenance_preserved": b["cache"]["source_response_ids"]
            == a["response_ids"],
            "revalidated_before_return": b["cache"]["revalidated"] is True,
            "identical_correct_document": a["document"] == b["document"] == expected,
            "identical_correct_geometry": a["result"]["metrics"]
            == b["result"]["metrics"]
            and abs(b["result"]["metrics"]["volume_mm3"] - 8000) < 1e-7,
            "warm_snapshot_valid": b["snapshot"]["passed"],
        }
        results = {
            "passed": all(checks.values()),
            "checks": checks,
            "cold_end_to_end_s": cold_elapsed,
            "warm_end_to_end_s": warm_elapsed,
            "completed_duplicate_http_s": same_elapsed,
            "cold_estimated_model_cost_usd": a["estimated_cost_usd"],
            "warm_estimated_model_cost_usd": 0,
            "source_run_id": a["run_id"],
            "warm_run_id": b["run_id"],
            "scope": "One synthetic live request and exact repeats; warm result reuse is not fresh generation latency. Includes HTTP serialization, job polling and snapshot validation. No user project modified.",
        }
        dump(DEST / "results.json", results)
        assert results["passed"], checks
        print(json.dumps(results, indent=2), flush=True)
    finally:
        if (
            previous
            and pointer.exists()
            and json.loads(pointer.read_text())["id"] in owned
        ):
            pointer.write_bytes(previous)


if __name__ == "__main__":
    main()
