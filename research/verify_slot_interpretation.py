"""Post-hoc human clarification, explicitly excluded from frozen model scores."""

from copy import deepcopy
import math
from pathlib import Path
from .run_forma_eval import ROOT, FROZEN, load, dump, public_score
from crate_studio.workspace_geometry import build_document


def main():
    ident = "plate_80x40x8_slot_4_hole"
    task = next(t for t in load(FROZEN / "public-tasks.json") if t["id"] == ident)
    original = load(ROOT / "output/forma/evaluation/v1" / ident / "proposal.json")[
        "document"
    ]
    clarified = deepcopy(original)
    center = [
        f
        for f in clarified["features"]
        if f["type"] == "sketch_extrude" and f["params"].get("operation") == "cut"
    ]
    if len(center) != 1:
        raise ValueError("Unexpected retained slot feature structure")
    center[0]["params"]["width"] = 40
    removed = []
    kept = []
    for f in clarified["features"]:
        p = f.get("params", {})
        if (
            f["type"] == "cut_hole"
            and p.get("radius") == 5
            and abs(p.get("x", 0)) == 15
            and p.get("y", 0) == 0
        ):
            removed.append(f["id"])
        else:
            kept.append(f)
    if len(removed) != 2:
        raise ValueError("Expected exactly two round-end cutters")
    clarified["features"] = kept
    output = ROOT / "output/forma/evaluation/slot-clarification"
    output.mkdir(exist_ok=False)
    verdict = public_score(
        task, {"status": "ready", "document": clarified}, output / "clarified"
    )
    rectangle_volume = 80 * 40 * 8 - 40 * 10 * 8 - 4 * math.pi * 3**2 * 8
    rounded_volume = (
        80 * 40 * 8 - ((40 - 10) * 10 + math.pi * 5**2) * 8 - 4 * math.pi * 3**2 * 8
    )
    actual_original = build_document(original)["metrics"]["volume_mm3"]
    actual_clarified = build_document(clarified)["metrics"]["volume_mm3"]
    report = {
        "origin": "Post-hoc explicit human clarification; not a new model run and not included in frozen benchmark aggregate.",
        "instruction": "Use a square-ended rectangular through slot exactly 40 by 10 mm. Preserve the plate and four mounting holes.",
        "original_model_interpretation": "Rounded-end slot, overall 40 by 10 mm",
        "upstream_reference_interpretation": "Square-ended rectangular cut, 40 by 10 mm",
        "removed_round_end_features": removed,
        "original_volume_mm3": actual_original,
        "original_analytic_volume_mm3": rounded_volume,
        "clarified_volume_mm3": actual_clarified,
        "clarified_analytic_volume_mm3": rectangle_volume,
        "original_matches_rounded_formula": abs(actual_original - rounded_volume)
        < 1e-5,
        "clarified_matches_rectangle_formula": abs(actual_clarified - rectangle_volume)
        < 1e-5,
        "clarified_upstream_verdict": verdict,
        "model_calls": 0,
    }
    dump(output / "results.json", report)
    dump(output / "clarified-document.json", clarified)
    if not (
        report["original_matches_rounded_formula"]
        and report["clarified_matches_rectangle_formula"]
        and verdict["passed"]
    ):
        raise AssertionError("Clarification geometry verification failed")
    print(
        {
            "clarified_upstream_score": verdict["overall_score"],
            "included_in_frozen_aggregate": False,
        }
    )


if __name__ == "__main__":
    main()
