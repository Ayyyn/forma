"""Persistent, human-editable feature documents. Only declarative CAD operations."""

from copy import deepcopy
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
    build_document,
    export_document,
    _bounds as exact_bounds_mm,
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
            "workspace_server.py",
            "component_exports.py",
            "workspace_requirements.py",
            "workspace_workflow.py",
            "folding_study.py",
            "folding_print.py",
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
    "limits": {"features": 60, "bodies": 50, "upload_bytes": 15_000_000},
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
    if not isinstance(doc.get("features"), list) or len(doc["features"]) > 60:
        raise ValueError("A document supports up to 60 features")
    doc.setdefault("annotations", [])
    validate_annotations(doc)
    doc.setdefault("display", {})
    doc.setdefault("metadata", {})
    if not isinstance(doc["display"], dict) or not isinstance(doc["metadata"], dict):
        raise ValueError("Document display and metadata must be objects")
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


def build_key(doc):
    normalized = normalize_document(doc)
    return json.dumps(
        {"features": normalized["features"]}, sort_keys=True, allow_nan=False
    )


def drawing_key(doc):
    return json.dumps(
        {
            "features": doc["features"],
            "name": doc["name"],
            "annotations": doc["annotations"],
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
    return drawing_svg(doc, built(build_key(doc))["parts"])


def snapshot(document, cad_lock):
    doc = normalize_document(document)
    with cad_lock:
        result = built(build_key(doc))
        statuses = result["features"]
        empty = not doc["features"] or all(
            f.get("suppressed", False) for f in doc["features"]
        )
        valid = bool(result["checks"]["passed"])
        drawing_error = None
        try:
            sheet = (
                projected(drawing_key(doc))
                if valid
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
        "geometry_signature": geometry_signature(doc),
        "geometry": {
            "parts": meshes,
            "face_meshes": result["face_meshes"],
            "edge_meta": result["edge_meta"],
        },
        "metrics": result["metrics"],
        "checks": checks,
        "feature_results": statuses,
        "passed": valid,
        "document_valid": valid or empty,
        "drawing_svg": sheet,
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


def read_document(id, cad_lock):
    path = DOCS / (valid_id(id) + ".json")
    if not path.is_file():
        raise HTTPException(404, "Document not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    result = {**snapshot(record["document"], cad_lock), **record}
    result["undo_id"] = record["parent_id"]
    children = [r for r in list_documents() if r["parent_id"] == id]
    result["redo_id"] = children[0]["id"] if children else None
    return result


def save_document(document, cad_lock, parent_id=None, label="Edit", provenance=None):
    value = snapshot(document, cad_lock)
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
        read_document(parent_id, cad_lock)
    record = {
        "id": "cad-" + uuid.uuid4().hex[:12],
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


def current_document(cad_lock):
    pointer = DATA / "current.json"
    if pointer.is_file():
        try:
            return read_document(json.loads(pointer.read_text())["id"], cad_lock)
        except (KeyError, HTTPException, ValueError):
            pass
    rows = list_documents()
    return (
        read_document(rows[0]["id"], cad_lock)
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


class SaveBody(DocumentBody):
    parent_id: str | None = None
    label: str = Field(default="Edit", max_length=150)


class EnclosureBody(DocumentBody):
    spec: dict
    requirements: dict
    replace_geometry: bool = False


class MotionBody(DocumentBody):
    config: dict | None = None


class CursorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_id: str


class ImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(min_length=1, max_length=250)
    content_base64: str = Field(max_length=22_000_000)
    mesh_units: str | None = None
    parent_id: str | None = None


class MeasureBody(DocumentBody):
    selection: list[str] = Field(min_length=1, max_length=2)


class PromptBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    prompt: str = Field(min_length=1, max_length=6000)
    selection: list[str] = Field(default_factory=list, max_length=2)
    selected_feature_id: str | None = None
    regenerate: bool = False
    agent_mode: Literal["standard", "tools"] = "standard"
    resume_from: str | None = Field(default=None, max_length=80)


def create_router(cad_lock, crate_reader=None):
    router = APIRouter(prefix="/api/studio")

    @router.get("/bootstrap")
    def bootstrap():
        from .agent import configured

        return {
            "document": current_document(cad_lock),
            "documents": list_documents(),
            "capabilities": CAPABILITIES,
            "model": {"name": "muse-wonder-1.0", "configured": configured()},
        }

    @router.post("/preview")
    def preview(body: DocumentBody):
        return snapshot(body.document, cad_lock)

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

    @router.post("/documents")
    def create(body: SaveBody):
        return save_document(body.document, cad_lock, body.parent_id, body.label)

    @router.get("/documents/{id}")
    def document(id: str):
        return read_document(id, cad_lock)

    @router.post("/undo")
    def undo(body: CursorBody):
        current = read_document(body.current_id, cad_lock)
        target = current["undo_id"] or current["id"]
        (DATA / "current.json").write_text(json.dumps({"id": target}), encoding="utf-8")
        return read_document(target, cad_lock)

    @router.post("/redo")
    def redo(body: CursorBody):
        current = read_document(body.current_id, cad_lock)
        target = current["redo_id"] or current["id"]
        (DATA / "current.json").write_text(json.dumps({"id": target}), encoding="utf-8")
        return read_document(target, cad_lock)

    @router.post("/from-crate/{id}")
    def from_crate(id: str):
        if crate_reader is None:
            raise HTTPException(404, "Enclosure conversion is unavailable")
        source = crate_reader(id)
        features = enclosure_features(source["panels"])
        names = {f"body_{i+1:03d}": p["name"] for i, p in enumerate(source["panels"])}
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

    @router.post("/import")
    def import_document(body: ImportBody):
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
        return save_document(
            doc, cad_lock, body.parent_id, "Imported " + suffix.upper().lstrip(".")
        )

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

    @router.post("/agent", status_code=202)
    def start_agent(body: PromptBody):
        from .workspace_agent import propose_document
        from .design_agent import propose_design
        from .agent import configured

        if body.resume_from is not None and body.agent_mode != "tools":
            raise ValueError("Only a tool-driven design can resume a checkpoint")

        if not configured():
            raise HTTPException(503, "Meta API is not configured")
        base = read_document(body.document_id, cad_lock)
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
                        return deepcopy(previous)
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

        def work():
            try:
                JOBS[id]["status"] = "running"
                planner = (
                    propose_design if body.agent_mode == "tools" else propose_document
                )
                p = planner(
                    base["document"],
                    body.prompt,
                    asset_loader=asset_path,
                    on_event=event,
                    run_id=id,
                    geometry_lock=cad_lock,
                    selection_context={
                        "feature_id": body.selected_feature_id,
                        "topology_ids": body.selection,
                    },
                    use_cache=not body.regenerate,
                    **(
                        {"resume_from": body.resume_from}
                        if body.agent_mode == "tools"
                        else {}
                    ),
                )
                if p["status"] == "ready":
                    p["snapshot"] = snapshot(p["document"], cad_lock)
                with JOBS_LOCK:
                    JOBS[id].update(
                        status="completed", stage="Review proposal", proposal=p
                    )
            except Exception as error:
                with JOBS_LOCK:
                    JOBS[id].update(
                        status="failed", stage="Request failed", error=str(error)
                    )

        threading.Thread(target=work, daemon=True).start()
        return deepcopy(JOBS[id])

    @router.get("/jobs/{id}")
    def get_job(id: str):
        with JOBS_LOCK:
            if id not in JOBS:
                raise HTTPException(404, "Proposal not found")
            return deepcopy(JOBS[id])

    @router.post("/proposals/{id}/apply")
    def apply_proposal(id: str):
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
                return read_document(job["applied_id"], cad_lock)
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
            )
            with JOBS_LOCK:
                JOBS[id]["applied_id"] = saved["id"]
            return saved

    @router.get("/documents/{id}/export/{format}")
    def export(id: str, format: str):
        value = read_document(id, cad_lock)
        if format not in CAPABILITIES["exports"]:
            raise HTTPException(404, "Unknown export format")
        if format == "print":
            from .folding_print import export_print_pack

            folder = DATA / "exports" / valid_id(id) / EXPORT_VERSION / "print"
            with cad_lock:
                if not (folder / "complete.json").is_file():
                    packed = export_print_pack(value["document"], folder, asset_path)
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
        folder = DATA / "exports" / valid_id(id) / EXPORT_VERSION
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
                drawing = export_drawings(value["document"], parts, folder)
                portable = portable_document(value["document"])
                workflow = {
                    "revision_id": id,
                    "geometry_signature": value["geometry_signature"],
                    "requirements": value["requirements_state"],
                    "design_review": value["design_review_state"],
                    "motion": {"status": "not_configured"},
                }
                if value["requirements_state"]["status"] == "current":
                    workflow["panel_pack"] = export_panel_pack(
                        value["document"], folder
                    )
                if any(
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
