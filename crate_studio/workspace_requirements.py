"""Bind enclosure checks to the exact supported panel feature definition."""

from .engine import evaluate


def enclosure_features(panels):
    features = []
    for panel in panels:
        x, y, z = panel["size_mm"]
        cx, cy, cz = panel["center_mm"]
        features.append(
            {
                "id": panel["id"],
                "type": "box",
                "name": panel["name"],
                "params": {
                    "width": x,
                    "depth": y,
                    "height": z,
                    "cx": cx,
                    "cy": cy,
                    "z": cz - z / 2,
                    "operation": "new_body",
                },
                "suppressed": False,
            }
        )
    return features


def requirement_state(document):
    metadata = document.get("metadata", {})
    if not metadata.get("source_crate_id"):
        return {
            "status": "unbound",
            "checks": [],
            "detail": "No enclosure requirements are attached to this project.",
        }
    try:
        if not isinstance(metadata.get("source_spec"), dict) or not isinstance(
            metadata.get("source_requirements"), dict
        ):
            raise ValueError("Missing source specification or requirements")
        source = evaluate(metadata["source_spec"], metadata["source_requirements"])

        def geometry(features):
            return [
                {
                    "id": f.get("id"),
                    "type": f.get("type"),
                    "params": f.get("params", {}),
                    "suppressed": bool(f.get("suppressed", False)),
                }
                for f in features
            ]

        unchanged = geometry(document["features"]) == geometry(
            enclosure_features(source["panels"])
        )
        if unchanged:
            return {
                "status": "current",
                "passed": source["passed"],
                "checks": source["checks"],
                "detail": "Enclosure checks recomputed for the matching panel definition. Material and load assumptions still apply.",
            }
        return {
            "status": "stale",
            "checks": [],
            "detail": "Panel geometry has changed. Capacity, mass and load checks require requalification in the enclosure workspace.",
        }
    except (ValueError, KeyError, TypeError) as error:
        return {
            "status": "stale",
            "checks": [],
            "detail": "Source requirements cannot be evaluated: " + str(error),
        }
