"""Development-only comparison of retained Miura research and Studio motion scope.

No benchmark tasks, model requests, material mechanics or integration claims.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from continuum.geometry import Design, mesh, validate_geometry, export_fold, export_svg
from continuum.audit import reference_vertices
from crate_studio.workspace_workflow import motion_study, validate_motion


def audit(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    designs = [
        Design(columns=4, rows=4, a_mm=20, b_mm=20, gamma_deg=60),
        Design(columns=10, rows=6, a_mm=24, b_mm=28, gamma_deg=72),
        Design(
            columns=16, rows=12, a_mm=12, b_mm=15, gamma_deg=45, packed_theta_deg=88
        ),
    ]
    checks = []
    for design in designs:
        checks.append(
            {
                "design": design.model_dump(),
                "rigid_facets": validate_geometry(design, samples=41),
                "max_reference_vertex_delta_mm": max(
                    float(
                        np.max(
                            np.abs(
                                np.asarray(mesh(design, float(angle))["vertices"])
                                - reference_vertices(design.model_dump(), float(angle))
                            )
                        )
                    )
                    for angle in np.linspace(0, design.packed_theta_deg, 41)
                ),
            }
        )
    try:
        validate_motion({"family": "miura"})
        rejected_family = False
    except ValueError as error:
        rejected_family = str(error)
    try:
        motion_study({"features": [], "metadata": {}})
        rejected_custom = False
    except ValueError as error:
        rejected_custom = str(error)
    design = designs[0]
    (destination / "miura-flat.fold").write_text(
        json.dumps(export_fold(design), indent=2), encoding="utf-8"
    )
    (destination / "miura-pattern.svg").write_text(export_svg(design), encoding="utf-8")
    frames = [{"angle_deg": angle, **mesh(design, angle)} for angle in (0, 30, 60, 85)]
    (destination / "miura-frames.json").write_text(
        json.dumps(frames, indent=2), encoding="utf-8"
    )
    fig = plt.figure(figsize=(13, 4.2), layout="constrained")
    for i, frame in enumerate(frames):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d")
        vertices = np.asarray(frame["vertices"])
        ax.add_collection3d(
            Poly3DCollection(
                [vertices[f] for f in frame["faces"]],
                facecolors="#b8d8d4",
                edgecolors="#355d62",
                linewidths=0.7,
                alpha=0.95,
            )
        )
        ax.set(
            xlim=(0, 95),
            ylim=(0, 80),
            zlim=(0, 22),
            title=f'{frame["angle_deg"]} degrees',
            xlabel="X (mm)",
            ylabel="Y (mm)",
            zlabel="Z (mm)",
        )
        ax.set_box_aspect((95, 80, 22))
        ax.view_init(elev=30, azim=-65)
    fig.suptitle(
        "Retained Miura research: ideal rigid kinematics, zero thickness\n4 x 4 facets; not integrated into Forma Studio or qualified for printing",
        fontsize=12,
    )
    fig.savefig(destination / "miura-reference-states.png", dpi=160)
    plt.close(fig)
    report = {
        "scope": "Development reference audit, not the reserved unseen evaluator",
        "reference": "Schenk & Guest (2013), Geometry of Miura-folded metamaterials, https://doi.org/10.1073/pnas.1217998110",
        "comparison_method": "Retained independent unsimplified unit-cell parameterization versus mesh coordinates; rigid edge/diagonal, area and planarity checks over 41 sampled states each",
        "cases": checks,
        "studio_miura_family_rejection": rejected_family,
        "studio_custom_geometry_rejection": rejected_custom,
        "ideal_research_passed": all(
            x["rigid_facets"]["passed"] and x["max_reference_vertex_delta_mm"] < 1e-8
            for x in checks
        ),
        "product_complex_folding_acceptance": False,
        "missing": [
            "shared CAD/crease graph",
            "editable hinge constraints and loop closure",
            "finite-thickness interference and clearance",
            "FOLD import/export in Studio",
            "material/hinge mechanics and physical validation",
        ],
    }
    (destination / "audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    audit(parser.parse_args().destination)
