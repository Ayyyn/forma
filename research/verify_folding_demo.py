"""Reproducible local folding development checks; no API or public benchmark.

Writes new evidence folders only. It compares exact CAD with exported meshes,
checks a dense prescribed trajectory, and builds provisional print packs.
Physical fit and printer-profile validation remain separate acceptance steps.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from crate_studio.folding import DEFAULTS, DEFAULT_LIMITS, flat_assembly, assembly
from crate_studio.folding_study import folding_study
from crate_studio.folding_print import export_print_pack
from crate_studio.workspace_geometry import export_document, build_document
from crate_studio.workspace_drawing import export_drawings


def render(study, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    palette = ["#407b99", "#6d9a99", "#a6b8a3", "#7595b1"]
    fig = plt.figure(figsize=(16, 5), facecolor="#f5f3ed")
    for n, index in enumerate((0, len(study["frames"]) // 2, -1)):
        frame = study["frames"][index]
        ax = fig.add_subplot(1, 3, n + 1, projection="3d")
        ax.set_facecolor("#f5f3ed")
        all_points = []
        all_faces = []
        face_colors = []
        for part in study["parts"]:
            vertices = np.asarray(part["vertices"]).reshape(-1, 3)
            matrix = np.asarray(frame["pose_matrices"][part["face"]])
            vertices = vertices @ matrix[:3, :3].T + matrix[:3, 3]
            triangles = np.asarray(part["triangles"]).reshape(-1, 3)
            color = (
                "#bf9457"
                if part["kind"] == "pin"
                else palette[part["face"] % len(palette)]
            )
            all_faces.append(vertices[triangles])
            face_colors.extend([color] * len(triangles))
            all_points.append(vertices)
        collection = Poly3DCollection(
            np.concatenate(all_faces),
            facecolors=face_colors,
            edgecolors=face_colors,
            linewidths=0,
            shade=True,
            zsort="average",
        )
        ax.add_collection3d(collection)
        points = np.vstack(all_points)
        lo, hi = points.min(axis=0), points.max(axis=0)
        center = (lo + hi) / 2
        radius = max(hi - lo) * 0.55
        ax.set(
            xlim=(center[0] - radius, center[0] + radius),
            ylim=(center[1] - radius, center[1] + radius),
            zlim=(center[2] - radius, center[2] + radius),
        )
        ax.set_box_aspect([1, 1, 1])
        ax.view_init(elev=30, azim=-65)
        ax.set_axis_off()
        ax.set_title(
            f"Driver {frame['angle_deg']:.1f}° / native solid pose", fontsize=11
        )
    fig.suptitle(
        study["mechanism_family"].replace("_", " ").title()
        + " / actual panels, knuckles and pins",
        fontsize=17,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140, facecolor=fig.get_facecolor())
    plt.close(fig)


def verify(folder, samples, resume=False, documents=None):
    from crate_studio.workspace_workflow import geometry_signature

    folder.mkdir(parents=True, exist_ok=resume)
    results = []
    for family in DEFAULT_LIMITS:
        start = time.perf_counter()
        params = {
            **DEFAULTS,
            "family": family,
            "rows": 4,
            "columns": 4,
            "count": 8,
            "fold_angle": float(DEFAULT_LIMITS[family]),
        }
        document = dict(
            name=family.replace("_", " ").title() + " / articulated print study",
            features=[
                dict(
                    id="fold",
                    type="folding_assembly",
                    name="Articulated panels",
                    params=params,
                )
            ],
            annotations=[],
            display={},
            metadata={
                "brief": "Finite-thickness articulated demonstrator with removable hinge pins.",
                "motion": dict(
                    family="panel_hinges",
                    max_angle_deg=DEFAULT_LIMITS[family],
                    samples=samples,
                ),
            },
        )
        if documents is not None:
            from crate_studio.workspace_server import normalize_document

            document = normalize_document(deepcopy(documents[family]))
            if (
                len(document["features"]) != 1
                or document["features"][0]["type"] != "folding_assembly"
                or document["features"][0]["params"]["family"] != family
            ):
                raise ValueError(
                    "Source documents must contain exactly the named folding family"
                )
            document["metadata"]["motion"] = dict(
                family="panel_hinges",
                max_angle_deg=DEFAULT_LIMITS[family],
                samples=samples,
            )
        target = folder / family
        target.mkdir(exist_ok=resume)
        if (target / "project.json").exists() and json.loads(
            (target / "project.json").read_text()
        ) != document:
            raise ValueError("Resume source document differs from retained evidence")
        (target / "project.json").write_text(
            json.dumps(document, indent=2), encoding="utf-8"
        )
        retained = resume and (target / "motion.json").exists()
        if retained:
            motion_path = target / "motion.json"
            for module in ("folding.py", "folding_study.py"):
                if (
                    Path("crate_studio", module).stat().st_mtime
                    > motion_path.stat().st_mtime
                ):
                    raise ValueError(
                        "Folding engine changed after retained motion; generate fresh evidence in a new folder"
                    )
            study = json.loads(motion_path.read_text())
            if (
                study["geometry_signature"] != geometry_signature(document)
                or study["config"] != document["metadata"]["motion"]
            ):
                raise ValueError(
                    "Retained trajectory does not match the source/configuration"
                )
            elapsed = None
        else:
            study = folding_study(document)
            elapsed = time.perf_counter() - start
            (target / "motion.json").write_text(json.dumps(study), encoding="utf-8")
        if not study["passed"]:
            raise AssertionError(f"{family}: trajectory failed; retained motion.json")
        render(study, target / "native-poses.png")
        geometry = build_document(document)
        exports = export_document(document, None, target / "exports")
        if not exports["checks"]["passed"]:
            raise AssertionError(f"{family}: export roundtrip failed")
        drawing = export_drawings(document, geometry["parts"], target / "exports")
        pack = export_print_pack(document, target / "print-pack")
        row = dict(
            family=family,
            samples=samples,
            trajectory_seconds=elapsed,
            trajectory_generation=(
                "retained completed motion; regenerated exports"
                if retained
                else "fresh native trajectory"
            ),
            trajectory_sha256=hashlib.sha256(
                (target / "motion.json").read_bytes()
            ).hexdigest(),
            passed=study["passed"],
            max_axis_closure_error_mm=study["max_axis_closure_error_mm"],
            native_boolean_checks=sum(
                f["native_boolean_checks"] for f in study["frames"]
            ),
            reused_invariant_checks=sum(
                f["reused_invariant_pairs"] for f in study["frames"]
            ),
            parts=len(study["parts"]),
            plates=len(pack["manifest"]["layout"]),
            export_checks=exports["checks"],
            drawing_measurements=drawing["measurements"],
            total_seconds=time.perf_counter() - start,
        )
        results.append(row)
        (folder / "verification.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    k: row[k]
                    for k in (
                        "family",
                        "samples",
                        "trajectory_seconds",
                        "total_seconds",
                        "parts",
                        "plates",
                        "passed",
                    )
                }
            ),
            flush=True,
        )
    coupon = flat_assembly({**DEFAULTS, "family": "concertina", "count": 2})
    a, b, pin = [p["shape"] for p in coupon["parts"]]
    # Independent native surface distances for the actual small hinge, not an
    # asserted global minimum over an entire moving mechanism.
    hardware = dict(
        panel_to_panel_mm=a.distance(b),
        pin_to_first_panel_mm=pin.distance(a),
        pin_to_second_panel_mm=pin.distance(b),
    )
    np.testing.assert_allclose(list(hardware.values()), [0.35, 0.25, 0.25], atol=1e-6)
    (folder / "coupon-native-clearances.json").write_text(
        json.dumps(hardware, indent=2), encoding="utf-8"
    )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=361)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed native motion only when source/configuration and engine file dates match; reported explicitly as retained",
    )
    parser.add_argument(
        "--documents",
        type=Path,
        help="JSON mapping of all five families to source documents, for verification of exact generated/human-edited designs",
    )
    args = parser.parse_args()
    verify(
        args.output,
        args.samples,
        args.resume,
        (
            json.loads(args.documents.read_text(encoding="utf-8"))
            if args.documents
            else None
        ),
    )
