"""All-task Meta comparison, isolated Python execution and unchanged Linux grading.

Resume only completed tasks. A task-start marker without a result requires manual
receipt inspection; never silently repeat a possibly billed model request.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from crate_studio import agent, workspace_agent as wa
from crate_studio.workspace_geometry import export_document
from scripts.api_preflight import load_env, request
from research.freeze_forma_full17 import BASELINE_SYSTEM, digest, dump

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "evaluation/forma-full17-v1"
AGENT_IMAGE = "forma-cadbench-agent:full17-compatible"
VERIFIER_IMAGE = "forma-cadbench-verifier:full17-compatible"


def load(p):
    return json.loads(p.read_text(encoding="utf8"))


def linux(p):
    p = Path(p).resolve()
    if not p.is_relative_to(ROOT) or p == ROOT:
        raise ValueError("Docker mounts must stay in the project")
    if len(p.drive) != 2 or p.drive[1] != ":":
        raise ValueError("This runner requires a Windows drive mounted by WSL")
    return "/mnt/" + p.drive[0].lower() + "/" + p.as_posix()[3:]


def container(mode, source, output, task=None, timeout=None):
    output.mkdir(parents=True, exist_ok=True)
    source.mkdir(parents=True, exist_ok=True)
    name = "forma-bench-" + hashlib.sha256(str(output).encode()).hexdigest()[:16]
    cmd = [
        "wsl",
        "-d",
        "Ubuntu",
        "--",
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--user",
        "1000:1000",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--cpus",
        "4",
        "--memory",
        "4g",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,size=2g",
        "-e",
        "HOME=/tmp",
        "-e",
        "OMP_NUM_THREADS=4",
        "--mount",
        f"type=bind,source={linux(source)},target=/input,readonly",
        "--mount",
        f"type=bind,source={linux(output)},target=/output",
        "--mount",
        f"type=bind,source={linux(ROOT/'research/cadbench_container.py')},target=/runner.py,readonly",
        AGENT_IMAGE if mode == "build" else VERIFIER_IMAGE,
        "python",
        "/runner.py",
        mode,
    ]
    if task:
        cmd += ["--task", task]
    started = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf8",
            errors="replace",
            timeout=timeout or (600 if mode == "build" else 7200),
        )
        (output / "stdout.txt").write_text(result.stdout, encoding="utf8")
        (output / "stderr.txt").write_text(result.stderr, encoding="utf8")
        data = (
            load(output / "result.json")
            if (output / "result.json").exists()
            else {"error": "Container failed", "detail": result.stderr[-1500:]}
        )
    except subprocess.TimeoutExpired:
        # Stop only this named task container; never prune or affect other work.
        subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "docker", "kill", name], capture_output=True
        )
        data = {"error": "Container timeout", "timeout": True}
    data["container_elapsed_s"] = time.monotonic() - started
    dump(output / "container-result.json", data)
    return data


def baseline(prompt, folder, run_id, *, resume_empty=False):
    load_env()
    key = os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY")
    if not key:
        raise ValueError("Meta API key missing")
    receipts = wa.RUNS / run_id
    if not resume_empty:
        receipts.mkdir(parents=True, exist_ok=False)
    messages = [
        {"role": "system", "content": BASELINE_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    events = (
        [
            json.loads(l)
            for l in (receipts / "events.jsonl").read_text(encoding="utf8").splitlines()
        ]
        if resume_empty
        else []
    )

    def log(x):
        events.append(x)
        with (receipts / "events.jsonl").open("a", encoding="utf8") as f:
            f.write(json.dumps(wa._redact(x), allow_nan=False) + "\n")

    built = None
    start_attempt = 0
    if resume_empty:
        prior = [e for e in events if e.get("kind") == "response"]
        reservations = [e for e in events if e.get("kind") == "reservation"]
        if (
            len(prior) != 1
            or len(reservations) != 1
            or prior[0].get("public_response")
            or prior[0]["transport"].get("http_status") != 200
            or reservations[0]["request"]["messages"] != messages
        ):
            raise ValueError(
                "Resume is restricted to one successful transport with an empty public response and the identical original prompt"
            )
        trial = folder / "attempt-1"
        trial.mkdir(exist_ok=False)
        (trial / "final.py").write_text("", encoding="utf8")
        built = container("build", trial, trial / "build")
        messages += [
            {"role": "assistant", "content": ""},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "actual_build_error": built,
                        "original_instruction": prompt,
                        "instruction": "Repair the complete program. Preserve the original geometry requirements.",
                    }
                ),
            },
        ]
        log(
            {
                "kind": "resume_empty_response",
                "source_response_id": prior[0]["response_id"],
                "budget_charge_usd": 0,
                "reason": "Restore the remaining repair after null-content client error; original response retained.",
            }
        )
        start_attempt = 1
    for attempt in range(start_attempt, 2):
        payload = {
            "model": wa.MODEL,
            "messages": messages,
            "max_tokens": 8192,
            "temperature": 0.15,
            "reasoning_effort": "medium",
            "prompt_cache_key": "forma-full17-build123d-v1",
        }
        encoded = json.dumps(payload).encode()
        reservation = len(encoded) * 4e-6 + 8192 * 20e-6
        with agent._spend_lock:
            if wa.estimated_spend() + reservation > agent.CAP_USD:
                raise ValueError("Approved application budget reached")
            log(
                {
                    "kind": "reservation",
                    "model": wa.MODEL,
                    "attempt": attempt + 1,
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "request": payload,
                    "request_sha256": hashlib.sha256(encoded).hexdigest(),
                    "budget_charge_usd": reservation,
                    "billing_verified": False,
                }
            )
            ts = time.monotonic()
            transport, body = request(
                "https://api.meta.ai/v1", key, "/chat/completions", payload, timeout=120
            )
            body = body if isinstance(body, dict) else {}
            choices = body.get("choices") or []
            public = (
                (choices[0].get("message", {}).get("content") or "") if choices else ""
            )
            usage = transport.get("usage") or {}
            valid = all(
                type(usage.get(k)) is int and usage[k] >= 0
                for k in ("prompt_tokens", "completion_tokens")
            )
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            if (
                type(cached) is not int
                or not valid
                or not 0 <= cached <= usage["prompt_tokens"]
            ):
                cached = 0
            cost = (
                (usage["prompt_tokens"] - cached) * 4e-6
                + cached * 0.2e-6
                + usage["completion_tokens"] * 20e-6
                if valid
                else reservation
            )
            log(
                {
                    "kind": "response",
                    "model": wa.MODEL,
                    "attempt": attempt + 1,
                    "response_id": body.get("id"),
                    "returned_model": body.get("model"),
                    "transport": transport,
                    "public_response": public,
                    "elapsed_s": time.monotonic() - ts,
                    "estimated_cost_usd": cost,
                    "cached_input_tokens": cached,
                    "usage_complete": valid,
                    "budget_charge_usd": max(0, cost - reservation),
                    "billing_verified": False,
                }
            )
        if transport.get("http_status") != 200:
            break
        code = public.strip()
        if code.startswith("```") and code.endswith("```"):
            code = code.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        trial = folder / f"attempt-{attempt+1}"
        trial.mkdir()
        (trial / "final.py").write_text(code, encoding="utf8")
        built = container("build", trial, trial / "build")
        if built.get("passed"):
            shutil.copy2(trial / "build/candidate.step", folder / "candidate.step")
            break
        messages += [
            {"role": "assistant", "content": public},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "actual_build_error": built,
                        "original_instruction": prompt,
                        "instruction": "Repair the complete program. Preserve the original geometry requirements.",
                    }
                ),
            },
        ]
    return {
        "build": built,
        "calls": sum(e["kind"] == "response" for e in events),
        "estimated_cost_usd": sum(e.get("estimated_cost_usd", 0) for e in events),
        "response_ids": [e["response_id"] for e in events if e["kind"] == "response"],
    }


def summarize(folder, tasks):
    rows = []
    for task in tasks:
        p = folder / task["id"] / "result.json"
        rows.append(
            load(p)
            if p.exists()
            else {
                "id": task["id"],
                "difficulty": task["difficulty"],
                "score": 0,
                "missing": True,
            }
        )
    # The metric script consumes exactly 17 entries in frozen manifest order.
    (folder / "rewards.jsonl").write_text(
        "".join(json.dumps({"overall_score": r["score"]}) + "\n" for r in rows),
        encoding="utf8",
    )
    subprocess.run(
        [
            os.sys.executable,
            str(ROOT / "research/vendor/cad-bench/dataset/metric.py"),
            "-i",
            str(folder / "rewards.jsonl"),
            "-o",
            str(folder / "aggregate.json"),
        ],
        check=True,
    )
    aggregate = load(folder / "aggregate.json")
    dump(
        folder / "summary.json",
        {
            "tasks": rows,
            "aggregate": aggregate,
            "completed": sum(not r.get("missing") for r in rows),
            "total": 17,
            "successes_at_095": sum(r["score"] >= 0.95 for r in rows),
            "estimated_cost_usd": sum(
                r.get("generation", {}).get("estimated_cost_usd", 0) for r in rows
            ),
            "billing_verified": False,
        },
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", required=True, choices=["forma", "build123d"])
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--generate-only", action="store_true")
    p.add_argument("--score-only", action="store_true")
    p.add_argument("--task")
    p.add_argument("--protocol-dir", type=Path, default=FROZEN)
    p.add_argument("--run-prefix", default="full17")
    p.add_argument(
        "--mechanical-policy", choices=["standard", "design"], default="standard"
    )
    args = p.parse_args()
    import re

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", args.run_prefix):
        raise ValueError("Invalid receipt prefix")
    frozen = args.protocol_dir.resolve()
    for name, sha in load(frozen / "manifest.json").items():
        if digest(frozen / name) != sha:
            raise ValueError("Frozen manifest mismatch: " + name)
    protocol = load(frozen / "protocol.json")
    if not args.score_only and args.arm == "forma":
        actual_system = (
            wa.MECHANICAL_SYSTEM if args.mechanical_policy == "design" else wa.SYSTEM
        )
        if protocol["forma_system"] != actual_system:
            raise ValueError(
                "Selected mechanical policy does not match the recorded protocol"
            )
    for name, sha in {
        str(Path("research/vendor/cad-bench") / k): v
        for k, v in protocol["upstream_hashes"].items()
    }.items():
        if digest(ROOT / name) != sha:
            raise ValueError("Source changed since freeze: " + name)
    # Regrading retained STEP must verify the original generation snapshot,
    # rather than requiring the developer to roll back unrelated product fixes.
    source_root = args.output.resolve() / "source-snapshot" if args.score_only else ROOT
    for name, sha in protocol["source_hashes"].items():
        if digest(source_root / name) != sha:
            raise ValueError("Generation source changed since freeze: " + name)
    tasks = load(frozen / "tasks.json")
    folder = args.output.resolve() / args.arm
    folder.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        if args.task and task["id"] != args.task:
            continue
        dest = folder / task["id"]
        if (dest / "result.json").exists():
            continue
        dest.mkdir(exist_ok=True)
        generation_path = dest / "generation.json"
        if not generation_path.exists():
            if args.score_only:
                continue
            if not args.live:
                raise ValueError("Generation requires --live")
            if (dest / "started.json").exists():
                raise ValueError(
                    "Unfinished paid task; inspect receipts before resuming: "
                    + str(dest)
                )
            dump(
                dest / "started.json",
                {
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "task": task["id"],
                    "arm": args.arm,
                },
            )
            ts = time.monotonic()
            run_id = (
                args.run_prefix
                + "-"
                + args.arm
                + "-"
                + hashlib.sha256(str(dest).encode()).hexdigest()[:16]
            )
            print("GENERATE", args.arm, task["id"], flush=True)
            try:
                if args.arm == "forma":
                    doc = {
                        "name": task["id"],
                        "features": [],
                        "annotations": [],
                        "display": {},
                        "metadata": {},
                    }
                    proposal = wa.propose_document(
                        doc,
                        task["prompt"],
                        run_id=run_id,
                        use_cache=False,
                        max_tokens=8192,
                        mechanical_policy=args.mechanical_policy,
                    )
                    dump(dest / "proposal.json", proposal)
                    generation = {
                        k: proposal[k]
                        for k in (
                            "status",
                            "calls",
                            "estimated_cost_usd",
                            "response_ids",
                        )
                    }
                    if proposal["status"] == "ready":
                        exported = export_document(
                            proposal["document"], None, dest / "exports"
                        )
                        dump(dest / "export.json", exported)
                        # Scoring native STEP is separate from optional STL print QC.
                        if (
                            exported.get("checks", {})
                            .get("step_roundtrip", {})
                            .get("passed")
                        ):
                            shutil.copy2(
                                dest / "exports/workspace.step", dest / "candidate.step"
                            )
                else:
                    generation = baseline(task["prompt"], dest, run_id)
            except Exception as exc:
                generation = {"error": str(exc)[:1500], "receipt_run_id": run_id}
                ledger = wa.RUNS / run_id / "events.jsonl"
                if ledger.exists():
                    responses = [
                        json.loads(l)
                        for l in ledger.read_text(encoding="utf8").splitlines()
                        if json.loads(l).get("kind") == "response"
                    ]
                    generation.update(
                        calls=len(responses),
                        estimated_cost_usd=sum(
                            r.get("estimated_cost_usd", 0) for r in responses
                        ),
                        response_ids=[r.get("response_id") for r in responses],
                    )
            generation["elapsed_s"] = time.monotonic() - ts
            generation["receipt_run_id"] = run_id
            dump(generation_path, generation)
        if args.generate_only:
            continue
        generation = load(generation_path)
        print("SCORE", args.arm, task["id"], flush=True)
        graded = (
            container("score", dest, dest / "verifier", task["id"])
            if (dest / "candidate.step").exists()
            else {"error": "No valid STEP candidate"}
        )
        metrics = graded.get("metrics", {})
        row = {
            "id": task["id"],
            "difficulty": task["difficulty"],
            "score": float(metrics.get("overall_score", 0)),
            "generation": generation,
            "grading": graded,
        }
        dump(dest / "result.json", row)
        summarize(folder, tasks)
        print("RESULT", task["id"], row["score"], flush=True)
    summarize(folder, tasks)


if __name__ == "__main__":
    main()
