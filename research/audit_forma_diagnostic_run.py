"""Independent all-task, receipt and frozen-source audit of a diagnostic run."""

import argparse
import hashlib
import json
import math
import statistics

from research.run_forma_full17 import ROOT, dump, load, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    root = (ROOT / args.run).resolve()
    root.relative_to(ROOT / "output")
    protocol = load(root / "protocol/protocol.json")
    tasks = load(root / "protocol/tasks.json")
    checks = {}
    checks["all_original_prompts"] = tasks == load(
        ROOT / "evaluation/forma-full17-v1/tasks.json"
    )
    checks["original_upstream"] = all(
        digest(ROOT / "research/vendor/cad-bench" / name) == sha
        for name, sha in protocol["upstream_hashes"].items()
    )
    checks["frozen_source_bytes"] = all(
        digest(root / "source-snapshot" / name) == sha
        for name, sha in protocol["source_hashes"].items()
    )
    rows = []
    responses = []
    cost = 0
    guard = 0
    request_checks = []
    generation_seconds = []
    for task in tasks:
        folder = root / "forma" / task["id"]
        row = load(folder / "result.json")
        rows.append(row)
        assert row["id"] == task["id"] and row["difficulty"] == task["difficulty"]
        generation = load(folder / "generation.json")
        ledger = (
            ROOT
            / "output/forma/studio/agent"
            / generation["receipt_run_id"]
            / "events.jsonl"
        )
        events = [
            json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
        ]
        receipts = [e for e in events if e.get("kind") == "response"]
        assert 1 <= len(receipts) <= protocol["max_calls_per_task"]
        assert len(receipts) == generation["calls"]
        assert [e["response_id"] for e in receipts] == generation["response_ids"]
        responses.extend(receipts)
        estimate = sum(e["estimated_cost_usd"] for e in receipts)
        assert math.isclose(estimate, generation["estimated_cost_usd"], abs_tol=1e-10)
        cost += estimate
        guard += sum(e.get("budget_charge_usd", 0) for e in events)
        generation_seconds.append(generation["elapsed_s"])
        for event in events:
            if event.get("kind") != "reservation":
                continue
            request = event["request"]
            messages = request["messages"]
            context = json.loads(messages[1]["content"])
            okay = (
                messages[0]["content"] == protocol["forma_system"]
                and context["instruction"] == task["prompt"]
                and request["model"] == protocol["model"]
                and request["max_tokens"] == protocol["max_tokens_per_response"]
                and request["reasoning_effort"] == protocol["reasoning_effort"]
            )
            # Generation is schema/geometry repair only; external grading begins
            # after generation.json. Verify the actual payload, not the claim.
            for message in messages[2:]:
                if message["role"] == "user":
                    feedback = json.loads(message["content"])
                    okay = okay and feedback["original_instruction"] == task["prompt"]
                    okay = (
                        okay
                        and "grading" not in feedback
                        and "overall_score" not in json.dumps(feedback)
                    )
            request_checks.append(okay)
    means = {
        tier: statistics.mean(r["score"] for r in rows if r["difficulty"] == tier)
        for tier in ["easy", "medium", "hard", "insane"]
    }
    score = (
        sum(
            means[t] * weight
            for t, weight in [("easy", 1), ("medium", 2), ("hard", 3), ("insane", 4)]
        )
        / 10
    )
    summary = load(root / "forma/summary.json")
    checks["complete_17"] = len(rows) == 17 and summary["completed"] == 17
    checks["aggregate"] = abs(score - summary["aggregate"]["benchmark_score"]) < 1e-12
    checks["cost"] = abs(cost - summary["estimated_cost_usd"]) < 1e-10
    checks["success_count"] = (
        sum(r["score"] >= 0.95 for r in rows) == summary["successes_at_095"]
    )
    checks["unique_response_ids"] = len({e["response_id"] for e in responses}) == len(
        responses
    )
    checks["meta_only_complete_usage"] = all(
        e["model"] == e["returned_model"] == protocol["model"]
        and e["usage_complete"]
        and e["transport"]["http_status"] == 200
        for e in responses
    )
    checks["frozen_requests_no_benchmark_feedback"] = all(request_checks)
    result = dict(
        passed=all(checks.values()),
        checks=checks,
        score=score,
        successes_at_095=sum(r["score"] >= 0.95 for r in rows),
        responses=len(responses),
        estimated_inference_usd=cost,
        conservative_guard_charge_usd=guard,
        median_generation_workflow_seconds=statistics.median(generation_seconds),
        median_provider_response_seconds=statistics.median(
            e["elapsed_s"] for e in responses
        ),
        billing_verified=False,
        scope="Known public diagnostic development; not held-out, official rank or new matched comparison",
        system_sha256=hashlib.sha256(protocol["forma_system"].encode()).hexdigest(),
    )
    dump(root / "independent-audit.json", result)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
