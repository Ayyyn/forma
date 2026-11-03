"""Opt-in paid synthetic development checks for Muse's engineering tool loop.

These are development examples, never held-out benchmark results. Full model
proposals and tool failures remain in Studio's existing private receipt ledger.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid
import hashlib
import re

from crate_studio.design_agent import propose_design

CASES = {
    "module_revision": "Continue the existing Muse-generated adjustable-box concept for ONE bounded implementation step. Inspect the retained geometry. Make each corner's floor and its two walls a single connected native rigid component, preserving nominal 2 mm material and the retained envelope. Keep the four intended corner components separate from one another so future X/Y adjustment remains possible. Choose the actual joining/correction operations yourself using measured geometry and available targeted native CAD operations; do not merely label disconnected bodies fixed. Check interference, inspect rendered views, and verify exports before selecting the resulting editable geometry. Do not implement every later mechanism detail in this step. The retained original box brief remains mandatory: four usable sizes, permanent guides/retention, positive locks, floor coverage and motion still need subsequent work and MUST be listed unresolved. This is a continuation and developer-guided diagnostic step, not an autonomous complete adjustable-box result or benchmark.",
    "plate": "Create an editable 30 by 20 mm mounting plate, 2 mm thick, with a central 4 mm diameter through-hole. Use provisional printer/material assumptions where needed and label them; do not ask for a printer to make this geometry proposal. Inspect the actual CAD views and verify interference and exports using your tools before selecting the result. Keep physical fit/load qualification explicitly unresolved.",
    "adjustable_box": "Design one permanently connected, open-top adjustable-size box, with a usable floor and stable small, medium, large and rectangular states. Example useful floors are about 70x70, 100x100, 130x130 and 130x70 mm, but you may justify better dimensions. Flattening/refolding and initial assembly are allowed; swapping parts during resizing is not. Use real nonzero thickness, initially around 2 mm panels but you may justify alternatives. A single print job is preferred only where practical. You have freedom to choose folding, sliding, telescoping, linkages, hybrid or another mechanism: compare alternatives and choose your own design, not a preselected template. Include real adjustment/retention/locking geometry where your tools support it. Printer, material and service load are unknown: choose labelled provisional assumptions for a development candidate, rather than stopping to ask. Preserve finite thickness and every functional requirement. Use actual editable CAD, measurements, native interference, a model-declared motion study when appropriate, actual rendered views and export checks; revise from failures. Virtual joints do not establish hardware, locks or physical strength. Retain useful geometry but explicitly report unmet requirements if the available tools cannot solve them. Do not claim a working adjustable box merely because a solid or kinematic path is valid. This is a self-authored synthetic development test, not a public benchmark.",
}


def run(
    case,
    output,
    turns,
    reasoning_effort="medium",
    max_tokens=4096,
    continue_run=None,
    candidate_id=None,
    resume_run=None,
):
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    files = [
        "design_agent.py",
        "design_tools.py",
        "mechanism_study.py",
        "workspace_agent.py",
        "workspace_geometry.py",
        "workspace_cache.py",
        "workspace_workflow.py",
        "design_checkpoint.py",
    ]
    hashes = {}
    for name in files:
        data = (
            Path(__file__).resolve().parents[1] / "crate_studio" / name
        ).read_bytes()
        (source / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "case": case,
                "reasoning_effort": reasoning_effort,
                "max_tokens": max_tokens,
                "max_turns": turns,
                "source_sha256": hashes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    base = {
        "name": "Muse tool-loop " + case,
        "features": [],
        "annotations": [],
        "display": {},
        "metadata": {},
    }
    if continue_run is not None:
        from crate_studio.workspace_agent import RUNS

        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", continue_run) or not candidate_id:
            raise ValueError(
                "Continuation requires an existing run ID and candidate ID"
            )
        prior = json.loads(
            (RUNS / continue_run / "candidates.json").read_text(encoding="utf-8")
        )[candidate_id]
        base = prior["document"]
        base.setdefault("metadata", {})["development_origin"] = {
            "source_run": continue_run,
            "source_candidate": candidate_id,
            "prior_summary": prior["summary"],
            "scope": "Continuation of prior Muse-generated geometry; not a new design from an empty project",
        }
        (output / "continuation.json").write_text(
            json.dumps(base["metadata"]["development_origin"], indent=2),
            encoding="utf-8",
        )
    if resume_run is not None:
        from crate_studio.workspace_agent import RUNS

        if continue_run is not None or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,80}", resume_run
        ):
            raise ValueError(
                "Use one valid checkpoint resume ID, without a separate candidate continuation"
            )
        events = [
            json.loads(line)
            for line in (RUNS / resume_run / "events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        request = next(e["request"] for e in events if e.get("kind") == "reservation")
        context = json.loads(
            next(
                m["content"]
                for m in request["messages"]
                if m["role"] == "user"
                and isinstance(m.get("content"), str)
                and '"original_instruction"' in m["content"]
            )
        )
        if context["original_instruction"] != CASES[case]:
            raise ValueError("Checkpoint does not match this development case")
        base = context["project"]

    def budget():
        subprocess.run(
            [sys.executable, "-m", "research.update_forma_engineering_budget"],
            check=True,
        )

    budget()
    try:
        result = propose_design(
            base,
            CASES[case],
            run_id="design-dev-" + case + "-" + uuid.uuid4().hex[:10],
            max_turns=turns,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
            resume_from=resume_run,
            on_event=lambda kind, message: print(
                json.dumps({"kind": kind, "message": message}), flush=True
            ),
        )
        (output / "result.json").write_text(
            json.dumps(
                {"case": case, "prompt": CASES[case], "proposal": result},
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    key: result.get(key)
                    for key in (
                        "status",
                        "summary",
                        "calls",
                        "tool_calls",
                        "tool_cache_hits",
                        "estimated_cost_usd",
                        "elapsed_s",
                        "run_id",
                    )
                }
            ),
            flush=True,
        )
    finally:
        budget()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=list(CASES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument(
        "--reasoning-effort", choices=["low", "medium", "high"], default="medium"
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--continue-run")
    parser.add_argument("--candidate-id")
    parser.add_argument("--resume-run")
    parser.add_argument("--run-paid", action="store_true")
    args = parser.parse_args()
    if not args.run_paid:
        parser.error(
            "Paid synthetic Meta calls require --run-paid within the authorized application cap"
        )
    run(
        args.case,
        args.output,
        args.turns,
        args.reasoning_effort,
        args.max_tokens,
        args.continue_run,
        args.candidate_id,
        args.resume_run,
    )
