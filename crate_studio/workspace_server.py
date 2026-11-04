"""Persistent, human-editable feature documents. Only declarative CAD operations."""

from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
from functools import lru_cache
from importlib.metadata import version as package_version
from .workspace_requirements import enclosure_features, requirement_state
from .workspace_workflow import (
    revise_enclosure,
    motion_study,
    validate_motion,
    geometry_signature,
    export_panel_pack,
)
import base64
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
import threading
import uuid
from typing import Literal
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
import ezdxf

from .workspace_geometry import (
    export_document,
    _bounds as exact_bounds_mm,
    MAX_FEATURES,
)
from .workspace_drawing import (
    drawing_svg,
    export_drawings,
    validate_annotations,
    FONT_PATH,
)
from .workspace_cache import (
    cached_build,
    cache_clear,
    cache_info,
    asset_identity,
    VERSION as GEOMETRY_VERSION,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output/forma/studio"
# Bind disk artifacts to the code loaded by this process. Reading source hashes
# per request could label an old imported function with newly edited source.
EXPORT_VERSION = hashlib.sha256(
    GEOMETRY_VERSION.encode()
    + FONT_PATH.read_bytes()
    + FONT_PATH.with_name("FormaSans-LICENSE.txt").read_bytes()
    + json.dumps(
        {
            name: package_version(name)
            for name in (
                "cadquery",
                "cadquery-ocp",
                "trimesh",
                "ezdxf",
                "reportlab",
                "numpy",
                "shapely",
                "cq-gears",
                "cq-warehouse",
            )
        },
        sort_keys=True,
    ).encode()
    + b"".join(
        Path(__file__).with_name(name).read_bytes()
        for name in (
            "workspace_geometry.py",
            "workspace_drawing.py",
            "drawing_layout.py",
            "drawing_sections.py",
            "workspace_server.py",
            "component_exports.py",
            "assembly_study.py",
            "retention_study.py",
            "prismatic_controls.py",
            "handling_study.py",
            "design_tools.py",
            "mechanism_study.py",
            "motion_cache.py",
            "motion_probe.py",
            "native_study.py",
            "floor_check.py",
            "workspace_requirements.py",
            "workspace_workflow.py",
            "folding_study.py",
            "folding_print.py",
            "mechanical_print.py",
        )
    )
).hexdigest()[:12]
DOCS = DATA / "documents"
ASSETS = DATA / "assets"
STORE_LOCK = threading.RLock()
JOBS_LOCK = threading.RLock()
JOBS = {}
CAPABILITIES = {
    "feature_types": [
        "box",
        "cylinder",
        "sketch_extrude",
        "cut_hole",
        "fillet",
        "chamfer",
        "transform",
        "linear_pattern",
        "mirror",
        "union",
        "boolean_cut",
        "mate",
        "face_offset",
        "import_step",
        "spur_gear",
        "bevel_gear",
        "threaded_body",
        "socket_head_screw",
        "folding_assembly",
    ],
    "imports": ["step", "stp", "stl", "obj", "dxf", "json"],
    "exports": [
        "step",
        "stl",
        "components",
        "json",
        "svg",
        "pdf",
        "dxf",
        "csv",
        "bundle",
        "print",
    ],
    "limits": {"features": MAX_FEATURES, "bodies": 50, "upload_bytes": 15_000_000},
    "scope": "Declarative BREP features, dimension-driven profiles and sequential planar alignment. No native SolidWorks/AutoCAD feature history, general sketch constraint solver, simultaneous mate solver or manufacturing qualification.",
}

DEFAULT_DOCUMENT = {
    "name": "Mounting plate",
    "features": [
        {
            "id": "plate",
            "type": "box",
            "name": "Base plate",
            "params": {"width": 120, "depth": 80, "height": 10},
            "suppressed": False,
        },
        {
            "id": "corners",
            "type": "fillet",
            "name": "Corner fillets",
            "params": {"radius": 4, "selector": "vertical"},
            "suppressed": False,
        },
        {
            "id": "left-hole",
            "type": "cut_hole",
            "name": "Left mounting hole",
            "params": {"radius": 8, "depth": 14, "x": -35, "y": 0, "z": -2},
            "suppressed": False,
        },
        {
            "id": "right-hole",
            "type": "cut_hole",
            "name": "Right mounting hole",
            "params": {"radius": 8, "depth": 14, "x": 35, "y": 0, "z": -2},
            "suppressed": False,
        },
    ],
    "annotations": [],
    "display": {"color": "#9baec3", "hidden_parts": [], "colors": {}, "body_names": {}},
    "metadata": {},
}


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise HTTPException(404, "Unknown document")
    return value


def asset_path(asset_id):
    if not isinstance(asset_id, str) or not re.fullmatch(r"[a-f0-9]{64}", asset_id):
        raise ValueError("Invalid STEP asset identifier")
    path = ASSETS / (asset_id + ".step")
    if not path.is_file():
        raise ValueError(
            "A referenced STEP asset is missing; import a portable project or reimport its STEP file"
        )
    return path


def normalize_document(value):
    if not isinstance(value, dict) or set(value) - {
        "name",
        "features",
        "annotations",
        "display",
        "metadata",
        "configurations",
    }:
        raise ValueError("Unsupported document fields")
    doc = deepcopy(value)
    name = doc.get("name", "Untitled part")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValueError("Document name must contain 1–100 characters")
    doc["name"] = name.strip()
    if not isinstance(doc.get("features"), list) or len(doc["features"]) > MAX_FEATURES:
        raise ValueError(f"A document supports up to {MAX_FEATURES} features")
    doc.setdefault("annotations", [])
    validate_annotations(doc)
    doc.setdefault("display", {})
    doc.setdefault("metadata", {})
    if not isinstance(doc["display"], dict) or not isinstance(doc["metadata"], dict):
        raise ValueError("Document display and metadata must be objects")
    doc["metadata"].setdefault(
        "drawing_layout", "legacy-v1" if doc["annotations"] else "aligned-v1"
    )
    if doc["metadata"]["drawing_layout"] not in ("legacy-v1", "aligned-v1"):
        raise ValueError("Unknown drawing layout")
    if "drawing_sections" in doc["metadata"]:
        from .drawing_sections import specifications

        doc["metadata"]["drawing_sections"] = specifications(
            doc["metadata"]["drawing_sections"]
        )
    from .folding import specification as fold_specification

    for feature in doc["features"]:
        if isinstance(feature, dict) and feature.get("type") == "folding_assembly":
            feature["params"] = fold_specification(feature.get("params", {}))
    if "print_settings" in doc["metadata"]:
        from .folding_print import print_settings

        doc["metadata"]["print_settings"] = print_settings(
            doc["metadata"]["print_settings"]
        )
    if "motion" in doc["metadata"]:
        doc["metadata"]["motion"] = validate_motion(doc["metadata"]["motion"])
    if (
        not isinstance(doc["metadata"].get("brief", ""), str)
        or len(doc["metadata"].get("brief", "")) > 6000
    ):
        raise ValueError("Project brief must contain at most 6000 characters")
    for key in ["color"]:
        if key in doc["display"] and not re.fullmatch(
            r"#[0-9a-fA-F]{6}", str(doc["display"][key])
        ):
            raise ValueError("Body colors must use #RRGGBB")
    colors = doc["display"].get("colors", {})
    if not isinstance(colors, dict) or any(
        not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)) for v in colors.values()
    ):
        raise ValueError("Body colors must use #RRGGBB")
    if not isinstance(doc["display"].get("hidden_parts", []), list):
        raise ValueError("Hidden bodies must be an array of body identifiers")
    if len(json.dumps(doc, allow_nan=False).encode()) > 1_000_000:
        raise ValueError("Document definition exceeds 1 MB")
    # Configuration definitions are snapshots of feature data, never programs.
    configurations = doc.get("configurations", {})
    if not isinstance(configurations, dict) or len(configurations) > 20:
        raise ValueError("At most 20 named configurations are supported")
    for key, config in configurations.items():
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 80
            or not isinstance(config, list)
        ):
            raise ValueError("Configurations map names to feature arrays")
        if len(config) > 60:
            raise ValueError("Configuration feature limit exceeded")
        for feature in config:
            if isinstance(feature, dict) and feature.get("type") == "folding_assembly":
                feature["params"] = fold_specification(feature.get("params", {}))
    return doc


def export_key(doc):
    """Bind cached files to source, actual imported bytes and loaded exporters."""
    source = json.dumps(
        [doc, asset_identity(doc, asset_path)], sort_keys=True, allow_nan=False
    )
    return EXPORT_VERSION + "-" + hashlib.sha256(source.encode()).hexdigest()[:16]


def build_key(doc):
    normalized = normalize_document(doc)
    return json.dumps(
        {"features": normalized["features"]}, sort_keys=True, allow_nan=False
    )


def drawing_key(doc, context=None):
    return json.dumps(
        {
            "features": doc["features"],
            "name": doc["name"],
            "annotations": doc["annotations"],
            "metadata": {
                "component_instances": doc.get("metadata", {}).get(
                    "component_instances", {}
                ),
                "drawing_layout": doc.get("metadata", {}).get(
                    "drawing_layout",
                    "legacy-v1" if doc.get("annotations") else "aligned-v1",
                ),
                "drawing_sections": doc.get("metadata", {}).get("drawing_sections", []),
            },
            "_drawing_context": context or {},
            "assets": asset_identity(doc, asset_path),
        },
        sort_keys=True,
        allow_nan=False,
    )


def built(encoded):
    return cached_build(json.loads(encoded), asset_path)


built.cache_clear = cache_clear
built.cache_info = cache_info


@lru_cache(maxsize=20)
def projected(encoded):
    doc = json.loads(encoded)
    # Asset content belongs to the cache identity, not the editable document
    # schema passed to native regeneration.
    doc.pop("assets", None)
    context = doc.pop("_drawing_context", {})
    native = built(build_key(doc))
    return drawing_svg(doc, native["parts"], context=context, native_build=native)


def snapshot(document, cad_lock, drawing_context=None, include_drawing=True):
    doc = normalize_document(document)
    from .workspace_cache import lookup_build

    existing = (
        lookup_build(json.loads(build_key(doc)), asset_path)
        if not include_drawing
        else None
    )
    # Cached geometry is immutable. A new label/section revision can copy its
    # already-checked mesh/metrics without waiting behind an unrelated sweep.
    # Cold builds and every native projection still acquire the CAD lock.
    with cad_lock if existing is None else nullcontext():
        result = existing if existing is not None else built(build_key(doc))
        statuses = result["features"]
        empty = not doc["features"] or all(
            f.get("suppressed", False) for f in doc["features"]
        )
        valid = bool(result["checks"]["passed"])
        drawing_error = None
        try:
            sheet = (
                projected(drawing_key(doc, drawing_context))
                if valid and include_drawing
                else None
                if not include_drawing
                else '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800"><rect width="1200" height="800" fill="white"/><text x="50" y="65" font-family="Arial" font-size="25">'
                + html.escape(doc["name"])
                + '</text><text x="50" y="110" font-family="Arial" font-size="16">Add valid solid geometry to generate model views.</text></svg>'
            )
        except Exception as error:
            drawing_error = str(error)[:200]
            sheet = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800"><text x="50" y="80" font-family="Arial" font-size="20">Drawing projection unavailable for this geometry.</text></svg>'
    meshes = deepcopy(result["mesh"])
    names = doc["display"].get("body_names", {})
    for part in meshes:
        part["name"] = str(names.get(part["id"], part["name"]))[:100]
    checks = [
        {
            "id": "brep",
            "label": "Valid solid geometry",
            "status": "pass" if valid else ("info" if empty else "fail"),
            "detail": result["checks"].get("error")
            or "OpenCascade BREP validity and positive solid volume.",
        },
        {
            "id": "regeneration",
            "label": "Feature regeneration",
            "status": (
                "fail"
                if any(x["status"] in ["error", "blocked"] for x in statuses)
                else "pass"
            ),
            "detail": "Each active feature is replayed in order. Failed features block downstream operations.",
        },
        {
            "id": "topology",
            "label": "Topology references",
            "status": "info",
            "detail": result["checks"]["topology_ids"],
        },
        {
            "id": "qualification",
            "label": "Engineering scope",
            "status": "info",
            "detail": CAPABILITIES["scope"],
        },
    ]
    requirements = requirement_state(doc)
    development = doc.get("metadata", {}).get("assembly_development", {})
    remaining = (
        development.get("remaining", []) if isinstance(development, dict) else []
    )
    if isinstance(remaining, list) and remaining:
        checks.append(
            {
                "id": "practical_release",
                "label": "Prototype requirements unfinished",
                "status": "fail",
                "detail": "; ".join(str(value)[:220] for value in remaining[:6]),
            }
        )
    from .native_study import native_review_state

    native_review = native_review_state(doc, asset_path)
    if native_review["status"] != "unbound":
        checks.append(
            {
                "id": "native_study",
                "label": "Native study · " + native_review["status"],
                "status": (
                    ("pass" if native_review["passed"] else "fail")
                    if native_review["status"] == "current"
                    else "stale"
                ),
                "detail": native_review["detail"],
            }
        )
    design_review = {"status": "unbound"}
    if doc.get("metadata", {}).get("design_review"):
        from .design_tools import review_state

        design_review = review_state(doc, asset_path)
        checks.append(
            {
                "id": "design_review",
                "label": "Design tool review · " + design_review["status"],
                "status": "info" if design_review["status"] == "current" else "stale",
                "detail": design_review["detail"],
            }
        )
    if "folding" in result["checks"]:
        folded = result["checks"]["folding"]
        checks.append(
            {
                "id": "folding_pose",
                "label": "Hinge alignment and solid clearance · current pose",
                "status": "pass" if folded["passed"] else "fail",
                "detail": f"Axis closure {folded['axis_closure_error_mm']:.3g} mm; native solid interference checked. Run Motion to verify a trajectory.",
            }
        )
    if requirements["status"] != "unbound":
        checks.append(
            {
                "id": "crate_scope",
                "label": "Enclosure requirements · " + requirements["status"],
                "status": (
                    "stale"
                    if requirements["status"] == "stale"
                    else ("pass" if requirements["passed"] else "fail")
                ),
                "detail": requirements["detail"],
            }
        )
        checks.extend(
            {**check, "id": "requirement_" + check["id"]}
            for check in requirements["checks"]
        )
    if drawing_error:
        checks.append(
            {
                "id": "drawing_projection",
                "label": "Drawing projection",
                "status": "info",
                "detail": drawing_error,
            }
        )
    folding_info = None
    if "folding" in result["checks"]:
        from .folding import describe, flat_assembly, DEFAULT_LIMITS, ABSOLUTE_LIMITS

        feature = next(
            f
            for f in doc["features"]
            if f["type"] == "folding_assembly" and not f.get("suppressed")
        )
        folding_info = describe(feature["params"])
        folding_info["graph"] = flat_assembly(feature["params"])["graph"]
        folding_info["default_limit_deg"] = DEFAULT_LIMITS[folding_info["family"]]
        folding_info["absolute_limit_deg"] = ABSOLUTE_LIMITS[folding_info["family"]]
    return {
        "document": doc,
        "folding": folding_info,
        "requirements_state": requirements,
        "design_review_state": design_review,
        "native_study_state": native_review,
        "geometry_signature": geometry_signature(doc),
        "geometry_version": GEOMETRY_VERSION,
        "asset_identity": asset_identity(doc, asset_path),
        "geometry": {
            "parts": meshes,
            "face_meshes": result["face_meshes"],
            "edge_meta": result["edge_meta"],
        },
        "body_measurements": deepcopy(result["body_measurements"]),
        "metrics": result["metrics"],
        "checks": checks,
        "feature_results": statuses,
        "passed": valid,
        "document_valid": valid or empty,
        "drawing_svg": sheet,
        "drawing_pending": bool(valid and not include_drawing),
    }


def list_documents():
    rows = []
    if DOCS.exists():
        for path in DOCS.glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            rows.append(
                {
                    k: record[k]
                    for k in ["id", "parent_id", "label", "created_at", "name"]
                }
            )
    return sorted(rows, key=lambda x: x["created_at"], reverse=True)


@lru_cache(maxsize=4)
def _revision_snapshot(encoded, cad_lock):
    # lru_cache does not hold its map lock while running the function. A warm
    # immutable revision therefore avoids the CAD lock even during an agent
    # sweep; concurrent misses still serialize inside snapshot's native lock.
    document, revision_id, _assets, include_drawing = json.loads(encoded)
    return snapshot(document, cad_lock, {"revision_id": revision_id}, include_drawing)


def revision_snapshot(document, revision_id, cad_lock, include_drawing=True):
    encoded = json.dumps(
        [document, revision_id, asset_identity(document, asset_path), include_drawing],
        sort_keys=True,
        allow_nan=False,
    )
    return deepcopy(_revision_snapshot(encoded, cad_lock))


def read_document(id, cad_lock, include_drawing=True):
    path = DOCS / (valid_id(id) + ".json")
    if not path.is_file():
        raise HTTPException(404, "Document not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    result = {
        **record,
        **revision_snapshot(record["document"], id, cad_lock, include_drawing),
    }
    result["undo_id"] = record["parent_id"]
    children = [r for r in list_documents() if r["parent_id"] == id]
    result["redo_id"] = children[0]["id"] if children else None
    return result


def save_document(
    document,
    cad_lock,
    parent_id=None,
    label="Edit",
    provenance=None,
    include_drawing=True,
):
    document_id = "cad-" + uuid.uuid4().hex[:12]
    # Normalize before keying so the subsequent saved-file read is an exact hit.
    value = revision_snapshot(
        normalize_document(document), document_id, cad_lock, include_drawing
    )
    if not value["document_valid"]:
        detail = next(
            (
                x.get("error")
                for x in value["feature_results"]
                if x["status"] == "error"
            ),
            "Feature regeneration failed",
        )
        raise ValueError(detail)
    if parent_id:
        if not (DOCS / (valid_id(parent_id) + ".json")).is_file():
            raise HTTPException(404, "Parent document not found")
    record = {
        "id": document_id,
        "parent_id": parent_id,
        "name": value["document"]["name"],
        "label": label[:150],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "document": value["document"],
        "provenance": provenance,
    }
    DOCS.mkdir(parents=True, exist_ok=True)
    with STORE_LOCK:
        (DOCS / (record["id"] + ".json")).write_text(
            json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        (DATA / "current.json").write_text(
            json.dumps({"id": record["id"]}), encoding="utf-8"
        )
    return {**value, **record, "undo_id": parent_id, "redo_id": None}


def current_document(cad_lock, include_drawing=True):
    pointer = DATA / "current.json"
    if pointer.is_file():
        try:
            return read_document(
                json.loads(pointer.read_text())["id"], cad_lock, include_drawing
            )
        except (KeyError, HTTPException, ValueError):
            pass
    rows = list_documents()
    return (
        read_document(rows[0]["id"], cad_lock, include_drawing)
        if rows
        else save_document(DEFAULT_DOCUMENT, cad_lock, label="Mounting plate example")
    )


def store_asset(data):
    if not 0 < len(data) <= 15_000_000:
        raise ValueError("STEP file must contain 1 byte to 15 MB")
    digest = hashlib.sha256(data).hexdigest()
    ASSETS.mkdir(parents=True, exist_ok=True)
    path = ASSETS / (digest + ".step")
    if not path.exists():
        path.write_bytes(data)
    return digest


def referenced_assets(document):
    histories = [document["features"], *document.get("configurations", {}).values()]
    return sorted(
        {
            f.get("params", {}).get("asset_id")
            for features in histories
            for f in features
            if isinstance(f, dict) and f.get("type") == "import_step"
        }
    )


def portable_document(document):
    return {
        "format": "forma-studio/v1",
        "document": document,
        "assets": {
            key: base64.b64encode(asset_path(key).read_bytes()).decode()
            for key in referenced_assets(document)
        },
    }


class DocumentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: dict
    include_drawing: bool = True


class SaveBody(DocumentBody):
    parent_id: str | None = None
    label: str = Field(default="Edit", max_length=150)


class EnclosureBody(DocumentBody):
    spec: dict
    requirements: dict
    replace_geometry: bool = False


class MotionBody(DocumentBody):
    config: dict | None = None


class SectionBody(DocumentBody):
    section_index: int = Field(ge=0, le=5)
    revision_id: str | None = None


class DrawingBody(DocumentBody):
    revision_id: str | None = None


class CursorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_id: str
    include_drawing: bool = True


class ImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=250)
    content_base64: str = Field(max_length=22_000_000)
    mesh_units: str | None = None
    parent_id: str | None = None


class MeasureBody(DocumentBody):
    selection: list[str] = Field(min_length=1, max_length=2)


class ComponentBody(DocumentBody):
    parent_id: str
    catalog_id: str
    parameters: dict = Field(default_factory=dict)
    translation: list[float] = Field(
        default_factory=lambda: [0, 0, 0], min_length=3, max_length=3
    )
    rotation: list[float] = Field(
        default_factory=lambda: [0, 0, 0], min_length=3, max_length=3
    )
    feature_id: str | None = None


class ComponentImportBody(ImportBody):
    document: dict
    translation: list[float] = Field(
        default_factory=lambda: [0, 0, 0], min_length=3, max_length=3
    )
    rotation: list[float] = Field(
        default_factory=lambda: [0, 0, 0], min_length=3, max_length=3
    )


class PromptBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    prompt: str = Field(min_length=1, max_length=6000)
    selection: list[str] = Field(default_factory=list, max_length=2)
    selected_feature_id: str | None = None
    regenerate: bool = False
    agent_mode: Literal["standard", "tools"] = "standard"
    resume_from: str | None = Field(default=None, max_length=80)
    message_id: str | None = Field(default=None, max_length=80)


def create_router(cad_lock, crate_reader=None):
    router = APIRouter(prefix="/api/studio")
    from .conversations import Conversations

    chat = Conversations(DATA / "conversations.sqlite3", DOCS)

    @router.get("/conversation/{document_id}")
    def conversation(document_id: str):
        return chat.read(valid_id(document_id))

    @router.get("/bootstrap")
    def bootstrap(
        document_id: str | None = None,
        include_document: bool = True,
        include_drawing: bool = True,
    ):
        from .agent import configured

        return {
            "document": (
                (
                    read_document(
                        document_id,
                        cad_lock,
                        **({"include_drawing": False} if not include_drawing else {}),
                    )
                    if document_id
                    else current_document(
                        cad_lock,
                        **({"include_drawing": False} if not include_drawing else {}),
                    )
                )
                if include_document
                else None
            ),
            "documents": list_documents(),
            "capabilities": CAPABILITIES,
            "model": {"name": "muse-wonder-1.0", "configured": configured()},
        }

    @router.post("/preview")
    def preview(body: DocumentBody):
        return snapshot(body.document, cad_lock, include_drawing=body.include_drawing)

    @router.post("/study/recheck")
    def recheck_study(body: SaveBody):
        from .native_study import recheck

        document = normalize_document(body.document)
        folder = DATA / "native-study" / uuid.uuid4().hex
        with cad_lock:
            checked, report = recheck(document, folder, asset_path, cad_lock)
            return save_document(
                checked,
                cad_lock,
                body.parent_id,
                "Native study recheck - "
                + ("passed" if report["passed"] else "issues found"),
                {"actor": "native_tools", "model_calls": 0, "evidence_id": folder.name},
            )

    @router.post("/enclosure/preview")
    def enclosure_preview(body: EnclosureBody):
        return snapshot(
            revise_enclosure(
                body.document, body.spec, body.requirements, body.replace_geometry
            ),
            cad_lock,
        )

    @router.post("/enclosure/options")
    def enclosure_options(body: EnclosureBody):
        from .engine import optimize

        return optimize(body.spec, body.requirements)

    @router.post("/motion")
    def simulate_motion(body: MotionBody):
        with cad_lock:
            return motion_study(
                normalize_document(body.document), body.config, asset_path
            )

    @router.get("/documents")
    def documents():
        return list_documents()

    @router.post("/drawing/section")
    def section_preview(body: SectionBody):
        from .workspace_drawing import section_page, _svg

        doc = normalize_document(body.document)
        context = {}
        if body.revision_id:
            path = DOCS / (valid_id(body.revision_id) + ".json")
            if (
                path.is_file()
                and normalize_document(
                    json.loads(path.read_text(encoding="utf-8"))["document"]
                )
                == doc
            ):
                context["revision_id"] = body.revision_id
        with cad_lock:
            result = built(build_key(doc))
            if not result["checks"]["passed"]:
                raise ValueError("Section requires valid native solid geometry")
            page = section_page(doc, result["parts"], body.section_index, context)
            return {
                "svg": _svg({"layout": "section-v1"}, scene=page["scene"]),
                "measurements": page["measurements"],
                "geometry_signature": geometry_signature(doc),
            }

    @router.post("/drawing/overview")
    def drawing_overview(body: DrawingBody):
        doc = normalize_document(body.document)
        context = {}
        if body.revision_id:
            path = DOCS / (valid_id(body.revision_id) + ".json")
            if (
                path.is_file()
                and normalize_document(
                    json.loads(path.read_text(encoding="utf-8"))["document"]
                )
                == doc
            ):
                context["revision_id"] = body.revision_id
        with cad_lock:
            native = built(build_key(doc))
            if not native["checks"]["passed"]:
                raise ValueError("Drawing requires valid native solids")
            svg = projected(drawing_key(doc, context))
        return {
            "svg": svg,
            "geometry_signature": geometry_signature(doc),
            "geometry_version": GEOMETRY_VERSION,
            "asset_identity": asset_identity(doc, asset_path),
        }

    @router.post("/documents")
    def create(body: SaveBody):
        return save_document(
            body.document,
            cad_lock,
            body.parent_id,
            body.label,
            include_drawing=body.include_drawing,
        )

    @router.get("/documents/{id}")
    def document(id: str, include_drawing: bool = True):
        return read_document(id, cad_lock, include_drawing)

    @router.post("/undo")
    def undo(body: CursorBody):
        current = read_document(body.current_id, cad_lock, body.include_drawing)
        target = current["undo_id"] or current["id"]
        (DATA / "current.json").write_text(json.dumps({"id": target}), encoding="utf-8")
        return read_document(target, cad_lock, body.include_drawing)

    @router.post("/redo")
    def redo(body: CursorBody):
        current = read_document(body.current_id, cad_lock, body.include_drawing)
        target = current["redo_id"] or current["id"]
        (DATA / "current.json").write_text(json.dumps({"id": target}), encoding="utf-8")
        return read_document(target, cad_lock, body.include_drawing)

    @router.post("/from-crate/{id}")
    def from_crate(id: str):
        if crate_reader is None:
            raise HTTPException(404, "Enclosure conversion is unavailable")
        source = crate_reader(id)
        features = enclosure_features(source["panels"])
        names = {f"body_{i + 1:03d}": p["name"] for i, p in enumerate(source["panels"])}
        doc = {
            "name": source["spec"]["name"],
            "features": features,
            "annotations": [],
            "display": {"body_names": names},
            "metadata": {
                "source_crate_id": id,
                "source_spec": source["spec"],
                "source_requirements": source["requirements"],
            },
        }
        return save_document(
            doc, cad_lock, label="Enclosure imported as editable panels"
        )

    def parse_import(body: ImportBody):
        try:
            data = base64.b64decode(body.content_base64, validate=True)
        except Exception:
            raise ValueError("File content is not valid base64") from None
        if len(data) > 15_000_000:
            raise ValueError("Import limit is 15 MB")
        suffix = Path(body.filename).suffix.lower()
        name = Path(body.filename.replace("\\", "/")).stem[:100] or "Imported part"
        if suffix in [".step", ".stp"]:
            key = store_asset(data)
            doc = {
                "name": name,
                "features": [
                    {
                        "id": "import-" + uuid.uuid4().hex[:8],
                        "type": "import_step",
                        "name": "Imported STEP solids",
                        "params": {"asset_id": key},
                        "suppressed": False,
                    }
                ],
                "annotations": [],
                "display": {},
                "metadata": {
                    "import_filename": name,
                    "import_units": "STEP unit conversion to millimetres",
                },
            }
        elif suffix in (".stl", ".obj"):
            from .mesh_import import import_mesh

            ASSETS.mkdir(parents=True, exist_ok=True)
            original = ASSETS / (hashlib.sha256(data).hexdigest() + suffix)
            if not original.exists():
                original.write_bytes(data)
            with cad_lock:
                shape, conversion = import_mesh(data, suffix[1:], body.mesh_units)
                # The standard STEP asset path then supplies every existing CAD
                # editing, caching and portable-project operation.
                from .mesh_import import CONVERSION_VERSION

                converted = ASSETS / (
                    hashlib.sha256(
                        data + body.mesh_units.encode() + CONVERSION_VERSION.encode()
                    ).hexdigest()
                    + ".converted.step"
                )
                if not converted.exists():
                    import cadquery as cq

                    cq.exporters.export(shape, str(converted))
                key = store_asset(converted.read_bytes())
            doc = {
                "name": name,
                "features": [
                    {
                        "id": "import-" + uuid.uuid4().hex[:8],
                        "type": "import_step",
                        "name": "Imported " + suffix[1:].upper() + " solid",
                        "params": {"asset_id": key},
                        "suppressed": False,
                    }
                ],
                "annotations": [],
                "display": {},
                "metadata": {"import_filename": name, "mesh_conversion": conversion},
            }
        elif suffix == ".json":
            try:
                value = json.loads(
                    data.decode("utf-8-sig"),
                    parse_constant=lambda _: (_ for _ in ()).throw(
                        ValueError("Non-finite JSON")
                    ),
                )
            except (ValueError, UnicodeError):
                raise ValueError("Invalid project JSON") from None
            if not isinstance(value, dict):
                raise ValueError("Project JSON must contain an object")
            doc = value.get("document", value)
            assets = value.get("assets", {})
            if not isinstance(assets, dict) or len(assets) > 50:
                raise ValueError("Invalid project assets")
            total = 0
            for key, encoded in assets.items():
                if not isinstance(key, str) or not isinstance(encoded, str):
                    raise ValueError("Invalid portable asset data")
                raw = base64.b64decode(encoded, validate=True)
                total += len(raw)
                if total > 15_000_000 or hashlib.sha256(raw).hexdigest() != key:
                    raise ValueError("Portable STEP asset hash/size check failed")
                store_asset(raw)
        elif suffix == ".dxf":
            try:
                dxf = ezdxf.read(io.StringIO(data.decode("utf-8-sig")))
            except Exception as error:
                raise ValueError("DXF could not be read: " + str(error)[:100]) from None
            if dxf.units == 0:
                raise ValueError(
                    "DXF units are unspecified. Declare its units before importing so dimensions can be converted correctly."
                )
            try:
                unit_scale = ezdxf.units.conversion_factor(dxf.units, 4)
            except Exception:
                raise ValueError("Unsupported DXF unit definition") from None
            entities = [
                e for e in dxf.modelspace() if e.dxftype() in ["CIRCLE", "LWPOLYLINE"]
            ]
            if len(entities) != 1:
                raise ValueError(
                    "DXF import supports one circle or one closed straight polyline; nested/multiple contours require separate sketches"
                )
            entity = entities[0]
            if tuple(entity.dxf.extrusion) != (0, 0, 1):
                raise ValueError(
                    "DXF profile must use the world XY plane; non-XY object-coordinate systems are unsupported"
                )
            if entity.dxftype() == "CIRCLE":
                params = {
                    "shape": "circle",
                    "radius": entity.dxf.radius * unit_scale,
                    "cx": entity.dxf.center.x * unit_scale,
                    "cy": entity.dxf.center.y * unit_scale,
                    "z": entity.dxf.center.z * unit_scale,
                    "height": 10,
                }
            else:
                if not entity.closed or any(
                    abs(p[4]) > 1e-12 for p in entity.get_points()
                ):
                    raise ValueError(
                        "Import a closed straight-segment DXF polyline; curved bulges are unsupported"
                    )
                params = {
                    "shape": "polyline",
                    "points": [
                        [p[0] * unit_scale, p[1] * unit_scale]
                        for p in entity.get_points()
                    ],
                    "z": entity.dxf.elevation * unit_scale,
                    "height": 10,
                }
            doc = {
                "name": name,
                "features": [
                    {
                        "id": "dxf-" + uuid.uuid4().hex[:8],
                        "type": "sketch_extrude",
                        "name": "Imported profile · 10 mm extrusion",
                        "params": params,
                        "suppressed": False,
                    }
                ],
                "annotations": [],
                "display": {},
                "metadata": {
                    "dxf_source_units": dxf.units,
                    "dxf_scale_to_mm": unit_scale,
                    "dxf_units": "Declared source units converted to mm",
                },
            }
        else:
            raise ValueError(
                "Supported imports: STEP, STP, single-profile DXF, or Forma Studio JSON. Native SLDPRT/DWG is not supported."
            )
        return doc

    @router.post("/import")
    def import_document(body: ImportBody):
        doc = parse_import(body)
        suffix = Path(body.filename).suffix.lower()
        return save_document(
            doc, cad_lock, body.parent_id, "Imported " + suffix.upper().lstrip(".")
        )

    @router.get("/components")
    def component_catalog():
        from .component_library import catalog

        return {
            "components": catalog(),
            "scope": "Native reference geometry. Check alignment, interference and supplier specifications after insertion.",
        }

    @router.post("/components/insert")
    def insert_component(body: ComponentBody):
        from .component_library import materialize, insert

        # Verify parent exists and do not silently append to an obsolete revision.
        parent = read_document(body.parent_id, cad_lock)
        doc = normalize_document(body.document)
        if parent["document"] != doc:
            raise HTTPException(
                409, "Save or discard local edits before inserting a component"
            )
        with cad_lock:
            record = materialize(
                body.catalog_id, body.parameters, DATA / "component-cache", store_asset
            )
            doc, ident = insert(
                doc, record, body.translation, body.rotation, body.feature_id
            )
            result = built(build_key(doc))
            if not result["checks"]["passed"]:
                raise ValueError(
                    "Component insertion could not regenerate: "
                    + str(result["checks"].get("error"))
                )
        saved = save_document(
            doc,
            cad_lock,
            body.parent_id,
            ("Edit" if body.feature_id else "Insert")
            + " component · "
            + record["name"],
        )
        saved["selected_feature_id"] = ident
        return saved

    @router.post("/components/import")
    def import_component(body: ComponentImportBody):
        if Path(body.filename).suffix.lower() not in (".step", ".stp", ".stl", ".obj"):
            raise ValueError("Insert a STEP, STP, STL or OBJ component")
        if body.parent_id is None:
            raise ValueError("Select a saved parent design")
        parent = read_document(body.parent_id, cad_lock)
        doc = normalize_document(body.document)
        if parent["document"] != doc:
            raise HTTPException(
                409, "Save or discard local edits before inserting a component"
            )
        imported = parse_import(body)
        feature = imported["features"][0]
        feature["params"].update(translation=body.translation, rotation=body.rotation)
        doc["features"].append(feature)
        doc["metadata"].setdefault("component_instances", {})[feature["id"]] = {
            "catalog_id": None,
            "name": feature["name"],
            "asset_id": feature["params"]["asset_id"],
            "source": body.filename,
            "license": "User-supplied; verify permission",
            "parameters": {},
            "scope": "Imported geometry; original parametric feature history is not recovered.",
            **imported.get("metadata", {}),
        }
        with cad_lock:
            result = built(build_key(doc))
            if not result["checks"]["passed"]:
                raise ValueError(
                    "Component insertion could not regenerate: "
                    + str(result["checks"].get("error"))
                )
        saved = save_document(
            doc, cad_lock, body.parent_id, "Insert file component · " + imported["name"]
        )
        saved["selected_feature_id"] = feature["id"]
        return saved

    @router.post("/measure")
    def measure(body: MeasureBody):
        doc = normalize_document(body.document)
        with cad_lock:
            result = built(build_key(doc))
            meta = {x["id"]: x for x in result["face_meshes"] + result["edge_meta"]}
            selected = []
            shapes = []
            for key in body.selection:
                if key not in meta:
                    raise ValueError(
                        "Selection references outdated topology; select again after regeneration"
                    )
                selected.append(
                    {
                        k: v
                        for k, v in meta[key].items()
                        if k not in ["vertices", "triangles"]
                    }
                )
                part, kind, ordinal = re.fullmatch(
                    r"(body_\d+):(face|edge)_(\d+)", key
                ).groups()
                shape = next(p["shape"] for p in result["parts"] if p["id"] == part)
                shapes.append(
                    (shape.Faces() if kind == "face" else shape.Edges())[int(ordinal)]
                )
            record = {
                "selection": selected,
                "units": "mm",
                "topology_scope": result["checks"]["topology_ids"],
            }
            if len(shapes) == 2:
                import math

                record["distance_mm"] = float(shapes[0].distance(shapes[1]))
                record["center_distance_mm"] = float(
                    shapes[0].Center().sub(shapes[1].Center()).Length
                )
                if all(x.get("normal") is not None for x in selected):
                    a, b = selected[0]["normal"], selected[1]["normal"]
                    cosine = sum(x * y for x, y in zip(a, b)) / math.sqrt(
                        sum(x * x for x in a) * sum(x * x for x in b)
                    )
                    record["angle_degrees"] = math.degrees(
                        math.acos(max(-1, min(1, cosine)))
                    )
            return record

    @router.post("/interference")
    def interference(body: DocumentBody):
        doc = normalize_document(body.document)
        pairs = []
        with cad_lock:
            parts = built(build_key(doc))["parts"]
            for i, first in enumerate(parts):
                a = first["shape"].BoundingBox()
                for second in parts[i + 1 :]:
                    b = second["shape"].BoundingBox()
                    if (
                        min(a.xmax, b.xmax) - max(a.xmin, b.xmin) <= 1e-8
                        or min(a.ymax, b.ymax) - max(a.ymin, b.ymin) <= 1e-8
                        or min(a.zmax, b.zmax) - max(a.zmin, b.zmin) <= 1e-8
                    ):
                        continue
                    volume = first["shape"].intersect(second["shape"]).Volume()
                    if volume > 1e-7:
                        pairs.append(
                            {
                                "parts": [first["id"], second["id"]],
                                "volume_mm3": float(volume),
                            }
                        )
        return {
            "pairs": pairs,
            "interference_count": len(pairs),
            "passed": not pairs,
            "scope": "Positive-volume BREP intersections only; intended joins and contact require review.",
        }

    @router.get("/checkpoints/{id}")
    def retained_checkpoint(id: str, document_id: str):
        from .workspace_agent import RUNS
        from .design_checkpoint import _canonical_project, retained_context

        folder = RUNS / valid_id(id)
        prior_path = folder / "proposal.json"
        events_path = folder / "events.jsonl"
        if not prior_path.is_file() or not events_path.is_file():
            raise HTTPException(404, "No retained completed checkpoint")
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        if prior.get("status") != "incomplete" or not prior.get("has_checkpoint"):
            raise HTTPException(
                409, "Only an incomplete retained design can be reopened"
            )
        try:
            context = retained_context(id)
        except (ValueError, KeyError, OSError) as error:
            raise HTTPException(
                409, "Checkpoint has no recoverable original design context"
            ) from error
        current = read_document(document_id, cad_lock, include_drawing=False)
        if _canonical_project(context["project"]) != _canonical_project(
            current["document"]
        ):
            raise HTTPException(409, "Checkpoint source changed; start a new proposal")
        selection = context.get("selection") or {}
        if selection.get("topology_ids"):
            raise HTTPException(
                409,
                "Geometry-selected checkpoints require the original selection session; portable recovery supports document and feature selections",
            )
        return {
            "prompt": context["original_instruction"],
            "selection": selection,
            "proposal": prior,
        }

    @router.post("/agent", status_code=202)
    def start_agent(body: PromptBody):
        from .workspace_agent import propose_document
        from .design_agent import propose_design
        from .agent import configured

        if body.resume_from is not None and body.agent_mode != "tools":
            raise ValueError("Only a tool-driven design can resume a checkpoint")

        if not configured():
            raise HTTPException(503, "Meta API is not configured")
        base = read_document(body.document_id, cad_lock, include_drawing=False)
        known = {
            x["id"]
            for x in base["geometry"]["face_meshes"] + base["geometry"]["edge_meta"]
        }
        if any(key not in known for key in body.selection):
            raise ValueError("Select geometry again after regeneration")
        if body.selected_feature_id is not None and body.selected_feature_id not in {
            f["id"] for f in base["document"]["features"]
        }:
            raise ValueError("Unknown selected feature")
        request_key = hashlib.sha256(
            json.dumps(
                {
                    "document_id": body.document_id,
                    "prompt": body.prompt,
                    "selection": body.selection,
                    "selected_feature_id": body.selected_feature_id,
                    "agent_mode": body.agent_mode,
                    "resume_from": body.resume_from,
                    "message_id": body.message_id,
                },
                sort_keys=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        with JOBS_LOCK:
            for previous in reversed(list(JOBS.values())):
                if previous.get("request_key") == request_key:
                    active = previous["status"] in ("queued", "running")
                    reusable = previous.get("proposal", {}).get("status") == "ready"
                    if active or (not body.regenerate and reusable):
                        return deepcopy(
                            {
                                key: value
                                for key, value in previous.items()
                                if not key.startswith("_")
                            }
                        )
            if any(x["status"] in ["queued", "running"] for x in JOBS.values()):
                raise HTTPException(409, "A Studio proposal is already running")
            id = "studio-" + uuid.uuid4().hex[:12]
            JOBS[id] = {
                "id": id,
                "document_id": body.document_id,
                "status": "queued",
                "stage": "Queued",
                "events": [],
                "request_key": request_key,
                "agent_mode": body.agent_mode,
            }

        def event(kind, message):
            with JOBS_LOCK:
                JOBS[id]["stage"] = message
                JOBS[id]["events"].append({"kind": kind, "message": message})

        def preview(document, candidate_id):
            value = snapshot(document, cad_lock, include_drawing=False)
            with JOBS_LOCK:
                sequence = JOBS[id].get("preview", {}).get("sequence", 0) + 1
                JOBS[id]["_preview_snapshot"] = value
                JOBS[id]["preview"] = {
                    "sequence": sequence,
                    "candidate_id": candidate_id,
                    "feature_count": len(document["features"]),
                    "base_document_id": body.document_id,
                    "scope": "Working native geometry; not applied or mechanically approved",
                }

        def work():
            try:
                JOBS[id]["status"] = "running"
                chat.save_job(JOBS[id])
                prior_conversation = chat.context(body.document_id)
                chat.append(body.document_id, id, "user", {"text": body.prompt})
                planner = (
                    propose_design if body.agent_mode == "tools" else propose_document
                )
                p = planner(
                    base["document"],
                    body.prompt,
                    asset_loader=asset_path,
                    on_event=event,
                    **(
                        {
                            "on_preview": preview,
                            "component_store": store_asset,
                            "max_turns": 20,
                            "max_tokens": 32768 if body.resume_from else 16384,
                        }
                        if body.agent_mode == "tools"
                        else {}
                    ),
                    run_id=id,
                    geometry_lock=cad_lock,
                    selection_context={
                        "feature_id": body.selected_feature_id,
                        "topology_ids": body.selection,
                    },
                    use_cache=not body.regenerate,
                    conversation_context=prior_conversation,
                    **(
                        {"resume_from": body.resume_from}
                        if body.agent_mode == "tools"
                        else {}
                    ),
                )
                if p["status"] == "ready":
                    p["snapshot"] = snapshot(
                        p["document"], cad_lock, include_drawing=False
                    )
                chat.append(
                    body.document_id,
                    id,
                    "assistant",
                    {
                        "text": p.get("summary", ""),
                        "questions": p.get("questions", []),
                        "status": p.get("status"),
                        "estimated_cost_usd": p.get("estimated_cost_usd"),
                    },
                )
                with JOBS_LOCK:
                    JOBS[id].update(
                        status="completed", stage="Review proposal", proposal=p
                    )
                    chat.save_job(JOBS[id])
            except Exception as error:
                try:
                    chat.append(
                        body.document_id,
                        id,
                        "assistant",
                        {"text": str(error), "status": "error"},
                    )
                except Exception as persistence_error:
                    with JOBS_LOCK:
                        JOBS[id]["conversation_error"] = str(persistence_error)
                with JOBS_LOCK:
                    JOBS[id].update(
                        status="failed", stage="Request failed", error=str(error)
                    )

        threading.Thread(target=work, daemon=True).start()
        with JOBS_LOCK:
            return deepcopy(
                {
                    key: value
                    for key, value in JOBS[id].items()
                    if not key.startswith("_")
                }
            )

    @router.get("/jobs/{id}")
    def get_job(id: str):
        with JOBS_LOCK:
            missing = id not in JOBS
        if missing:
            # Never wait for native CAD while holding the progress/job lock:
            # an active CAD worker may need that lock to report a tool event.
            retained = chat.read_job(id)
            if retained is None:
                raise HTTPException(404, "Proposal not found")
            from .workspace_agent import RUNS

            path = RUNS / id / "proposal.json"
            if path.is_file():
                proposal = json.loads(path.read_text(encoding="utf-8"))
                if proposal.get("status") == "ready":
                    proposal["snapshot"] = snapshot(
                        proposal["document"], cad_lock, include_drawing=False
                    )
                retained.update(
                    status="completed", stage="Retained proposal", proposal=proposal
                )
            else:
                retained.update(
                    status="failed",
                    error="The previous server stopped before a final response was saved. Raw receipts remain retained; no request was automatically repeated.",
                )
            with JOBS_LOCK:
                JOBS.setdefault(id, retained)
        with JOBS_LOCK:
            return deepcopy(
                {
                    key: value
                    for key, value in JOBS[id].items()
                    if not key.startswith("_")
                }
            )

    @router.get("/jobs/{id}/preview")
    def get_preview(id: str, sequence: int | None = None):
        with JOBS_LOCK:
            job = JOBS.get(id)
            if job is None:
                raise HTTPException(404, "Proposal not found")
            if "preview" not in job:
                raise HTTPException(404, "No native candidate is available yet")
            if sequence is not None and sequence != job["preview"]["sequence"]:
                raise HTTPException(409, "Draft advanced; refresh the preview")
            return {
                "preview": deepcopy(job["preview"]),
                "snapshot": deepcopy(job["_preview_snapshot"]),
            }

    @router.post("/proposals/{id}/apply")
    def apply_proposal(id: str):
        get_job(id)
        with STORE_LOCK:
            with JOBS_LOCK:
                job = deepcopy(JOBS.get(id))
            if (
                not job
                or job["status"] != "completed"
                or job.get("proposal", {}).get("status") != "ready"
            ):
                raise HTTPException(
                    409, "Only a ready verified proposal can be applied"
                )
            if job.get("applied_id"):
                return read_document(job["applied_id"], cad_lock, include_drawing=False)
            p = job["proposal"]
            saved = save_document(
                p["document"],
                cad_lock,
                job["document_id"],
                p["summary"],
                {
                    "model": p["model"],
                    "run_id": p["run_id"],
                    "response_ids": p["response_ids"],
                    "cache": p.get("cache", {}),
                },
                include_drawing=False,
            )
            with JOBS_LOCK:
                JOBS[id]["applied_id"] = saved["id"]
                chat.save_job(JOBS[id])
            return saved

    @router.get("/documents/{id}/export/{format}")
    def export(id: str, format: str):
        value = read_document(id, cad_lock, include_drawing=False)
        if format not in CAPABILITIES["exports"]:
            raise HTTPException(404, "Unknown export format")
        if format == "print":
            from .folding_print import export_print_pack as folding_print_pack
            from .mechanical_print import export_print_pack as mechanical_print_pack

            folder = (
                DATA
                / "exports"
                / valid_id(id)
                / export_key(value["document"])
                / "print"
            )
            with cad_lock:
                if not (folder / "complete.json").is_file():
                    document = value["document"]
                    if any(
                        f["type"] == "folding_assembly" for f in document["features"]
                    ):
                        packed = folding_print_pack(document, folder, asset_path)
                    else:
                        packed = mechanical_print_pack(
                            document,
                            folder,
                            asset_path,
                            context={
                                "revision_id": id,
                                "pose": "Source construction pose",
                            },
                            portable_source=portable_document(document),
                        )
                    (folder / "complete.json").write_text(
                        json.dumps(
                            {
                                "verified": packed["manifest"][
                                    "geometric_print_preflight_passed"
                                ]
                            }
                        ),
                        encoding="utf-8",
                    )
            return FileResponse(
                folder / "print-pack.zip",
                media_type="application/zip",
                filename="print-pack.zip",
            )
        folder = DATA / "exports" / valid_id(id) / export_key(value["document"])
        with cad_lock:
            if not (folder / "complete.json").is_file():
                result = export_document(value["document"], asset_path, folder)
                if not result["checks"]["passed"]:
                    raise ValueError(
                        result["checks"].get("error") or "Export verification failed"
                    )
                parts = built(build_key(value["document"]))["parts"]
                from .component_exports import export_components

                export_components(built(build_key(value["document"])), folder)
                drawing = export_drawings(
                    value["document"], parts, folder, context={"revision_id": id}
                )
                portable = portable_document(value["document"])
                workflow = {
                    "revision_id": id,
                    "geometry_signature": value["geometry_signature"],
                    "requirements": value["requirements_state"],
                    "design_review": value["design_review_state"],
                    "native_study": value["native_study_state"],
                    "motion": {"status": "not_configured"},
                }
                if value["requirements_state"]["status"] == "current":
                    workflow["panel_pack"] = export_panel_pack(
                        value["document"], folder
                    )
                if value["document"]["metadata"].get("design_mechanism"):
                    # Geometry export is not an implicit request to rerun an
                    # arbitrarily long mechanism analysis. Retained, source-bound
                    # study/review status remains in the same workflow report.
                    # The print-release route still reruns all required studies.
                    workflow["motion"] = {
                        "status": "not_rechecked_at_export",
                        "declared_spec": value["document"]["metadata"][
                            "design_mechanism"
                        ],
                        "scope": "Native STEP/STL and drawing geometry are verified during export. Motion is a separate study; run Motion or Recheck native study for current collision evidence. Retained native-study and design-review status are reported above.",
                    }
                elif any(
                    key in value["document"]["metadata"]
                    for key in ("motion", "design_mechanism")
                ):
                    try:
                        workflow["motion"] = {
                            "status": "current",
                            "study": motion_study(
                                value["document"], asset_loader=asset_path
                            ),
                        }
                    except ValueError as error:
                        workflow["motion"] = {"status": "stale", "detail": str(error)}
                (folder / "workflow-report.json").write_text(
                    json.dumps(workflow, indent=2, allow_nan=False), encoding="utf-8"
                )
                with (folder / "body-list.csv").open(
                    "w", newline="", encoding="utf-8"
                ) as body_csv:
                    writer = csv.writer(body_csv)
                    writer.writerow(
                        [
                            "body_id",
                            "name",
                            "quantity",
                            "volume_mm3",
                            "surface_area_mm2",
                            "width_mm",
                            "depth_mm",
                            "height_mm",
                        ]
                    )
                    for part in parts:
                        shape = part["shape"]
                        lo, hi = exact_bounds_mm(shape)
                        name = str(
                            value["document"]["display"]
                            .get("body_names", {})
                            .get(part["id"], part["name"])
                        )
                        if name.startswith(("=", "+", "-", "@", "\t", "\r")):
                            name = "'" + name
                        writer.writerow(
                            [
                                part["id"],
                                name,
                                1,
                                shape.Volume(),
                                shape.Area(),
                                *[hi[i] - lo[i] for i in range(3)],
                            ]
                        )
                (folder / "project.json").write_text(
                    json.dumps(portable, indent=2, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8",
                )
                from .component_library import instances

                (folder / "library-components.json").write_text(
                    json.dumps(
                        {
                            "scope": "Declared source component instances, including suppressed features; downstream patterns/booleans can change final body quantities and geometry.",
                            "instances": instances(value["document"]),
                        },
                        indent=2,
                        ensure_ascii=False,
                        allow_nan=False,
                    ),
                    encoding="utf-8",
                )
                (folder / "export-manifest.json").write_text(
                    json.dumps(
                        {
                            "format": "forma-export/v1",
                            "revision_id": id,
                            "geometry_signature": value["geometry_signature"],
                            "generation": "Deterministic native CAD and drawing tools; no model call during export",
                            "parameters": "project.json retains editable feature parameters, annotations and project metadata; STEP/STL/PDF do not retain the feature history",
                            "units": {
                                "workspace.step": "mm, encoded by STEP exporter",
                                "workspace.stl": "mm by convention; STL itself has no length-unit field",
                                "components.zip": "Separate native bodies as individual STL files, original coordinates, mm by convention; read-back checks in components.json",
                                "drawing.dxf": "mm, INSUNITS=4; model-space projections 1:1",
                                "drawing.pdf": "A3 landscape; declared common model scale; print 100%",
                                "drawing.svg": "420 x 280 mm content; declared common model scale",
                                "body-list.csv": "dimensions mm, volume mm3, area mm2",
                                "design-parameters.csv": "Complete source parameter values with meanings and units; inactive parameters are labelled",
                            },
                            "drawing_scope": "Measured overall BREP extents and complete parameter appendix with embedded Unicode font; not a complete local-feature/tolerance manufacturing drawing; user dimensions are REF",
                            "folding_print": "workspace.stl is the assembled source pose. Use the separate Folding print pack for oriented independent parts, build plates, fit coupon and assembly instructions.",
                            "separate_bodies": "components.zip preserves independent bodies even when they touch. It is not an oriented build-plate layout or print qualification. Assembled workspace.stl can fuse movable interfaces.",
                            "curve_chord_deflection_mm": drawing["measurements"][
                                "curve_chord_deflection_mm"
                            ],
                            "byte_repeatability": "Geometry is regenerated from source; STEP/DXF exporter timestamps or identifiers and ZIP metadata may vary",
                            "verification": "verification.json contains reopened STEP/STL checks; workflow-report.json binds engineering/motion status to this revision",
                        },
                        indent=2,
                        allow_nan=False,
                    ),
                    encoding="utf-8",
                )
                files = [
                    p
                    for p in sorted(folder.iterdir())
                    if p.is_file()
                    and (p.suffix != ".zip" or p.name == "components.zip")
                    and p.name not in ("complete.json", "sha256.json")
                ]
                hashes = {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files
                }
                (folder / "sha256.json").write_text(
                    json.dumps(hashes, indent=2), encoding="utf-8"
                )
                with zipfile.ZipFile(
                    folder / "studio-bundle.zip", "w", zipfile.ZIP_DEFLATED
                ) as z:
                    for p in files + [folder / "sha256.json"]:
                        z.write(p, p.name)
                (folder / "complete.json").write_text(
                    json.dumps(
                        {"geometry": result["checks"], "drawing": drawing}, indent=2
                    ),
                    encoding="utf-8",
                )
        file = {
            "step": "workspace.step",
            "stl": "workspace.stl",
            "components": "components.zip",
            "json": "project.json",
            "svg": "drawing.svg",
            "pdf": "drawing.pdf",
            "dxf": "drawing.dxf",
            "csv": "body-list.csv",
            "bundle": "studio-bundle.zip",
        }[format]
        return FileResponse(
            folder / file,
            media_type={
                "svg": "image/svg+xml",
                "pdf": "application/pdf",
                "json": "application/json",
                "csv": "text/csv",
            }.get(format),
            filename=file,
        )

    return router
