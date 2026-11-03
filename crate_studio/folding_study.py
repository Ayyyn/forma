"""Native-solid sampled motion studies for the supported folding feature."""

from copy import deepcopy
from functools import lru_cache
import json

import cadquery as cq
import numpy as np

from .folding import (
    ABSOLUTE_LIMITS,
    DEFAULT_LIMITS,
    specification,
    flat_assembly,
    assembly,
    transforms,
    closure,
    collisions,
    _native_bounds,
)


def folding_feature(document):
    active = [f for f in document.get("features", []) if not f.get("suppressed")]
    folds = [f for f in active if f.get("type") == "folding_assembly"]
    if not folds:
        return None
    if len(folds) != 1 or len(active) != 1:
        raise ValueError(
            "A folding study requires one unmodified folding feature. Edit its parameters, or retain custom edits as a separate static CAD revision."
        )
    return folds[0]


@lru_cache(maxsize=8)
def _trajectory(key):
    from .workspace_geometry import _mesh

    p, config = json.loads(key)
    template = flat_assembly(p)
    meshes = [
        {k: v for k, v in part.items() if k not in ("shape", "axis", "start")}
        | _mesh(part["shape"].copy())
        for part in template["parts"]
    ]
    frames = []
    pair_cache = {}
    for angle in np.linspace(0, config["max_angle_deg"], config["samples"]):
        value = assembly(p, float(angle))
        error = closure(value["graph"], value["poses"], p["hinge_radius"])
        c = collisions(value["parts"], pair_cache=pair_cache if error < 1e-8 else None)
        lo, hi = _native_bounds(
            cq.Compound.makeCompound([x["shape"] for x in value["parts"]])
        )
        frames.append(
            dict(
                angle_deg=float(angle),
                bounds_min_mm=lo.tolist(),
                bounds_max_mm=hi.tolist(),
                extent_mm=(hi - lo).tolist(),
                overlaps=[x["parts"] for x in c["overlaps"]],
                collision_details=c["overlaps"],
                minimum_clearance_mm=c["minimum_clearance_mm"],
                native_distance_checks=c["native_distance_checks"],
                native_boolean_checks=c["native_pair_checks"],
                reused_invariant_pairs=c["reused_pair_checks"],
                axis_closure_error_mm=error,
                pose_matrices=value["poses"],
            )
        )
    passing = all(
        not f["overlaps"] and f["axis_closure_error_mm"] < 1e-7 for f in frames
    )
    return dict(
        family="panel_hinges",
        mechanism_family=p["family"],
        config=config,
        parts=meshes,
        panels=[
            dict(id=f"panel_{i+1:03d}", face=i)
            for i in range(len(template["graph"]["faces"]))
        ],
        graph=template["graph"],
        joints=template["joints"],
        frames=frames,
        passed=passing,
        sampled_overlap_free=all(not f["overlaps"] for f in frames),
        collision_sample_count=sum(bool(f["overlaps"]) for f in frames),
        max_axis_closure_error_mm=max(f["axis_closure_error_mm"] for f in frames),
        specified_radial_clearance_mm=p["radial_clearance"],
        specified_axial_clearance_mm=p["axial_clearance"],
        reuse_scope="Same rigid face group, or the generated axisymmetric pin and either adjacent panel; cache is local to one exact trajectory specification, with hinge closure checked before reuse",
        minimum_sampled_clearance_mm=None,
        scope="Real finite-thickness panels, bored hinge knuckles and removable pins. Exact native BREP positive-volume interference checks at every reported sampled pose; hinge-axis endpoints must coincide. Pin/bore and knuckle gaps are explicit design dimensions, not a global minimum-clearance measurement. Prescribed rigid kinematics, not forces, friction, retention, fatigue, a continuous swept-volume proof or physical validation.",
    )


def folding_study(document, config=None):
    from .workspace_workflow import geometry_signature, validate_motion

    feature = folding_feature(document)
    if feature is None:
        raise ValueError("No supported folding feature in this document")
    p = specification(feature["params"])
    default = dict(
        family="panel_hinges", max_angle_deg=DEFAULT_LIMITS[p["family"]], samples=73
    )
    selected = (
        config
        if config is not None
        else document.get("metadata", {}).get("motion", default)
    )
    selected = validate_motion(selected)
    if selected["family"] != "panel_hinges":
        raise ValueError("This CAD revision needs a panel-hinge folding study")
    if selected["max_angle_deg"] > ABSOLUTE_LIMITS[p["family"]]:
        raise ValueError(
            f"{p['family']} supports a driver angle up to {ABSOLUTE_LIMITS[p['family']]} degrees"
        )
    p["fold_angle"] = 0.0
    result = deepcopy(_trajectory(json.dumps([p, selected], sort_keys=True)))
    result["geometry_signature"] = geometry_signature(document)
    return result
