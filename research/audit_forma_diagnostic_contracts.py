"""Read-only public diagnostic audit; never alters tasks, references or scores."""

import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np
from shapely import get_coordinates
from shapely.geometry import Polygon, LineString

from research.run_forma_full17 import ROOT, dump, digest, load


def main():
    output = ROOT / "output/forma/diagnostic-dev/contract-audit"
    output.mkdir(exist_ok=True)
    source = ROOT / "research/vendor/cad-bench"
    frozen = load(ROOT / "evaluation/forma-full17-v1/protocol.json")
    assert all(
        digest(source / name) == sha for name, sha in frozen["upstream_hashes"].items()
    )
    spur_path = (
        ROOT
        / "output/forma/evaluation/full17-v1/forma/spur_gear_m1_z16_t6_bore5/candidate.step"
    )
    spur = cq.importers.importStep(str(spur_path)).val()
    face = cq.Workplane(obj=spur).faces(">Z").val()
    points, _ = face.outerWire().sample(0.0001)
    xy = np.array([[p.x, p.y] for p in points])
    polygon = Polygon(xy)
    radii = []
    for angle in np.linspace(0, math.tau, 720, endpoint=False):
        ray = LineString([(0, 0), (20 * math.cos(angle), 20 * math.sin(angle))])
        hits = get_coordinates(ray.intersection(polygon.boundary))
        radii.append(float(np.linalg.norm(hits, axis=1).max()))
    r30, r70 = np.quantile(radii, [0.3, 0.7])
    spur_audit = {
        "source_step_sha256": digest(spur_path),
        "outline_deflection_mm": 0.0001,
        "measured_outer_diameter_mm": float(2 * np.linalg.norm(xy, axis=1).max()),
        "measured_minimum_root_diameter_mm": float(
            2 * np.linalg.norm(xy, axis=1).min()
        ),
        "radial_quantile_30_mm": float(r30),
        "radial_quantile_70_mm": float(r70),
        "quantile_depth_proxy_mm": float(r70 - r30),
        "scorer_expected_quantile_depth_mm": (18 - 13.5) / 2,
        "finding": "Actual outer/root dimensions and angular quantile proxies are different measurements; matching dimensions alone does not satisfy this score",
    }
    screw_path = (
        ROOT
        / "output/forma/evaluation/full17-thread-repair/forma/m3x6_socket_head_zminus/candidate.step"
    )
    screw = cq.importers.importStep(str(screw_path)).val()
    cavity = screw.isInside(cq.Vector(0, 0, -1.49), 1e-6)
    floor = screw.isInside(cq.Vector(0, 0, -1.51), 1e-6)
    assert not cavity and floor
    screw_audit = {
        "source_step_sha256": digest(screw_path),
        "brief_depth_mm": 1.5,
        "scorer_fixed_reference_depth_mm": 2,
        "inside_material_above_floor": cavity,
        "inside_material_below_floor": floor,
        "finding": "The modeled floor follows the explicit brief; the fixed reference depth comparator differs",
    }
    lead, starts = 2.7, 2
    phases = []
    for i in range(starts):
        rotation = math.tau * i / starts
        translation = i * lead / starts
        phase = (rotation - math.tau * translation / lead) % math.tau
        phases.append(phase)
    assert max(phases) - min(phases) < 1e-12
    thread_audit = {
        "lead_mm": lead,
        "requested_starts": starts,
        "reference_net_helix_start_phases_rad": phases,
        "formula": "phase_i = rotation_i - 2*pi*axial_translation_i/lead",
        "finding": "Reference start rotation and axial translation cancel over the overlapping helix interval. End truncation can still differ. Do not substitute this for independent full-geometry fit checks.",
        "reference_sha256": digest(
            source / "dataset/custom_threaded_pair_nonstandard/solution/gold.py"
        ),
    }
    data = {
        "mode": "Public diagnostic contract audit; original scores and upstream code unchanged",
        "upstream_commit": frozen["upstream_commit"],
        "spur": spur_audit,
        "screw": screw_audit,
        "thread": thread_audit,
    }
    dump(output / "audit.json", data)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
