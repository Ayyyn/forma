"""Reusable native gears and helical threads; no benchmark IDs or reference CAD.

Gear profiles: cq_gears (Apache-2.0). Threads: native CadQuery helical sweeps.
All dimensions mm. These geometric features do not certify a transmission.
"""

import math
import cadquery as cq

KINDS = {"spur_gear", "bevel_gear", "threaded_body", "socket_head_screw"}
AXES = {
    "+Z": None,
    "-Z": ((1, 0, 0), 180),
    "+X": ((0, 1, 0), 90),
    "-X": ((0, 1, 0), -90),
    "+Y": ((1, 0, 0), -90),
    "-Y": ((1, 0, 0), 90),
}


def n(p, key, default=None, positive=False):
    from .workspace_geometry import _number

    return _number(p, key, default, positive=positive)


def integer(p, key, default, low, high):
    value = p.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer in [{low}, {high}]")
    return value


def place(shape, p):
    axis = p.get("axis", "+Z")
    if axis not in AXES:
        raise ValueError("axis must be +X, -X, +Y, -Y, +Z or -Z")
    if AXES[axis]:
        shape = shape.rotate((0, 0, 0), AXES[axis][0], AXES[axis][1])
    return shape.translate((n(p, "cx", 0), n(p, "cy", 0), n(p, "z", 0)))


def bore(body, p, start, length):
    diameter = n(p, "bore_diameter", 0)
    if diameter < 0:
        raise ValueError("bore_diameter cannot be negative")
    if not diameter:
        return body
    radius = diameter / 2
    tool = cq.Solid.makeCylinder(radius, length, cq.Vector(0, 0, start))
    if p.get("bore_flat") is not None:
        flat = n(p, "bore_flat")
        if not -radius < flat < radius:
            raise ValueError("bore_flat must be inside the bore radius")
        limit = cq.Solid.makeBox(
            radius + flat, 2 * radius, length, cq.Vector(-radius, -radius, start)
        )
        tool = tool.intersect(limit)
    angle = n(p, "bore_angle", 0)
    if angle:
        tool = tool.rotate((0, 0, 0), (0, 0, 1), angle)
    result = body.cut(tool)
    if body.Volume() - result.Volume() < 1e-8:
        raise ValueError("Bore does not intersect this gear")
    return result


def gear(kind, p):
    from cq_gears import SpurGear, BevelGear

    module = n(p, "module", positive=True)
    teeth = integer(p, "teeth", 20, 6, 160)
    pressure = n(p, "pressure_angle", 20)
    if not 5 <= pressure <= 35:
        raise ValueError("pressure_angle must be between 5 and 35 degrees")
    backlash = n(p, "backlash", 0)
    clearance = n(p, "clearance", 0)
    if not 0 <= backlash < module or not 0 <= clearance < module:
        raise ValueError(
            "backlash and clearance must be nonnegative and smaller than module"
        )
    if kind == "spur_gear":
        width = n(p, "thickness", positive=True)
        profile = SpurGear(
            module,
            teeth,
            width,
            pressure_angle=pressure,
            clearance=clearance,
            backlash=backlash,
        )
    else:
        cone = n(p, "cone_angle", positive=True)
        if not 5 <= cone <= 85:
            raise ValueError("cone_angle must be between 5 and 85 degrees")
        width = n(p, "face_width", positive=True)
        profile = BevelGear(
            module,
            teeth,
            cone,
            width,
            pressure_angle=pressure,
            clearance=clearance,
            backlash=backlash,
        )
    body = profile.build()
    phase = n(p, "phase", 0)
    if phase:
        body = body.rotate((0, 0, 0), (0, 0, 1), phase)
    bounds = body.BoundingBox()
    body = bore(body, p, bounds.zmin - 1, bounds.zlen + 2)
    # Bevel placement is the shared pitch-cone apex, rather than a guessed body
    # centre. Two perpendicular gears can therefore share one exact apex.
    if kind == "bevel_gear":
        body = body.translate((0, 0, -profile.cone_h))
    return place(body, p)


def threaded_shaft(p):
    major = n(p, "major_diameter", positive=True)
    pitch = n(p, "pitch", positive=True)
    length = n(p, "length", positive=True)
    starts = integer(p, "starts", 1, 1, 8)
    profile = p.get("profile", "iso")
    if profile not in ("iso", "buttress"):
        raise ValueError("profile must be iso or buttress")
    root = n(p, "root_diameter", major - 1.226869 * pitch, positive=True)
    if not root < major:
        raise ValueError("root_diameter must be smaller than major_diameter")
    if length / (pitch * starts) > 60:
        raise ValueError("At most 60 helix turns per start are supported")
    hand = p.get("hand", "right")
    if hand not in ("left", "right"):
        raise ValueError("hand must be right or left")
    crest = n(p, "crest_width", pitch / 8, positive=True)
    base = n(p, "root_width", pitch * 0.75, positive=True)
    offset = n(p, "apex_offset", pitch * 0.2 if profile == "buttress" else 0)
    if not crest < base < pitch or abs(offset) + crest / 2 >= base / 2:
        raise ValueError("Thread profile widths/offset must fit one nominal pitch")
    lead = pitch * starts
    # Sweep a closed axial profile along a true helix. Extending the guide on
    # both ends and clipping afterwards avoids partial end-turn artefacts.
    # Embed the ridge root into the core; the visible root remains exact.
    radial_root = root / 2 - min(pitch * 0.05, root * 0.05)
    points = [
        (radial_root, -base / 2 - lead),
        (major / 2, offset - crest / 2 - lead),
        (major / 2, offset + crest / 2 - lead),
        (radial_root, base / 2 - lead),
    ]
    path = cq.Wire.makeHelix(
        lead, length + 2 * lead, root / 2, lefthand=hand == "left"
    ).translate((0, 0, -lead))
    turn = cq.Workplane("XZ").polyline(points).close().sweep(path, isFrenet=True).val()
    core = cq.Solid.makeCylinder(root / 2, length)
    extended_core = cq.Solid.makeCylinder(
        root / 2, length + 4 * lead, cq.Vector(0, 0, -2 * lead)
    )
    limit = cq.Solid.makeCylinder(major / 2 + 0.1, length)
    turns = [turn.rotate((0, 0, 0), (0, 0, 1), 360 * i / starts) for i in range(starts)]
    # Fuse before clipping: trimming a ridge first can leave coincident end
    # boundaries that OCCT classifies incorrectly, silently discarding crests.
    result = extended_core.fuse(*turns).intersect(limit)
    if not result.isValid() or len(result.Solids()) != 1:
        raise ValueError("Thread failed to form a valid joined shaft")
    expected_ridge_volume = (
        math.pi
        * (major + root)
        / 2
        * ((major - root) / 2)
        * (crest + base)
        / 2
        * length
        / pitch
    )
    if result.Volume() < core.Volume() + expected_ridge_volume * 0.5 or abs(
        core.cut(result).Volume()
    ) > max(1e-5, core.Volume() * 1e-7):
        raise ValueError("Thread union lost its core or helical crests")
    return result


def threaded_body(p):
    external = p.get("external", True)
    if type(external) is not bool:
        raise ValueError("external must be boolean")
    if external:
        body = threaded_shaft(p)
    else:
        outer = n(p, "outer_diameter", positive=True)
        major = n(p, "major_diameter", positive=True)
        length = n(p, "length", positive=True)
        gap = n(p, "radial_clearance", 0)
        if gap < 0 or gap > major * 0.1:
            raise ValueError(
                "radial_clearance must be between zero and 10% of major diameter"
            )
        if outer <= major + 2 * gap:
            raise ValueError("Nut outside diameter must exceed its thread diameter")
        tool_params = {**p, "major_diameter": major + 2 * gap}
        if "root_diameter" in p:
            tool_params["root_diameter"] = n(p, "root_diameter") + 2 * gap
        tool = threaded_shaft(tool_params)
        body = cq.Solid.makeCylinder(outer / 2, length).cut(tool)
    return place(body, p)


def socket_screw(p):
    length = n(p, "length", positive=True)
    head_height = n(p, "head_height", positive=True)
    head_diameter = n(p, "head_diameter", positive=True)
    socket = n(p, "socket_af", positive=True)
    depth = n(p, "socket_depth", positive=True)
    if socket >= head_diameter or depth >= head_height:
        raise ValueError("Socket must fit inside the screw head")
    shaft = threaded_shaft({**p, "profile": "iso"}).translate(
        (0, 0, -head_height - length)
    )
    head = cq.Solid.makeCylinder(
        head_diameter / 2, head_height, cq.Vector(0, 0, -head_height)
    )
    body = shaft.fuse(head)
    radius = socket / math.sqrt(3)
    points = [
        (radius * math.cos(i * math.tau / 6), radius * math.sin(i * math.tau / 6))
        for i in range(6)
    ]
    tool = (
        cq.Workplane("XY")
        .polyline(points)
        .close()
        .extrude(depth + 0.1)
        .translate((0, 0, -depth))
        .val()
    )
    return place(body.cut(tool), p)


def apply_mechanical(kind, p, shapes):
    from .workspace_geometry import _solids, _union, _subtract

    tool = (
        gear(kind, p)
        if kind in ("spur_gear", "bevel_gear")
        else threaded_body(p) if kind == "threaded_body" else socket_screw(p)
    )
    operation = p.get("operation", "new_body")
    if operation == "new_body":
        return shapes + _solids(tool)
    if operation == "add":
        return _solids(_union(shapes + [tool]))
    if operation == "cut":
        return _subtract(_union(shapes), tool)
    raise ValueError("operation must be add, cut or new_body")
