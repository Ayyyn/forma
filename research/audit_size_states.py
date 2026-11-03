"""Independent native pose/ray controls for a selected development mechanism.

Not a new model run: rebuild source, apply native operations without the planner's
matrix application, and cross-check horizontal coverage using vertical rays.
"""

import argparse
import json
from pathlib import Path

import cadquery as cq
import numpy as np
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt

from crate_studio.workspace_geometry import build_document, _bounds, _mesh
from crate_studio.mechanism_study import mechanism_study, validate_spec
from crate_studio.floor_check import floor_coverage


def direct_pose(parts, spec, values):
    paths = {spec["root"]: []}
    for joint in spec["joints"]:
        paths[joint["child"]] = paths[joint["parent"]] + [joint]
    result = []
    for part in parts:
        shape = part["shape"].copy()
        for joint in reversed(paths[part["id"]]):
            q = values[joint["id"]]
            if joint["type"] == "prismatic":
                shape = shape.translate(tuple(q * x for x in joint["axis"]))
            elif joint["type"] == "revolute":
                a = joint["origin"]
                b = [x + y for x, y in zip(a, joint["axis"])]
                shape = shape.rotate(a, b, q)
        result.append({"id": part["id"], "shape": shape})
    return result


def run(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    data = json.loads(source.read_text(encoding="utf-8"))
    proposal = data["proposal"]
    doc = proposal["document"]
    built = build_document(doc)
    if not built["checks"]["passed"]:
        raise ValueError("Source did not rebuild as valid native solids")
    spec = validate_spec(
        doc["metadata"]["design_mechanism"], [p["id"] for p in built["parts"]]
    )
    trajectory = mechanism_study(doc, built, spec)
    (destination / "motion.json").write_text(
        json.dumps(trajectory, indent=2), encoding="utf-8"
    )
    reference = data.get("target_reference") or proposal.get("design_review", {})
    states, meshes = [], []
    for index, state in enumerate(spec["states"]):
        parts = direct_pose(built["parts"], spec, state["values"])
        shape = cq.Compound.makeCompound([p["shape"] for p in parts])
        bounds = _bounds(shape)
        floor = reference["reports"]["floor:state:" + state["name"]]
        coverage, *_ = floor_coverage(parts, floor["footprint"])
        target = coverage["footprint"]
        ray = IntCurvesFace_ShapeIntersector()
        ray.Load(shape.wrapped, 1e-7)
        missed = []
        # Off-boundary grid points test actual vertical CAD intersections, not
        # the face-projection union. The projection remains the coverage test.
        x, y = target["center_xy"]
        w, d = target["size_mm"]
        lo, hi = target["z_range_mm"]
        for xx in np.linspace(x - w / 2 + 0.013, x + w / 2 - 0.013, 25):
            for yy in np.linspace(y - d / 2 + 0.017, y + d / 2 - 0.017, 25):
                ray.Perform(
                    gp_Lin(gp_Pnt(float(xx), float(yy), lo - 1e-6), gp_Dir(0, 0, 1)),
                    0,
                    hi - lo + 2e-6,
                )
                if not ray.IsDone() or ray.NbPnt() == 0:
                    missed.append([float(xx), float(yy)])
        frame = (
            trajectory["frames"][0]
            if index == 0
            else next(
                f
                for f in trajectory["frames"]
                if f["segment"] == index - 1 and abs(f["fraction"] - 1) < 1e-8
            )
        )
        delta = max(
            abs(a - b)
            for aa, bb in zip(bounds, frame["bounds_mm"])
            for a, b in zip(aa, bb)
        )
        part_volume_error = max(
            abs(p["shape"].Volume() - q["shape"].Volume())
            for p, q in zip(parts, built["parts"])
        )
        margins = [
            x - w / 2 - bounds[0][0],
            bounds[1][0] - (x + w / 2),
            y - d / 2 - bounds[0][1],
            bounds[1][1] - (y + d / 2),
        ]
        states.append(
            {
                "name": state["name"],
                "floor_mm": [w, d],
                "outer_size_mm": [bounds[1][i] - bounds[0][i] for i in range(3)],
                "outside_floor_margins_mm": dict(
                    zip(("left", "right", "front", "back"), margins)
                ),
                "native_pose_bounds_error_mm": delta,
                "part_volume_error_mm3": part_volume_error,
                "floor_coverage": coverage,
                "native_ray_count": 625,
                "missed_native_rays": missed[:20],
                "passed": coverage["passed"]
                and not missed
                and delta < 1e-6
                and part_volume_error < 1e-5,
            }
        )
        meshes.append([{**_mesh(p["shape"]), "id": p["id"]} for p in parts])
    report = {
        "source": str(source),
        "fresh_model_call": False,
        "source_run_id": proposal["run_id"],
        "source_kind": data.get("source_kind", "selected_geometry_proposal"),
        "states": states,
        "motion_passed": trajectory["passed"],
        "sample_count": trajectory["sample_count"],
        "passed": trajectory["passed"] and all(s["passed"] for s in states),
        "scope": "Independent source rebuild and native per-joint shape operations; direct ray-grid support controls complement the face-union coverage check. Same four source solids/volumes in all states. No guides, locks, force, flatness or physical qualification.",
    }
    (destination / "verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(12, 10), facecolor="#f7f5f0")
    radius = max(max(s["outer_size_mm"]) for s in states) * 0.6
    for index, (state, parts) in enumerate(zip(states, meshes)):
        ax = fig.add_subplot(2, 2, index + 1, projection="3d")
        ax.set_facecolor("#f7f5f0")
        for j, mesh in enumerate(parts):
            v = np.array(mesh["vertices"]).reshape(-1, 3)
            t = np.array(mesh["triangles"]).reshape(-1, 3)
            ax.add_collection3d(
                Poly3DCollection(
                    v[t],
                    facecolor=("#8babb6", "#cfad7d", "#98b79a", "#b19bb8")[j % 4],
                    edgecolor="#53656a",
                    linewidth=0.12,
                )
            )
        bounds = (
            trajectory["frames"][0]["bounds_mm"]
            if index == 0
            else next(
                f["bounds_mm"]
                for f in trajectory["frames"]
                if f["segment"] == index - 1 and abs(f["fraction"] - 1) < 1e-8
            )
        )
        center = np.array(bounds).mean(axis=0)
        for setter, c in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center):
            setter(c - radius, c + radius)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=32, azim=-55)
        ax.set_axis_off()
        ax.set_title(
            f"{state['name']}: floor {state['floor_mm'][0]:g} x {state['floor_mm'][1]:g} mm\nouter {state['outer_size_mm'][0]:g} x {state['outer_size_mm'][1]:g} mm",
            fontsize=11,
        )
    fig.suptitle("Same finite-thickness source parts / actual named poses", fontsize=16)
    fig.text(
        0.5,
        0.03,
        "Common view scale. Independent native pose/ray controls; guides and locks remain unverified.",
        ha="center",
        fontsize=10,
    )
    fig.savefig(
        destination / "four-states.png",
        dpi=140,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "samples": report["sample_count"],
                "states": [
                    {
                        k: s[k]
                        for k in (
                            "name",
                            "floor_mm",
                            "outer_size_mm",
                            "outside_floor_margins_mm",
                            "passed",
                        )
                    }
                    for s in states
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    run(args.source, args.destination)
