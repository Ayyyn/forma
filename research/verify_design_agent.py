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
    "locking_module": "Continue the selected Muse-authored three-guide four-size box. Take the next bounded hardware step on ONE prismatic interface of your choice: propose and implement real overtravel stops and a positive releasable size lock using finite editable CAD. Choose your own practical mechanism/dimensions and label provisional printing assumptions. Retain all three existing guides and the original four useful sizes. Initial assembly is allowed; parts must not need to be swapped during resizing. Friction alone is not a positive lock, and virtual travel limits are not physical stops. A moving pin/latch may be a new solid, but update the joint tree so it follows the actual owning component, and declare an unlock/move/relock sequence rather than interpolating through a locked mechanism. The generic checker allows at most12 named states and361 total sampled poses; reduce per-transition samples appropriately rather than dropping the real unlock motion. Preserve exact old small/medium/large/rectangular locked targets when achievable; explicitly report any unmet functional part. Attempt one manageable native draft early and repair the first concrete failure. Use isolated joint/pin diagnostics where supported and actual whole-assembly motion/interference, floor checks and native state images, then checked separate-body/assembly exports before any selection. A partial candidate can be retained without finish_design; do not call it finished if this bounded run cannot qualify it. Other two interfaces' stops/locks, global/rotational retention, continuous assembly, floor steps and physical printer/material/load tests remain unresolved. This is guided synthetic hardware development, not an unseen evaluation or physical qualification.",
    "guide_qualification": "Continue the exact retained Muse-authored four-size box with three real T-guide interfaces. Its last development run passed native motion and four floors on the preceding draft but failed STL readback; its last repair is unselected and needs fresh checks. First inspect source and run verify_exports to get current per-body/native mesh diagnostics, then repair the concrete reported defect with a minimal editable CAD change you choose. Do not repeat unchanged failed exports without a reason or weaken acceptance. Preserve all three physical guide interfaces, original four usable floor targets, finite thickness, compactness and full size travel. After any repair run isolated probe_prismatic_pair on all three joints in small and large (batch independent calls), whole 217-pose motion, all four check_floor targets and actual render_state images, source interference/render and exports including independent component STLs. Review images before selecting. Use the same source solids and joint tree in every size. Batch up to eight independent tools per turn. Select only a geometry-stage guide result with explicit unresolved actual end stops, positive releasable size locks, rotational/global retention, complete/continuous assembly, floor steps, printer/material/load and physical fit. This is guided synthetic development, not a held-out evaluation or a finished working box.",
    "remaining_guides": "Continue the retained Muse-authored adjustable box with one actual south-wall T-guide. Implement real guidance for BOTH remaining prismatic interfaces so all four corner components are mechanically guided through the four retained sizes. This is bounded guide development, not finished locks/physical qualification. Choose the actual rail/channel geometry, dimensions, mounting and initial-assembly approach yourself. Reuse/adapt the existing editable guide where sensible, including reversing which body carries the rail if inner/outer wall layers require it; do not redesign the whole box. Preserve the existing four floor targets and source solids across named states, near-2 mm panel thickness, compact proportions and existing south guide. Read existing features and mechanism definition, perform one useful baseline pair probe for an unguided interface, then attempt one manageable native CAD step rather than spending the run only inspecting. After each draft use its automatic collision screen to fix the first concrete interference. Use probe_prismatic_pair to batch six isolated native directions for each finished interface in Small and Large, and use whole-assembly native motion at 73 samples per transition. Other corners obstructing a translation is not proof the interface has a guide. Verify every original floor target, render all four actual named states plus source views, check native interference and separate-body exports before selecting. Batch independent checks up to the eight-tool limit to avoid one model call per unchanged probe. Native tools determine numeric results; do not invent passes or relax requirements. Real travel endstops, positive releasable size locks, global/rotational retention, continuous/complete assembly, stepped-floor usability, printer/material/load and physical fit remain explicitly unresolved unless actually implemented and verified. This is guided diagnostic development of model-created CAD, not an unseen benchmark or autonomous novelty result.",
    "guide_module": "Continue the retained model-authored four-size sliding box. Implement ONE real sliding guide interface first: choose a suitable parent-child pair from its existing joint tree, explain a practical initially assemblable captive guide concept (for example a T/channel, dovetail or another design of your choice) and add editable finite-thickness geometry to those actual parts. This is a development module, not the complete hardware. Use provisional FDM clearances and printable feature thicknesses with stated assumptions. You may change the selected interface wall geometry where needed, but preserve the four usable floors, four connected corner components, compact body and declared full size travel. Test existing geometry with probe_translation to expose an unwanted direction, then test final guide geometry with virtual constraints released: include both signs of two independent directions transverse to the sliding axis at the most separated named state, and an axial probe demonstrating allowed travel. Select the actual dimensions, guide form and mounting yourself; developer did not supply coordinates. A blocked probe is only local sampled obstruction, not complete captivity/assembly/strength proof. Use native measurements, interference, full motion, all four floor checks and native state images, and exports; fix the first concrete failure incrementally. Other interfaces, physical endstops, positive releasable size locks, floor steps, global retention, assembly and printer/material/load qualification remain explicitly unresolved unless actually implemented and verified. Do not call the whole box permanently connected. This is developer-guided synthetic development, not an unseen benchmark.",
    "state_review": "Continue the selected Muse-authored four-size sliding-box geometry. Preserve the original adjustable-box functional requirements and nominal nonzero material. This bounded development stage fixes practical compactness, not complete adjustment hardware. First render_state for each of the four declared sizes, inspect actual outer bounds and images, and compare with the intended usable floor targets retained in metadata. Independent review found an unnecessary protruding wall in the small state despite passing floor coverage and collision checks. Choose and implement your own geometry correction so all four states have compact coherent outer walls without this conspicuous overhang; preserve usable floor coverage, connected individual corner components and collision-free sampled travel. Do not simply enlarge the small floor target or drop a size to hide the defect. Prefer a small targeted revision over restarting. Recheck all four actual floors and rendered named states, native interference, exports and the full motion with 73 samples per transition. Select only after examining all final native state images. Real captive guides, end stops, positive releasable locks, floor steps, wall continuity, material/load and physical validation remain open unless actually implemented and verified; list them explicitly. This is developer-guided diagnostic improvement of a model-generated design, not a held-out score or autonomous novelty claim.",
    "size_states": "Continue the retained Muse-generated four-corner adjustable-box draft. This development stage is about actual finite-thickness size-state geometry, floor coverage and motion, not finished hardware. Propose meaningfully different small, medium, large and rectangular usable footprints, explaining their sizes relative to the retained original brief; the earlier dimensions were examples, not fixed constraints. Use the SAME source solids in every state, with a declared compatible joint tree and named-state values, not four separately resized CAD objects. First TEST the retained geometry under your proposed states before modifying it, and preserve the diagnostics. Use check_floor for each intended usable floor (set a tight low Z band around actual floor surfaces so wall tops are excluded), and check_motion across the complete state sequence with 73 samples per segment where feasible. Revise from actual gaps and collisions. You may change floor dimensions, layer arrangements, wall connections, joints, sequence or mechanism family if needed; choose the actual fix yourself and keep nominal nonzero material near 2 mm with justified changes. A root-first tree can give a diagonal corner coupled X/Y motion through two parent-child prismatic joints; inspect mechanism_reference for exact conventions. Be incremental: test, fix the first concrete issue, and test again rather than reasoning about every future lock detail at once. When ready, run native interference/export checks and inspect actual images. Include all four floor checks and a passing motion study in any selected state-geometry result. Captive guides, positive releasable locks, floor-level steps, material/load and physical print validation remain unresolved unless actually implemented and verified; do not claim this is the complete working box. This is a guided development continuation, not a held-out benchmark or independent novelty claim.",
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
        "motion_cache.py",
        "floor_check.py",
        "motion_probe.py",
        "component_exports.py",
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
        if candidate_id == "selected":
            prior = json.loads(
                (RUNS / continue_run / "proposal.json").read_text(encoding="utf-8")
            )
            if prior.get("status") != "ready":
                raise ValueError(
                    "Selected-source continuation requires a ready geometry proposal"
                )
        else:
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
