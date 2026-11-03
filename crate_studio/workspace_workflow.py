"""Revision-bound enclosure editing and finite-thickness wall motion studies."""

from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np

from .engine import (
    DEFAULT_SPEC,
    DEFAULT_REQUIREMENTS,
    evaluate,
    normalize_spec,
    normalize_requirements,
)
from .workspace_requirements import enclosure_features, requirement_state


def geometry_signature(document):
    def canonical(value):
        if isinstance(value, dict):
            return {k: canonical(v) for k, v in value.items()}
        if isinstance(value, list):
            return [canonical(v) for v in value]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return value

    definition = [
        (
            {
                k: f.get(k, False if k == "suppressed" else None)
                for k in ("id", "type", "params", "suppressed")
            }
            if isinstance(f, dict)
            else f
        )
        for f in document["features"]
    ]
    return hashlib.sha256(
        json.dumps(canonical(definition), sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def revise_enclosure(document, spec, requirements, replace_geometry=False):
    """Replace only a recognized panel definition unless replacement is explicit."""
    state = requirement_state(document)
    if document["features"] and state["status"] != "current" and not replace_geometry:
        raise ValueError(
            "This design has custom geometry. Explicitly choose Replace geometry to rebuild enclosure panels; the previous revision remains available."
        )
    checked = evaluate(spec, requirements)
    doc = deepcopy(document)
    doc["name"] = checked["spec"]["name"]
    doc["features"] = enclosure_features(checked["panels"])
    metadata = doc.setdefault("metadata", {})
    metadata.update(
        source_crate_id=metadata.get("source_crate_id") or "studio-enclosure",
        source_spec=checked["spec"],
        source_requirements=checked["requirements"],
    )
    doc.setdefault("display", {}).update(
        body_names={
            f"body_{i+1:03d}": p["name"] for i, p in enumerate(checked["panels"])
        },
        hidden_parts=[],
        colors={},
    )
    return doc


def rotation(axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (
        np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
        if axis == "x"
        else np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    )


def interior_overlap(a, b, tolerance=1e-7):
    """Separating-axis test on all face normals and edge cross products of two OBBs.

    Touching is allowed. Reports positive-volume overlap; not surface clearance.
    """
    axes = [*a["axes"].T, *b["axes"].T]
    axes += [np.cross(x, y) for x in a["axes"].T for y in b["axes"].T]
    delta = b["center"] - a["center"]
    for axis in axes:
        length = np.linalg.norm(axis)
        if length < 1e-10:
            continue
        axis = axis / length
        ra = np.sum(a["half"] * np.abs(a["axes"].T @ axis))
        rb = np.sum(b["half"] * np.abs(b["axes"].T @ axis))
        if ra + rb - abs(delta @ axis) <= tolerance:
            return False
    return True


def wall_definitions(spec):
    source = evaluate(spec)
    w, d, t = (spec[k] for k in ("inner_width_mm", "inner_depth_mm", "thickness_mm"))
    hinges = {
        "front": ([0, -d / 2 - t, t], "x", 1),
        "back": ([0, d / 2 + t, t], "x", -1),
        "left": ([-w / 2 - t, 0, t], "y", -1),
        "right": ([w / 2 + t, 0, t], "y", 1),
    }
    return [
        {
            **p,
            "pivot_mm": hinges.get(p["id"], ([0, 0, 0], "x", 0))[0],
            "axis": hinges.get(p["id"], (None, "x", 0))[1],
            "direction": hinges.get(p["id"], (None, None, 0))[2],
        }
        for p in source["panels"]
    ]


def wall_frame(definitions, angle_deg):
    boxes, vertices = [], []
    for p in definitions:
        pivot = np.array(p["pivot_mm"], dtype=float)
        matrix = rotation(p["axis"], math.radians(angle_deg * p["direction"]))
        center = pivot + matrix @ (np.array(p["center_mm"]) - pivot)
        half = np.array(p["size_mm"]) / 2
        corners = [
            center + matrix @ (half * signs)
            for signs in itertools.product((-1, 1), repeat=3)
        ]
        vertices.extend(corners)
        boxes.append({"id": p["id"], "center": center, "half": half, "axes": matrix})
    points = np.array(vertices)
    pairs = [
        [a["id"], b["id"]]
        for a, b in itertools.combinations(boxes, 2)
        if interior_overlap(a, b)
    ]
    return {
        "angle_deg": angle_deg,
        "bounds_min_mm": points.min(axis=0).tolist(),
        "bounds_max_mm": points.max(axis=0).tolist(),
        "extent_mm": np.ptp(points, axis=0).tolist(),
        "overlaps": pairs,
    }


def motion_study(document, config=None, asset_loader=None):
    from .folding_study import folding_feature, folding_study

    if config and config.get("family") == "assembly":
        from .assembly_study import assembly_study
        from .workspace_cache import cached_build

        if set(config) != {"family"}:
            raise ValueError("Assembly sampling is controlled by the saved assembly plan")
        plan = document.get("metadata", {}).get("assembly_plan")
        if not plan:
            raise ValueError("No checked assembly plan has been saved for this design")
        built = cached_build(document, asset_loader)
        result = assembly_study(document, built, plan)
        result.update(
            family="general_mechanism", study_kind="assembly", assembly_plan=result["spec"],
            spec={"states": [{"name": "Separated parts"}, *[{"name": step["name"]} for step in result["spec"]["steps"]]]},
            parts=deepcopy(built["mesh"]),
            config={"family":"assembly","progress_max":100,"samples":result["sample_count"]},
            sampled_overlap_free=not result["collision_sample_count"],
        )
        return result

    if document.get("metadata", {}).get("design_mechanism"):
        from .mechanism_study import mechanism_study
        from .workspace_cache import cached_build

        spec = deepcopy(document["metadata"]["design_mechanism"])
        if config:
            if config.get("family") != "general_mechanism" or set(config) != {
                "family",
                "samples_per_segment",
            }:
                raise ValueError(
                    "Generic mechanism settings require family and samples_per_segment"
                )
            spec["samples_per_segment"] = config["samples_per_segment"]
        built = cached_build(document, asset_loader)
        result = mechanism_study(document, built, spec)
        result.update(
            family="general_mechanism",
            parts=deepcopy(built["mesh"]),
            config={
                "family": "general_mechanism",
                "progress_max": 100,
                "samples": spec["samples_per_segment"],
            },
            sampled_overlap_free=not result["collision_sample_count"],
        )
        return result
    if folding_feature(document) is not None:
        return folding_study(document, config)
    if requirement_state(document)["status"] != "current":
        raise ValueError(
            "Wall motion requires the current supported enclosure panel definition. Rebuild the enclosure before simulating custom geometry."
        )
    spec = normalize_spec(document["metadata"]["source_spec"])
    if spec["lid"]:
        raise ValueError(
            "Remove the top panel in Project before running the open-wall motion study."
        )
    config = validate_motion(config or document.get("metadata", {}).get("motion", {}))
    definitions = wall_definitions(spec)
    frames = [
        wall_frame(definitions, config["max_angle_deg"] * i / (config["samples"] - 1))
        for i in range(config["samples"])
    ]
    collisions = [f for f in frames if f["overlaps"]]
    return {
        "family": "enclosure_walls",
        "geometry_signature": geometry_signature(document),
        "config": config,
        "panels": definitions,
        "frames": frames,
        "sampled_overlap_free": not collisions,
        "collision_sample_count": len(collisions),
        "scope": "Rigid finite-thickness rectangular panels rotating outward about virtual hinges on the base outer top edges. Simultaneous prescribed motion; touching allowed. Sampled positive-volume OBB overlap checks, not a continuous swept-volume proof. Hinges, fasteners, flexibility, loads and physical validation are not modeled.",
    }


def validate_motion(config):
    if not isinstance(config, dict) or set(config) - {
        "family",
        "max_angle_deg",
        "samples",
    }:
        raise ValueError("Unsupported motion settings")
    c = {"family": "enclosure_walls", "max_angle_deg": 90.0, "samples": 37, **config}
    if c["family"] not in ("enclosure_walls", "panel_hinges"):
        raise ValueError("Unsupported motion family")
    if (
        isinstance(c["max_angle_deg"], bool)
        or not isinstance(c["max_angle_deg"], (int, float))
        or not math.isfinite(c["max_angle_deg"])
        or not 1
        <= c["max_angle_deg"]
        <= (90 if c["family"] == "enclosure_walls" else 170)
    ):
        raise ValueError("Motion driver angle is outside the supported range")
    maximum_samples = 73 if c["family"] == "enclosure_walls" else 721
    if type(c["samples"]) is not int or not 5 <= c["samples"] <= maximum_samples:
        raise ValueError(
            f"Motion samples must be an integer from 5 to {maximum_samples}"
        )
    return c


def export_panel_pack(document, folder):
    """Separate, flat panel solids for a fabrication mockup, with mesh read-back."""
    import cadquery as cq
    import trimesh

    if requirement_state(document)["status"] != "current":
        raise ValueError("Panel pack requires the supported enclosure definition")
    source = evaluate(
        document["metadata"]["source_spec"], document["metadata"]["source_requirements"]
    )
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for panel in source["panels"]:
        x, y, z = panel["size_mm"]
        thickness = source["spec"]["thickness_mm"]
        width, depth = (
            (x, y)
            if panel["id"] in ("base", "lid")
            else (x, z) if panel["id"] in ("front", "back") else (y, z)
        )
        shape = (
            cq.Workplane("XY")
            .box(width, depth, thickness, centered=(False, False, False))
            .val()
        )
        stem = "panel-" + panel["id"]
        cq.exporters.export(shape, str(destination / (stem + ".stl")))
        cq.exporters.export(shape, str(destination / (stem + ".step")))
        mesh = trimesh.load(destination / (stem + ".stl"), force="mesh", process=True)
        expected = x * y * z
        passed = bool(
            mesh.is_watertight
            and mesh.is_winding_consistent
            and abs(mesh.volume - expected) <= max(1e-5, expected * 1e-6)
        )
        if not passed:
            raise ValueError("Panel mesh verification failed: " + panel["id"])
        rows.append(
            {
                "panel": panel["id"],
                "flat_size_mm": [width, depth, thickness],
                "volume_mm3": expected,
                "stl_verified": passed,
                "files": [stem + ".stl", stem + ".step"],
            }
        )
    result = {
        "geometry_signature": geometry_signature(document),
        "panels": rows,
        "requirements": source["checks"],
        "instructions": "Separate flat panel components, in mm with bottoms at Z=0. Print one per file or arrange them in your slicer. Confirm printer bed fit, filament dimensions and clearances before a complete run. A tape or external hinge mockup can approximate the virtual axes at the base outer top edges. Hinge hardware is not designed or included. Material density/load assumptions in the project do not qualify the printed material. Record actual dimensions and motion; physical validation is pending.",
    }
    (destination / "panel-pack.json").write_text(
        json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
    )
    return result
