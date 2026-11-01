"""Exact ideal accordion/Miura kinematics; see docs/GEOMETRY.md for derivation."""
import hashlib
import json
import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Design(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    family: Literal["miura", "accordion"] = "miura"
    columns: int = Field(10, ge=2, le=16)
    rows: int = Field(6, ge=1, le=12)
    a_mm: float = Field(24, ge=5, le=100)
    b_mm: float = Field(28, ge=5, le=250)
    gamma_deg: float = Field(72, ge=25, le=90)
    deployed_theta_deg: float = Field(8, ge=0, le=25)
    packed_theta_deg: float = Field(86, ge=1, le=88)

    @model_validator(mode="after")
    def compatible(self):
        if self.packed_theta_deg <= self.deployed_theta_deg:
            raise ValueError("Packed angle must exceed deployed angle")
        if self.family == "accordion" and self.gamma_deg != 90:
            raise ValueError("Accordion requires gamma_deg=90")
        if self.family == "accordion" and self.rows != 1:
            raise ValueError("Accordion uses rows=1; coplanar subdivisions are not fabrication creases")
        if self.family == "miura" and self.rows < 2:
            raise ValueError("Miura requires at least two rows")
        if self.family == "miura" and self.gamma_deg > 85:
            raise ValueError("Miura sector angle must be at most 85 degrees")
        return self


class Requirements(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    deployed_x_min_mm: float = Field(240, ge=20, le=1000)
    deployed_y_min_mm: float = Field(150, ge=20, le=1000)
    packed_long_max_mm: float = Field(120, ge=10, le=1000)
    packed_short_max_mm: float = Field(45, ge=5, le=1000)
    packed_height_max_mm: float = Field(24, ge=1, le=200)
    blank_x_max_mm: float = Field(277, ge=20, le=1000)
    blank_y_max_mm: float = Field(190, ge=20, le=1000)
    crease_segments_max: int = Field(160, ge=4, le=400)


def cell(design: Design, theta_deg: float):
    if not math.isfinite(theta_deg) or not 0 <= theta_deg < 89:
        raise ValueError("Folding angle must be finite and in [0,89) degrees")
    theta, gamma = map(math.radians, (theta_deg, design.gamma_deg))
    q = math.sqrt(1 - (math.sin(theta) * math.sin(gamma)) ** 2)
    h = design.a_mm * math.sin(theta) * math.sin(gamma)
    length = design.a_mm * q
    offset = design.b_mm * math.cos(gamma) / q
    spacing = design.b_mm * math.sin(gamma) * math.cos(theta) / q
    return length, spacing, offset, h


def mesh(design: Design, theta_deg: float):
    length, spacing, offset, h = cell(design, theta_deg)
    n, m = design.columns, design.rows
    vertices = [[i * length + (j % 2) * offset, j * spacing, (i % 2) * h]
                for j in range(m + 1) for i in range(n + 1)]
    index = lambda i, j: j * (n + 1) + i
    faces = [[index(i, j), index(i + 1, j), index(i + 1, j + 1), index(i, j + 1)]
             for j in range(m) for i in range(n)]
    edge_faces = {}
    for fi, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            edge_faces.setdefault(tuple(sorted((a, b))), []).append(fi)
    edges = [{"vertices": list(edge), "faces": adjacent, "boundary": len(adjacent) == 1}
             for edge, adjacent in edge_faces.items()]
    return {"vertices": vertices, "faces": faces, "edges": edges, "theta_deg": theta_deg}


def dimensions(design: Design, theta_deg: float):
    length, spacing, offset, h = cell(design, theta_deg)
    return {"x_mm": design.columns * length + offset, "y_mm": design.rows * spacing, "z_mm": h}


def metrics(design: Design):
    deployed = dimensions(design, design.deployed_theta_deg)
    packed = dimensions(design, design.packed_theta_deg)
    flat = dimensions(design, 0)
    area = design.rows * design.columns * design.a_mm * design.b_mm * math.sin(math.radians(design.gamma_deg))
    return {"deployed": deployed, "packed": packed, "flat": flat,
            "material_area_mm2": area,
            "projected_coverage_mm2": area * math.cos(math.radians(design.deployed_theta_deg)),
            "packed_bounding_area_mm2": packed["x_mm"] * packed["y_mm"],
            "footprint_expansion_ratio": deployed["x_mm"] * deployed["y_mm"] / (packed["x_mm"] * packed["y_mm"]),
            "crease_segments": (design.columns - 1) * design.rows + (design.rows - 1) * design.columns,
            "facet_count": design.rows * design.columns,
            "blank_utilization": area / (flat["x_mm"] * flat["y_mm"])}


def evaluate(design: Design, requirements: Requirements):
    result = metrics(design)
    d, p, f = result["deployed"], result["packed"], result["flat"]
    tests = [
        ("Deployed length", d["x_mm"], ">=", requirements.deployed_x_min_mm, "mm"),
        ("Deployed width", d["y_mm"], ">=", requirements.deployed_y_min_mm, "mm"),
        ("Packed long side", max(p["x_mm"], p["y_mm"]), "<=", requirements.packed_long_max_mm, "mm"),
        ("Packed short side", min(p["x_mm"], p["y_mm"]), "<=", requirements.packed_short_max_mm, "mm"),
        ("Packed corrugation height", p["z_mm"], "<=", requirements.packed_height_max_mm, "mm"),
        ("Printable blank length", f["x_mm"], "<=", requirements.blank_x_max_mm, "mm"),
        ("Printable blank width", f["y_mm"], "<=", requirements.blank_y_max_mm, "mm"),
        ("Crease segments", result["crease_segments"], "<=", requirements.crease_segments_max, "segments"),
    ]
    constraints, penalty = [], 0
    for name, value, comparator, limit, unit in tests:
        violation = max(0, limit - value if comparator == ">=" else value - limit)
        penalty += violation / max(limit, 1)
        constraints.append({"name": name, "value": value, "comparator": comparator, "limit": limit,
                            "unit": unit, "passed": violation < 1e-7, "violation": violation})
    identifier = hashlib.sha256(json.dumps(design.model_dump(), sort_keys=True).encode()).hexdigest()[:10]
    return {"id": identifier, "design": design.model_dump(), "metrics": result, "constraints": constraints,
            "feasible": all(c["passed"] for c in constraints), "normalized_violation": penalty,
            "score": penalty * 100 + result["material_area_mm2"] / 50000 + result["crease_segments"] / 160 + result["packed_bounding_area_mm2"] / 5400}


def validate_geometry(design: Design, samples=21):
    flat = mesh(design, 0)
    reference = np.asarray(flat["vertices"])
    max_distance, max_area, max_planarity, max_extent = 0., 0., 0., 0.
    pairs = [(i, j) for i in range(4) for j in range(i + 1, 4)]
    expected_area = design.a_mm * design.b_mm * math.sin(math.radians(design.gamma_deg))
    for angle in np.linspace(0, design.packed_theta_deg, samples):
        current = mesh(design, float(angle))
        vertices = np.asarray(current["vertices"])
        for face in flat["faces"]:
            original, quad = reference[face], vertices[face]
            for i, j in pairs:
                before, after = np.linalg.norm(original[i] - original[j]), np.linalg.norm(quad[i] - quad[j])
                max_distance = max(max_distance, abs(after - before) / before)
            normal = np.cross(quad[1] - quad[0], quad[3] - quad[0])
            max_area = max(max_area, abs(np.linalg.norm(normal) - expected_area) / expected_area)
            max_planarity = max(max_planarity, abs(np.dot(quad[2] - quad[0], normal)) / np.linalg.norm(normal))
        measured = np.ptp(vertices, axis=0)
        predicted = dimensions(design, float(angle))
        max_extent = max(max_extent, float(np.max(np.abs(measured - list(predicted.values())))))
    return {"passed": bool(max_distance < 1e-9 and max_area < 1e-9 and max_planarity < 1e-8 and max_extent < 1e-8),
            "sample_count": samples, "max_distance_relative_error": float(max_distance),
            "max_facet_area_relative_error": float(max_area), "max_planarity_error_mm": float(max_planarity),
            "max_extent_error_mm": max_extent,
            "zero_thickness_nonintersection": "Analytical positive-Jacobian proof within the supported domain; docs/GEOMETRY.md",
            "physical_validation": "pending", "finite_thickness_clearance": "not modeled"}


def fold_assignments(design: Design):
    data = mesh(design, 10)
    vertices = np.asarray(data["vertices"])
    normals = []
    for face in data["faces"]:
        q = vertices[face]
        normal = np.cross(q[1] - q[0], q[3] - q[0])
        normals.append(normal / np.linalg.norm(normal))
    assignments = []
    for edge in data["edges"]:
        if edge["boundary"]:
            assignments.append("B")
            continue
        fi, fj = edge["faces"]
        face = data["faces"][fi]
        directed = next((a, b) for a, b in zip(face, face[1:] + face[:1]) if set((a, b)) == set(edge["vertices"]))
        tangent = vertices[directed[1]] - vertices[directed[0]]
        signed = np.dot(tangent, np.cross(normals[fi], normals[fj]))
        assignments.append("F" if abs(signed) < 1e-9 else ("M" if signed > 0 else "V"))
    return assignments


def export_fold(design: Design, folded=False):
    data = mesh(design, design.deployed_theta_deg if folded else 0)
    return {"file_spec": 1.2, "file_creator": "Design Continuum / Discover", "file_classes": ["singleModel"],
            "frame_title": "Ideal deployed panel" if folded else "Printable crease pattern",
            "frame_classes": ["foldedForm"] if folded else ["creasePattern"], "frame_unit": "mm",
            "vertices_coords": data["vertices"], "faces_vertices": data["faces"],
            "edges_vertices": [e["vertices"] for e in data["edges"]], "edges_assignment": fold_assignments(design),
            "continuum:design": design.model_dump(), "continuum:assumptions": ["zero thickness", "ideal rigid facets", "physical validation pending"]}


def export_svg(design: Design):
    data, assignments = mesh(design, 0), fold_assignments(design)
    dims = dimensions(design, 0)
    width, height = dims["x_mm"] + 20, dims["y_mm"] + 20
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.6f}mm" height="{height:.6f}mm" viewBox="0 0 {width:.6f} {height:.6f}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<g transform="translate(10 10)" fill="none" stroke-width="0.25">']
    for edge, assignment in zip(data["edges"], assignments):
        p, q = [data["vertices"][i] for i in edge["vertices"]]
        color = {"B": "#282923", "M": "#aa4c35", "V": "#326b86", "F": "#aaa"}[assignment]
        dash = ' stroke-dasharray="2 1"' if assignment == "V" else (' stroke-dasharray="4 1 1 1"' if assignment == "M" else "")
        lines.append(f'<line x1="{p[0]:.6f}" y1="{p[1]:.6f}" x2="{q[0]:.6f}" y2="{q[1]:.6f}" stroke="{color}"{dash}/>')
    y = dims["y_mm"] + 3
    lines += [f'<path d="M0 {y}h50m0 -2v4m-50 -4v4" stroke="#222"/>', '</g>',
              f'<text x="10" y="{height-1:.6f}" font-family="sans-serif" font-size="2.1">50 mm scale · Print 100% · red M / blue V from printed side · physical validation pending</text>', '</svg>']
    return "\n".join(lines)
