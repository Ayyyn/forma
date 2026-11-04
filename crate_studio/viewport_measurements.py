"""Read-only native measures for viewport annotations, never mesh estimates."""

from .workspace_geometry import _bounds


def body_measurements(parts):
    rows = []
    for part in parts:
        shape = part["shape"]
        lo, hi = _bounds(shape)
        circles = []
        for index, edge in enumerate(shape.Edges()):
            if edge.geomType() == "CIRCLE":
                circles.append(
                    {
                        "id": f"{part['id']}:edge_{index:04d}",
                        "radius_mm": float(edge.radius()),
                        "diameter_mm": 2 * float(edge.radius()),
                        "center_mm": list(edge.arcCenter().toTuple()),
                        "edge_point_mm": list(edge.startPoint().toTuple()),
                    }
                )
        rows.append(
            {
                "id": part["id"],
                "bounds_mm": [lo, hi],
                "size_mm": [hi[i] - lo[i] for i in range(3)],
                "volume_mm3": float(shape.Volume()),
                "surface_area_mm2": float(shape.Area()),
                "circles": circles,
            }
        )
    return rows
