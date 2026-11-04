"""Recheck retained mechanical targets with native tools and no model request."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from .design_tools import DesignSession, review_identity
from .floor_check import footprint_spec


def study_identity(document, asset_loader=None):
    metadata = document.get("metadata", {})
    spec = metadata.get("design_mechanism")
    reports = metadata.get("design_review", {}).get("reports", {})
    declared_targets = metadata.get("native_study_targets")
    if declared_targets is not None and (
        not isinstance(declared_targets, dict)
        or not isinstance(declared_targets.get("states"), dict)
    ):
        raise ValueError("Explicit native study targets require a states mapping")
    if not isinstance(spec, dict) or not spec.get("states"):
        raise ValueError("A retained named mechanism study is required")
    targets = {}
    for state in spec["states"]:
        name = state["name"]
        if declared_targets is not None:
            footprint = declared_targets["states"].get(name)
        else:
            row = reports.get("floor:state:" + name)
            footprint = row.get("footprint") if isinstance(row, dict) else None
        if not isinstance(footprint, dict):
            raise ValueError("Missing retained floor target for state: " + name)
        targets[name] = footprint_spec(footprint)
    encoded = json.dumps(
        [review_identity(document, asset_loader), targets],
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest(), targets


def native_review_state(document, asset_loader=None):
    review = document.get("metadata", {}).get("native_study_review")
    if not isinstance(review, dict):
        return {"status": "unbound"}
    try:
        current = (
            review.get("source_identity") == study_identity(document, asset_loader)[0]
        )
    except (ValueError, KeyError, OSError, TypeError):
        current = False
    return {
        "status": "current" if current else "stale",
        "passed": bool(review.get("passed")) if current else None,
        "model_calls": 0,
        "physical_validation": False,
        "detail": (
            "Native numeric/export recheck of retained targets; model visual assessment and physical qualification remain separate."
            if current
            else "Source, targets, assets or checker code changed; rerun native checks."
        ),
    }


def recheck(document, folder, asset_loader=None, geometry_lock=None):
    identity, targets = study_identity(document, asset_loader)
    spec = document["metadata"]["design_mechanism"]
    session = DesignSession(
        document,
        "Native recheck of retained targets; no model calls or model selection",
        folder,
        asset_loader,
        geometry_lock,
    )
    results = {}
    results["interference"] = session.call(
        "check_interference", {"candidate_id": "base"}
    )
    if document.get("metadata", {}).get("assembly_plan"):
        results["assembly"] = session.call(
            "check_assembly",
            {"candidate_id": "base", "spec": document["metadata"]["assembly_plan"]},
        )
    for name, footprint in targets.items():
        results["floor:state:" + name] = session.call(
            "check_floor",
            {
                "candidate_id": "base",
                "mechanism_spec": spec,
                "state_name": name,
                "footprint": footprint,
            },
        )
    results["motion"] = session.call(
        "check_motion", {"candidate_id": "base", "spec": spec}
    )
    if (
        document.get("metadata", {}).get("native_study_targets", {}).get("retention")
        is not None
    ):
        results["retention"] = session.call(
            "check_retention", {"candidate_id": "base", "spec": {}}
        )
    if (
        document.get("metadata", {})
        .get("native_study_targets", {})
        .get("prismatic_controls")
        is not None
    ):
        results["prismatic_controls"] = session.call(
            "check_prismatic_controls", {"candidate_id": "base", "spec": {}}
        )
    results["exports"] = session.call("verify_exports", {"candidate_id": "base"})
    if (
        document.get("metadata", {})
        .get("native_study_targets", {})
        .get("handling_paths")
        is not None
    ):
        results["handling"] = session.call(
            "check_handling", {"candidate_id": "base", "spec": {}}
        )
    passed = all(r.get("ok") and r.get("passed") for r in results.values())
    reports = deepcopy(session.reports.get("base", {}))
    if "motion" in reports:
        reports["motion"] = {
            k: v
            for k, v in reports["motion"].items()
            if k not in ("frames", "parts", "graph")
        }
    review = {
        "source_identity": identity,
        "passed": passed,
        "actor": "native_tools",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_calls": 0,
        "physical_validation": False,
        "locking_verified": False,
        "visual_review_performed": False,
        "reports": reports,
        "failures": {
            name: r.get("error", "Native check failed")
            for name, r in results.items()
            if not r.get("ok") or not r.get("passed")
        },
        "scope": "Rechecks existing explicit floor targets, declared finite-solid sampled motion, retained assembly plan if present, source interference and strict assembled/component exports. Does not infer new requirements, change targets or geometry, refresh model visual judgement, or qualify manufactured retention, locks, loads or print fit.",
    }
    # Reject any accidental source/target drift during the operation.
    if identity != study_identity(document, asset_loader)[0]:
        raise ValueError("Source or imported assets changed during native recheck")
    result = deepcopy(document)
    result.setdefault("metadata", {})["native_study_review"] = review
    return result, review
