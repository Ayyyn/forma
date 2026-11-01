"""Seeded bounded design exploration, independent of model inference."""
import math
import random
from .geometry import Design, Requirements, evaluate


def baseline_design():
    return Design(family="accordion", columns=8, rows=1, a_mm=32, b_mm=160, gamma_deg=90)


def search(requirements: Requirements, count=384, seed=27, family="both", gamma_min=40., gamma_max=80.):
    if not 16 <= count <= 512:
        raise ValueError("Search budget must be between 16 and 512 candidates")
    if family not in ("both", "miura", "accordion") or not 25 <= gamma_min <= gamma_max <= 85:
        raise ValueError("Invalid family or sector-angle search bounds")
    rng = random.Random(seed)
    designs = [Design(), baseline_design()]
    if family != "both":
        designs = [d for d in designs if d.family == family and (d.family == "accordion" or gamma_min <= d.gamma_deg <= gamma_max)]
    for _ in range(count - len(designs)):
        kind = rng.choice(["miura", "accordion"]) if family == "both" else family
        gamma = 90 if kind == "accordion" else rng.uniform(gamma_min, gamma_max)
        columns = rng.randint(6, 16)
        rows = rng.randint(3, 10) if kind == "miura" else 1
        a = requirements.deployed_x_min_mm / columns * rng.uniform(.91, 1.08)
        b = requirements.deployed_y_min_mm / (rows * math.sin(math.radians(gamma))) * rng.uniform(.99, 1.10)
        if not (5 <= a <= 100 and 5 <= b <= 250):
            continue
        designs.append(Design(family=kind, columns=columns, rows=rows, a_mm=round(a, 3), b_mm=round(b, 3),
                              gamma_deg=round(gamma, 3), deployed_theta_deg=8, packed_theta_deg=round(rng.uniform(78, 87), 3)))
    candidates = [evaluate(d, requirements) for d in designs]
    candidates.sort(key=lambda c: (not c["feasible"], c["score"]))
    feasible = [c for c in candidates if c["feasible"]]
    objectives = lambda c: (c["metrics"]["material_area_mm2"], c["metrics"]["crease_segments"], c["metrics"]["packed_bounding_area_mm2"])
    frontier = []
    for candidate in feasible:
        values = objectives(candidate)
        dominated = any(all(x <= y for x, y in zip(objectives(other), values)) and any(x < y for x, y in zip(objectives(other), values)) for other in feasible)
        if not dominated:
            frontier.append(candidate["id"])
    return {"seed": seed, "evaluated_count": len(candidates), "requested_budget": count, "feasible_count": len(feasible),
            "pareto_ids": frontier, "candidates": candidates[:24], "baseline": evaluate(baseline_design(), requirements),
            "search_space": {"family": family, "gamma_min": gamma_min, "gamma_max": gamma_max},
            "claim": "Bounded seeded exploration; no global optimality or AI advantage established."}
