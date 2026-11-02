"""Bounded integer design for two/three-shaft external spur trains.

Uses only supplied shaft locations, speed targets and design limits. Generated
gears remain ordinary editable features. No task IDs, fixtures or scoring data.
"""

import math

from .mechanical_features import n, integer

TRAIN_PARAMS = {
    "prefix",
    "centers",
    "input_rpm",
    "output_rpm",
    "thickness",
    "z",
    "bore_diameter",
    "bore_flat",
    "pressure_angle",
    "backlash",
    "outline_tolerance",
    "module",
    "max_teeth",
    "addendum_coeff",
    "dedendum_coeff",
    "tangential_backlash",
    "module_policy",
    "profile_preset",
    "complexity_limit_teeth",
}


def design_spur_train(spec):
    import re

    if not isinstance(spec, dict) or set(spec) - TRAIN_PARAMS:
        raise ValueError("Unsupported spur train specification")
    preset = spec.get("profile_preset", "full_depth")
    if preset not in ("full_depth", "compact", "adaptive"):
        raise ValueError("Unknown gear profile preset")
    spec = dict(spec)
    if preset == "adaptive":
        limit = integer(spec, "complexity_limit_teeth", 64, 24, 480)
        full = {**spec, "profile_preset": "full_depth"}
        for key, value in {
            "pressure_angle": 25,
            "tangential_backlash": 0.2,
            "outline_tolerance": 0.025,
            "module_policy": "custom",
        }.items():
            full.setdefault(key, value)
        try:
            features, proof = design_spur_train(full)
        except ValueError as exc:
            if "No integer tooth solution" not in str(exc):
                raise
            features, proof = design_spur_train({**spec, "profile_preset": "compact"})
            proof["profile_selection"] = (
                "Compact profile permits an integer solution under explicit limits"
            )
            return features, proof
        if sum(proof["teeth"]) <= limit:
            proof["profile_selection"] = (
                "Full-depth profile within the explicit complexity budget"
            )
            return features, proof
        compact, alternative = design_spur_train({**spec, "profile_preset": "compact"})
        if sum(alternative["teeth"]) < sum(proof["teeth"]):
            alternative["profile_selection"] = (
                "Stub profile reduces tooth complexity while preserving explicit constraints and ratio"
            )
            return compact, alternative
        proof["profile_selection"] = (
            "Explicit constraints retained; alternate profile gives no complexity reduction"
        )
        return features, proof
    if preset == "compact":
        for key, value in {
            "pressure_angle": 25,
            "addendum_coeff": 0.8,
            "dedendum_coeff": 1,
            "tangential_backlash": 0.2,
            "outline_tolerance": 0.025,
            "module_policy": "custom",
        }.items():
            spec.setdefault(key, value)
    prefix = spec.get("prefix", "train")
    if not isinstance(prefix, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_]{0,39}", prefix
    ):
        raise ValueError("Train prefix must be a short identifier")
    centers = spec.get("centers")
    if not isinstance(centers, list) or len(centers) not in (2, 3):
        raise ValueError("Supply two or three ordered XY shaft centers")
    for point in centers:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Shaft centers must contain two coordinates")
        for value in point:
            n({"v": value}, "v")
    distances = [math.dist(a, b) for a, b in zip(centers, centers[1:])]
    if min(distances) < 1:
        raise ValueError("Shaft centers must be at least 1 mm apart")
    input_rpm, output_rpm = n(spec, "input_rpm"), n(spec, "output_rpm")
    if input_rpm == 0 or output_rpm == 0:
        raise ValueError("Both target speeds must be nonzero")
    ratio = output_rpm / input_rpm
    expected_sign = (-1) ** (len(centers) - 1)
    if ratio * expected_sign <= 0:
        raise ValueError(
            "Requested direction is incompatible with this external gear train"
        )
    maximum = integer(spec, "max_teeth", 100, 18, 160)
    fixed_module = n(spec, "module", positive=True) if "module" in spec else None
    pressure = n(spec, "pressure_angle", 20)
    addendum = n(spec, "addendum_coeff", 1, positive=True)
    if not 5 <= pressure <= 35 or not 0.5 <= addendum <= 1.5:
        raise ValueError("Unsupported pressure angle or addendum")
    minimum = max(6, math.ceil(2 * addendum / math.sin(math.radians(pressure)) ** 2))
    policy = spec.get("module_policy", "standard")
    if policy not in ("standard", "custom"):
        raise ValueError("module_policy must be standard or custom")
    candidates = []
    for first in range(minimum, maximum + 1):
        for second in range(minimum, maximum + 1):
            module = 2 * distances[0] / (first + second)
            if not 0.25 <= module <= 10 or (
                fixed_module is not None and abs(module - fixed_module) > 1e-6
            ):
                continue
            teeth = [first, second]
            if len(centers) == 3:
                last = 2 * distances[1] / module - second
                if (
                    abs(last - round(last)) > 1e-6
                    or not minimum <= round(last) <= maximum
                ):
                    continue
                teeth.append(round(last))
            achieved = expected_sign * first / teeth[-1]
            error = abs(achieved / ratio - 1)
            if error <= 0.05:
                preferred = any(
                    abs(module - stock) < 1e-6
                    for stock in (0.5, 0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5)
                )
                order = (
                    (0 if preferred else 1, sum(teeth), error)
                    if policy == "standard"
                    else (0, error, sum(teeth))
                )
                candidates.append((*order, module, teeth, achieved))
    if not candidates:
        raise ValueError(
            "No integer tooth solution within 5% of requested ratio and the stated limits"
        )
    chosen = min(candidates)
    module, teeth, achieved = chosen[-3:]
    error = abs(achieved / ratio - 1)
    thickness = n(spec, "thickness", positive=True)
    common = {
        "module": module,
        "thickness": thickness,
        "z": n(spec, "z", 0),
        "axis": "+Z",
        "operation": "new_body",
        "bore_diameter": n(spec, "bore_diameter", 0),
        "pressure_angle": n(spec, "pressure_angle", 20),
        "backlash": n(spec, "backlash", 0.05),
        "outline_tolerance": n(spec, "outline_tolerance", 0),
        "addendum_coeff": addendum,
        "dedendum_coeff": n(spec, "dedendum_coeff", 1.25, positive=True),
        "tangential_backlash": n(spec, "tangential_backlash", 0),
    }
    if "bore_flat" in spec:
        common["bore_flat"] = n(spec, "bore_flat")
    phases = [0.0]
    for i in range(1, len(teeth)):
        gamma = math.degrees(
            math.atan2(
                centers[i][1] - centers[i - 1][1], centers[i][0] - centers[i - 1][0]
            )
        )
        phase = (
            teeth[i - 1] * (gamma - phases[-1]) + teeth[i] * (gamma + 180) - 180
        ) / teeth[i]
        phases.append(phase % (360 / teeth[i]))
    features = [
        {
            "id": f"{prefix}_{i+1}",
            "type": "spur_gear",
            "name": f"Gear {i+1} · {count} teeth",
            "params": {
                **common,
                "teeth": count,
                "cx": point[0],
                "cy": point[1],
                "phase": phase,
            },
            "suppressed": False,
        }
        for i, (count, point, phase) in enumerate(zip(teeth, centers, phases))
    ]
    return features, {
        "input_rpm": input_rpm,
        "target_output_rpm": output_rpm,
        "kinematic_output_rpm": input_rpm * achieved,
        "relative_error": error,
        "module_mm": module,
        "teeth": teeth,
        "selection_policy": (
            "Standard modules then complexity"
            if policy == "standard"
            else "Closest ratio then fewest teeth; custom module allowed"
        ),
        "module_policy": policy,
        "scope": "Ideal external-gear kinematics; verify interference and physical transmission separately",
    }
