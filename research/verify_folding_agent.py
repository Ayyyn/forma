"""Opt-in, paid synthetic development prompts for Forma's folding planner.

Not a held-out benchmark. Every prompt, unmodified proposal and receipt reference
is retained. Native motion and printing qualification are later separate steps.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from crate_studio.workspace_agent import propose_document

CASES = {
    "concertina": "Create a 10-panel concertina folding demonstrator for 3D printing, with roughly 40 mm panel pitches, actual bored knuckle hinges and separate removable headed pins. Choose sensible printable clearances and a 60 degree driver preview. Keep every hardware dimension editable. This is a rigid-panel mechanism, not a flexible living hinge.",
    "radial_fan": "Create an eight-panel open annular half-fan folding demonstrator, with finite thickness panels, actual bored hinges and separate removable pins. Size the rigid panels around 40 mm so the parts can be laid out on a 220 mm square printer bed. Choose sensible printable clearances; show a 35 degree fold driver. Keep dimensions editable.",
    "triangle_strip": "Create a 10-panel alternating triangulated folding strip demonstrator for 3D printing, with actual bored hinges and separate removable pins. Aim for roughly 40 mm panels, sensible printable clearances, and a 45 degree driver preview. Keep panel pitches, thickness, setback and all hinge hardware editable.",
    "cube_net": "Create a six-panel hinged cube net with a staged folding lid, actual bored hinges and separate removable pins, for 3D printing. Use about 40 mm nominal square panels and suitable printable thickness and clearances. Show the final closed pose at a 90 degree driver. Preserve editable dimensions. I will check sampled motion and generate separate print plates later.",
}


def budget():
    subprocess.run(
        [sys.executable, "-m", "research.update_forma_engineering_budget"], check=True
    )


def run(folder, family_filter=None):
    folder.mkdir(parents=True, exist_ok=False)
    budget()
    results = []
    try:
        for family, prompt in CASES.items():
            if family_filter is not None and family != family_filter:
                continue
            base = dict(
                name=family.replace("_", " ").title() + " / Meta development case",
                features=[],
                annotations=[],
                display={},
                metadata={},
            )
            run_id = "fold-dev-" + family + "-" + uuid.uuid4().hex[:10]
            start = time.perf_counter()
            proposal = propose_document(base, prompt, run_id=run_id, use_cache=False)
            result = dict(
                family=family,
                prompt=prompt,
                run_id=run_id,
                proposal=proposal,
                seconds=time.perf_counter() - start,
            )
            results.append(result)
            (folder / f"{family}.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    dict(
                        family=family,
                        status=proposal["status"],
                        calls=proposal.get("calls"),
                        estimated_cost_usd=proposal.get("estimated_cost_usd"),
                        seconds=result["seconds"],
                    )
                ),
                flush=True,
            )
        (folder / "summary.json").write_text(
            json.dumps(
                [{k: v for k, v in r.items() if k != "proposal"} for r in results],
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        budget()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--run-paid",
        action="store_true",
        help="Explicitly authorize this synthetic Meta development batch within the existing application cap",
    )
    parser.add_argument(
        "--family", choices=list(CASES), help="Run one named development case"
    )
    args = parser.parse_args()
    if not args.run_paid:
        parser.error(
            "This makes paid Meta calls; pass --run-paid only within the user's approved scope/cap"
        )
    run(args.output, args.family)
