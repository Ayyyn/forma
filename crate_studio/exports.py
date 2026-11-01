"""Inspectable neutral CAD, panel profiles, drawings and a reproducible source bundle."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
import zipfile

import cadquery as cq
import ezdxf
import trimesh

from .cad import normalize_spec, build_parts, compound, verify_geometry


def cut_list(spec, parts):
    t = spec["thickness_mm"]
    rows = []
    for p in parts:
        x, y, z = p["size_mm"]
        a, b = (
            (x, y)
            if p["id"] in ("base", "lid")
            else ((x, z) if p["id"] in ("front", "back") else (y, z))
        )
        rows.append(
            dict(
                part=p["id"],
                quantity=1,
                width_mm=a,
                height_mm=b,
                thickness_mm=t,
                material=spec["material"],
            )
        )
    return rows


def _views(spec):
    w, d, h, t = (
        spec[k]
        for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm", "thickness_mm")
    )
    oh = h + t * (1 + int(spec["lid"]))
    return [
        ("Front", w + 2 * t, oh),
        ("Side", d + 2 * t, oh),
        ("Top", w + 2 * t, d + 2 * t),
    ]


def _view_lines(spec, label, a, b):
    """Panel seams and cavity edges in orthographic coordinates, origin bottom left."""
    t = spec["thickness_mm"]
    h = spec["inner_height_mm"]
    if label == "Top":
        hidden = spec["lid"]
        return [
            (t, t, a - t, t, hidden),
            (a - t, t, a - t, b - t, hidden),
            (a - t, b - t, t, b - t, hidden),
            (t, b - t, t, t, hidden),
        ]
    lines = [(0, t, a, t, False)]
    if spec["lid"]:
        lines.append((0, t + h, a, t + h, False))
    lines.extend(
        [(t, t, t, t + h, label == "Front"), (a - t, t, a - t, t + h, label == "Front")]
    )
    return lines


def drawing_svg(spec):
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650">',
        '<rect width="1200" height="650" fill="white"/>',
        '<g font-family="Arial,sans-serif" fill="#152630">',
        f'<text x="35" y="40" font-size="25">{html.escape(spec["name"])}</text>',
        '<text x="35" y="70" font-size="14">Orthographic views · mm · schematic scale per view · dashed lines: hidden cavity edges</text>',
    ]
    for i, (label, a, b) in enumerate(_views(spec)):
        scale = min(260 / a, 330 / b)
        x, y, sw, sh = 55 + i * 395, 135, a * scale, b * scale
        out += [
            f'<text x="{x}" y="110" font-size="19">{label}</text>',
            f'<rect x="{x}" y="{y}" width="{sw}" height="{sh}" fill="#e9eef0" stroke="#203641" stroke-width="2"/>',
            f'<path d="M{x},{y+sh+15}v15 M{x},{y+sh+23}h{sw} M{x+sw},{y+sh+15}v15" fill="none" stroke="#203641"/>',
            f'<text x="{x+sw/2}" y="{y+sh+45}" text-anchor="middle" font-size="15">{a:g} mm</text>',
            f'<text x="{x+sw+8}" y="{y+sh/2}" font-size="14">{b:g} mm</text>',
        ]
        for x1, y1, x2, y2, hidden in _view_lines(spec, label, a, b):
            dash = ' stroke-dasharray="5 4"' if hidden else ""
            out.append(
                f'<line x1="{x+x1*scale}" y1="{y+sh-y1*scale}" x2="{x+x2*scale}" y2="{y+sh-y2*scale}" stroke="#47616f" stroke-width="1"{dash}/>'
            )
    out += [
        f'<text x="35" y="570" font-size="15">Internal clear: {spec["inner_width_mm"]:g} × {spec["inner_depth_mm"]:g} × {spec["inner_height_mm"]:g} mm; panel thickness: {spec["thickness_mm"]:g} mm</text>',
        f'<text x="35" y="595" font-size="14">Material label: {html.escape(spec["material"])}. Butt joints; no hardware, allowances or tolerances included.</text>',
        '<text x="35" y="620" font-size="14">GEOMETRY REVIEW ONLY — strength and manufacturing suitability unqualified. See panel DXFs and cut list.</text></g></svg>',
    ]
    return "\n".join(out)


def _pdf(spec, rows):
    # Small self-contained PDF writer: vector rectangles + selectable text, no raster dependency.
    def esc(s):
        return (
            str(s)
            .encode("latin1", "replace")
            .decode("latin1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    commands = []

    def text(x, y, s, size=11):
        commands.append(f"BT /F1 {size} Tf {x} {y} Td ({esc(s)}) Tj ET")

    text(35, 805, spec["name"], 20)
    text(35, 785, "Orthographic views (mm); schematic scale per view")
    text(
        35,
        770,
        "Dashed: hidden cavity edges. Solid interior lines: visible panel seams.",
        9,
    )
    for i, (label, a, b) in enumerate(_views(spec)):
        scale = min(145 / a, 180 / b)
        x = 40 + i * 190
        y = 550
        commands.append(f"{x} {y} {a*scale} {b*scale} re S")
        for x1, y1, x2, y2, hidden in _view_lines(spec, label, a, b):
            commands.append(
                ("[3 3] 0 d " if hidden else "[] 0 d ")
                + f"{x+x1*scale} {y+y1*scale} m {x+x2*scale} {y+y2*scale} l S"
            )
        commands.append("[] 0 d")
        text(x, 750, label, 14)
        text(x, y - 18, f"Width {a:g} mm")
        text(x, y - 34, f"Height {b:g} mm")
    text(35, 475, "Panel cut list - rectangular profiles, quantity 1 each", 14)
    for i, r in enumerate(rows):
        text(
            35,
            450 - i * 22,
            f'{r["part"]}: {r["width_mm"]:g} x {r["height_mm"]:g} x {r["thickness_mm"]:g} mm',
        )
    text(35, 265, f'Material label: {spec["material"]}')
    text(
        35,
        245,
        "Internal clear W/D/H: "
        + " / ".join(
            f"{spec[k]:g}"
            for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm")
        )
        + " mm",
    )
    text(
        35,
        220,
        "Butt joints. No fasteners, kerf, fabrication allowances or tolerances included.",
    )
    text(
        35,
        200,
        "GEOMETRY REVIEW ONLY: strength and manufacturing suitability unqualified.",
    )
    stream = "\n".join(commands).encode("latin1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(result))
        result.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        result.extend(f"{off:010d} 00000 n \n".encode())
    result.extend(
        f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    return bytes(result)


def export_bundle(spec, output_dir):
    spec = normalize_spec(spec)
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    parts = build_parts(spec)
    validation = verify_geometry(spec, parts)
    if not validation["passed"]:
        raise ValueError("Geometry verification failed")
    assembly = compound(parts)
    cq.exporters.export(assembly, str(dest / "assembly.step"))
    # A touching compound retains duplicate interface triangles. Export its geometric
    # union so the STL is a manifold boundary; STEP deliberately retains panel solids.
    fused = parts[0]["shape"].fuse(*[p["shape"] for p in parts[1:]]).clean()
    cq.exporters.export(fused, str(dest / "assembly.stl"))
    mesh = trimesh.load(str(dest / "assembly.stl"), force="mesh", process=True)
    w, d, h, t = (
        spec[k]
        for k in ("inner_width_mm", "inner_depth_mm", "inner_height_mm", "thickness_mm")
    )
    expected_bounds = [
        [-w / 2 - t, -d / 2 - t, 0],
        [w / 2 + t, d / 2 + t, h + t * (1 + int(spec["lid"]))],
    ]
    bounds_error = max(
        abs(float(mesh.bounds[i][j]) - expected_bounds[i][j])
        for i in range(2)
        for j in range(3)
    )
    stl_volume_tolerance = max(1e-5, validation["expected_volume_mm3"] * 2e-6)
    bounds_tolerance = max(1e-5, max(validation["expected_outer_mm"]) * 2e-7)
    validation["stl_roundtrip"] = {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "volume_mm3": float(mesh.volume),
        "bounds_mm": mesh.bounds.tolist(),
        "expected_bounds_mm": expected_bounds,
        "max_bounds_error_mm": bounds_error,
        "bounds_tolerance_mm": bounds_tolerance,
        "volume_tolerance_mm3": stl_volume_tolerance,
        "representation": "Fused geometric union of ideal touching panels; not assembled hardware or joint qualification.",
        "passed": bool(
            mesh.is_watertight
            and mesh.is_winding_consistent
            and mesh.is_volume
            and abs(float(mesh.volume) - validation["expected_volume_mm3"])
            <= stl_volume_tolerance
            and bounds_error <= bounds_tolerance
        ),
    }
    if not validation["stl_roundtrip"]["passed"]:
        raise ValueError("STL round-trip verification failed")
    imported = cq.importers.importStep(str(dest / "assembly.step"))
    imported_shapes = imported.solids().vals()
    volume = sum(x.Volume() for x in imported_shapes)
    validation["step_roundtrip"] = {
        "solid_count": len(imported_shapes),
        "volume_mm3": volume,
        "passed": len(imported_shapes) == len(parts)
        and abs(volume - validation["expected_volume_mm3"])
        <= validation["volume_tolerance_mm3"]
        and all(x.isValid() for x in imported_shapes),
    }
    if not validation["step_roundtrip"]["passed"]:
        raise ValueError("STEP round-trip verification failed")
    rows = cut_list(spec, parts)
    with (dest / "cut-list.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        doc = ezdxf.new("R2010")
        doc.units = 4
        a, b = row["width_mm"], row["height_mm"]
        doc.modelspace().add_lwpolyline([(0, 0), (a, 0), (a, b), (0, b)], close=True)
        doc.saveas(dest / f'panel-{row["part"]}.dxf')
    (dest / "drawing.svg").write_text(drawing_svg(spec), encoding="utf-8")
    (dest / "drawing.pdf").write_bytes(_pdf(spec, rows))
    (dest / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    (dest / "verification.json").write_text(
        json.dumps(validation, indent=2), encoding="utf-8"
    )
    source = Path(__file__).with_name("cad.py").read_text(encoding="utf-8")
    source += '\n\nif __name__ == "__main__":\n    import json\n    from pathlib import Path\n    s = json.loads(Path(__file__).with_name("spec.json").read_text())\n    cq.exporters.export(compound(build_parts(s)), "regenerated.step")\n'
    (dest / "parametric_model.py").write_text(source, encoding="utf-8")
    (dest / "README.txt").write_text(
        "Panel crate export\nAll dimensions are millimetres. Install cadquery==2.8 and run parametric_model.py with spec.json beside it to regenerate STEP.\nSTEP contains separate editable boundary-representation solids, not a native CAD feature tree. STL is the watertight tessellated geometric UNION of the panels, not separate assembled hardware; a closed lid encloses an internal void. STL has no intrinsic units: import as millimetres. Reimport checks are in verification.json. DXFs are closed 1:1 panel outlines; SVG/PDF are orthographic review drawings with visible seams and dashed hidden cavity edges, not production drawings.\nAll joints are ideal butt joints. No fasteners, bonding specification, kerf, tool clearance, fabrication tolerances, load or strength analysis are included. Material is a label, not engineering qualification.\n",
        encoding="utf-8",
    )
    files = sorted(
        [
            "assembly.step",
            "assembly.stl",
            "cut-list.csv",
            "drawing.svg",
            "drawing.pdf",
            "spec.json",
            "verification.json",
            "parametric_model.py",
            "README.txt",
        ]
        + [f'panel-{row["part"]}.dxf' for row in rows]
    )
    with zipfile.ZipFile(
        dest / "crate-bundle.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for name in files:
            archive.write(dest / name, name)
    return {
        "files": files + ["crate-bundle.zip"],
        "verification": validation,
        "cut_list": rows,
        "spec": spec,
    }
