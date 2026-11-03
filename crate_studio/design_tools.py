"""Revision-bound engineering tools for a Muse design session.

Candidates are private previews. Tools never change the saved user document.
"""

from contextlib import nullcontext
from copy import deepcopy
import hashlib
from importlib.metadata import version as package_version
import json
from pathlib import Path
import time

from . import workspace_agent as wa
from .workspace_cache import asset_identity, cached_build, VERSION
from .workspace_geometry import _bounds, export_document
from .workspace_workflow import geometry_signature

TOOL_VERSION = hashlib.sha256(
    (VERSION + wa.MODEL).encode()
    + b"".join(
        Path(__file__).with_name(name).read_bytes()
        for name in (
            "design_tools.py",
            "mechanism_study.py",
            "motion_cache.py",
            "native_study.py",
            "motion_probe.py",
            "component_exports.py",
            "floor_check.py",
            "workspace_agent.py",
            "workspace_drawing.py",
            "workspace_workflow.py",
        )
    )
    + Path(__file__).with_name("web").joinpath("vendor", "FormaSans.ttf").read_bytes()
    + json.dumps(
        {
            name: package_version(name)
            for name in (
                "cadquery",
                "cadquery-ocp",
                "trimesh",
                "numpy",
                "shapely",
                "reportlab",
                "ezdxf",
            )
        },
        sort_keys=True,
    ).encode()
).hexdigest()


def review_identity(document, asset_loader=None):
    metadata = document.get("metadata", {})
    source = {key: value for key, value in document.items() if key != "metadata"}
    source.setdefault("annotations", [])
    source.setdefault("display", {})
    source["metadata"] = {
        key: value
        for key, value in metadata.items()
        if key not in ("design_review", "native_study_review")
    }
    source = deepcopy(source)
    from .folding import specification as fold_specification

    for feature in source.get("features", []):
        if feature.get("type") == "folding_assembly":
            feature["params"] = fold_specification(feature.get("params", {}))

    def canonical(value):
        if isinstance(value, dict):
            return {key: canonical(item) for key, item in value.items()}
        if isinstance(value, list):
            return [canonical(item) for item in value]
        if type(value) in (int, float):
            return float(value)
        return value

    return hashlib.sha256(
        json.dumps(
            [TOOL_VERSION, canonical(source), asset_identity(document, asset_loader)],
            sort_keys=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def review_state(document, asset_loader=None):
    review = document.get("metadata", {}).get("design_review")
    if not isinstance(review, dict):
        return {"status": "unbound"}
    current = review.get("source_identity") == review_identity(document, asset_loader)
    return {
        "status": "current" if current else "stale",
        "geometry_only": True,
        "physical_validation": False,
        "detail": (
            "Recorded geometry/tool review matches this source and tool version; physical qualification is separate."
            if current
            else "Source, imported assets or verification tools changed; rerun the affected design checks."
        ),
    }


def _object(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


_STRING = {"type": "string"}
_CID = {"candidate_id": _STRING}


def report_key(name, arguments):
    if name == "check_floor":
        state = arguments.get("state_name")
        return "floor:static" if state is None else "floor:state:" + str(state)
    if name == "render_state":
        return "visual:state:" + str(arguments.get("state_name"))
    return {
        "check_interference": "interference",
        "check_motion": "motion",
        "check_folding": "motion",
        "render_views": "visual",
        "verify_exports": "exports",
    }.get(name)


def tool_definitions():
    rows = [
        (
            "probe_prismatic_pair",
            "Probe six directions of one actual parent/child prismatic interface in one named state, isolating it from unrelated corners. Batches both axial signs and four orthogonal transverse probes. Useful for guide diagnostics; blockage alone is not proof of manufactured guidance, global captivity or locks. Use at separated and compact states, alongside whole-assembly interference/motion.",
            _object(
                {
                    **_CID,
                    "mechanism_spec": {"type": "object"},
                    "joint_id": _STRING,
                    "state_name": _STRING,
                    "max_distance_mm": {"type": "number"},
                    "samples": {"type": "integer"},
                }
            ),
        ),
        (
            "probe_translation",
            "Release virtual constraints and probe an unwanted rigid translation of selected bodies against the others. Useful for finding missing real guide/retention geometry. Direction is WORLD coordinates; use several directions and named sizes. An obstruction is NOT proof of captivity or a working lock. Returns exact native sampled intersections and their bounds.",
            _object(
                {
                    **_CID,
                    "moving_part_ids": {"type": "array", "items": _STRING},
                    "direction": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                    "max_distance_mm": {"type": "number"},
                    "samples": {"type": "integer"},
                    "mechanism_spec": {"type": ["object", "null"]},
                    "state_name": {"type": ["string", "null"]},
                }
            ),
        ),
        (
            "render_state",
            "Render actual native solids in one named mechanism state, with exact outer bounds. Review compactness, protrusions and seams in every named state, not just the construction pose. This does not qualify physical guides or locks.",
            _object(
                {**_CID, "mechanism_spec": {"type": "object"}, "state_name": _STRING}
            ),
        ),
        (
            "check_floor",
            "Check actual horizontal floor/support coverage, including gaps and holes, in one declared current or named mechanism state. Returns a diagnostic image. This measures projection in a declared Z band, not floor strength, flatness, locks or retained engagement. Use mechanism_spec=null,state_name=null for static CAD.",
            _object(
                {
                    **_CID,
                    "footprint": _object(
                        {
                            "center_xy": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "size_mm": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "z_range_mm": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                        }
                    ),
                    "mechanism_spec": {"type": ["object", "null"]},
                    "state_name": {"type": ["string", "null"]},
                }
            ),
        ),
        (
            "record_strategy",
            "Record a concise design strategy before CAD: compare alternatives, select one, list assumptions and a small-step implementation plan. This records model decisions, not verified engineering results.",
            _object(
                {
                    "alternatives": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": _object(
                            {"name": _STRING, "benefit": _STRING, "risk": _STRING}
                        ),
                    },
                    "selected": {
                        "type": "string",
                        "description": "Copy the exact name of ONE alternative above; do not put a prose explanation here.",
                    },
                    "assumptions": {"type": "array", "items": _STRING, "maxItems": 12},
                    "steps": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 8,
                        "items": _STRING,
                    },
                }
            ),
        ),
        (
            "inspect_project",
            "Inspect a candidate's full editable source, native part dimensions and geometry diagnostics. Use candidate_id=base for the original project.",
            _object(_CID),
        ),
        (
            "feature_reference",
            "Get exact Studio feature/operation conventions and supported parameters. No executable code or invented operations are accepted.",
            _object({}),
        ),
        (
            "draft_candidate",
            "Build and validate a complete feature plan against an existing candidate. Branch alternatives or revise a failed candidate. Original instruction quotes are required. Saved projects remain unchanged.",
            _object({"base_candidate_id": _STRING, "plan": {"type": "object"}}),
        ),
        (
            "inspect_topology",
            "Get native faces/edges for one part, including actual ordinals for face edits and measurement.",
            _object({**_CID, "part_id": _STRING}),
        ),
        (
            "measure_parts",
            "Compute exact native distance between two bodies and their dimensions/volumes. Positive distance is clearance; zero can mean contact or interference, so use check_interference too.",
            _object({**_CID, "part_a": _STRING, "part_b": _STRING}),
        ),
        (
            "check_interference",
            "Check every independent body pair for positive-volume native intersection. No exclusions and no automatic treatment of overlaps as intended joints.",
            _object(_CID),
        ),
        (
            "check_motion",
            "Test a model-declared general mechanism path on real solids. Root-first fixed/revolute/prismatic tree, optional loop constraints, 2..12 named states. Virtual joints do NOT verify hardware, locks, engagement or loads. Get schema from mechanism_reference.",
            _object({**_CID, "spec": {"type": "object"}}),
        ),
        (
            "mechanism_reference",
            "Read schema/conventions and limitations for a general rigid-body motion study.",
            _object({}),
        ),
        (
            "check_folding",
            "Run the existing supported folding feature's actual native-solid sampled motion check. Only for one unmodified folding_assembly; never silently substitute it for another mechanism.",
            _object(
                {
                    **_CID,
                    "max_angle_deg": {"type": "number"},
                    "samples": {"type": "integer", "minimum": 3, "maximum": 361},
                }
            ),
        ),
        (
            "render_views",
            "Render four consistent views of actual candidate mesh for visual review. The resulting image is provided to you. A render is not physical verification.",
            _object(_CID),
        ),
        (
            "verify_exports",
            "Generate native STEP/STL/source and drawings, independently reopen solids/mesh and report exact checks and file hashes. Outputs remain local until user applies/exports.",
            _object(_CID),
        ),
        (
            "finish_design",
            "Select an existing candidate for user review. Geometry, interference, exports and visual inspection must have passed. State assumptions, considered alternatives, remaining problems and concrete visual observations. This never certifies a physical mechanism or automatically applies it.",
            _object(
                {
                    **_CID,
                    "summary": _STRING,
                    "alternatives": {
                        "type": "array",
                        "items": _STRING,
                        "minItems": 1,
                        "maxItems": 6,
                    },
                    "assumptions": {"type": "array", "items": _STRING, "maxItems": 20},
                    "unresolved": {"type": "array", "items": _STRING, "maxItems": 20},
                    "visual_review": _STRING,
                }
            ),
        ),
    ]
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description + (
                    " Send mechanism_spec:{} to reuse this exact candidate's latest recorded check_motion spec; unavailable on a new/changed candidate until checked. This avoids repeating the complete mechanism in every diagnostic. Explicit specs remain supported."
                    if "mechanism_spec" in schema.get("properties", {}) else ""
                ),
                "parameters": schema,
            },
        }
        for name, description, schema in rows
    ]


MECHANISM_REFERENCE = {
    "schema": {
        "root": "existing body ID",
        "joints": [
            {
                "id": "slide",
                "parent": "body_001",
                "child": "body_002",
                "type": "fixed|revolute|prismatic",
                "axis": [1, 0, 0],
                "origin": [0, 0, 0],
                "limits": [0, 10],
            }
        ],
        "states": [
            {"name": "small", "values": {"slide": 0}},
            {"name": "large", "values": {"slide": 10}},
        ],
        "connections": [],
        "samples_per_segment": 13,
    },
    "limits": "2..12 unique named states, every joint value explicit; root-first tree spans every body; <=24 bodies, <=361 total samples. Axis/origin/connection anchors are in each body's ORIGINAL WORLD coordinate frame, not its bounding-box center. A child pose is parent_pose * joint_motion; zero joint values reproduce original CAD. Revolute degrees; prismatic mm; fixed limits/value must be zero.",
    "loop_connections": "Optional {type:point,a:body_id,b:body_id,anchor_a:[x,y,z],anchor_b:[x,y,z]}; axis adds axis_a:[x,y,z],axis_b:[x,y,z]. Positions must agree and axes must be parallel at ALL samples. No numerical loop solver; propose compatible joint values/geometry and inspect failures.",
    "qualification": "Finite-volume interference and declared kinematic closure only. No physical bearing, telescopic engagement, floor coverage, holding/locking, actuation force, strength, material or fatigue qualification. These remain unresolved unless separately verified. Do not describe a virtual joint as manufactured hardware.",
}


class DesignSession:
    def __init__(
        self, document, instruction, folder, asset_loader=None, geometry_lock=None
    ):
        self.instruction = instruction
        self.folder = Path(folder)
        self.asset_loader = asset_loader
        self.geometry_lock = geometry_lock
        self.candidates = {
            "base": {
                "document": deepcopy(document),
                "changes": [],
                "summary": "Original project",
                "evidence": [],
            }
        }
        self.cache = {}
        self.cached_reports = {}
        self.asset_keys = {}
        self.reports = {}
        self.events = []
        self.finished = None
        self.strategy = None
        self.native_interference = {}

    def _candidate(self, ident):
        if not isinstance(ident, str) or ident not in self.candidates:
            raise ValueError(
                "Unknown candidate ID; use base or a returned candidate_id"
            )
        return self.candidates[ident]

    def _build(self, ident):
        return cached_build(self._candidate(ident)["document"], self.asset_loader)

    def _metrics(self, built):
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "bounds_mm": _bounds(p["shape"]),
                "volume_mm3": float(p["shape"].Volume()),
                "valid": p["shape"].isValid(),
            }
            for p in built["parts"]
        ]

    def call(self, name, arguments):
        start = time.perf_counter()
        hit = False
        requested_arguments = deepcopy(arguments)
        try:
            definitions = {
                x["function"]["name"]: x["function"]["parameters"]
                for x in tool_definitions()
            }
            schema = definitions.get(name)
            if (
                schema is None
                or not isinstance(arguments, dict)
                or set(arguments) != set(schema["required"])
            ):
                raise ValueError("Unknown tool or unexpected/missing arguments")
            # Identity includes current imported bytes and all candidate source;
            # no tool results are reused on changed imported assets.
            referenced = arguments.get(
                "candidate_id", arguments.get("base_candidate_id")
            )
            assets = (
                asset_identity(
                    self._candidate(referenced)["document"], self.asset_loader
                )
                if referenced is not None
                else []
            )
            if referenced is not None:
                if (
                    referenced in self.asset_keys
                    and self.asset_keys[referenced] != assets
                ):
                    self.reports.pop(referenced, None)
                self.asset_keys[referenced] = deepcopy(assets)
            if arguments.get("mechanism_spec") == {}:
                recorded = self.reports.get(referenced, {}).get("motion", {}).get("spec")
                if recorded is None:
                    raise ValueError("Run check_motion on this exact candidate before using mechanism_spec:{}")
                arguments = {**arguments, "mechanism_spec": deepcopy(recorded)}
            key = hashlib.sha256(
                json.dumps(
                    [TOOL_VERSION, name, arguments, assets],
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            if key in self.cache:
                hit = True
                result = deepcopy(self.cache[key])
                key_for_report = report_key(name, arguments)
                if key_for_report:
                    self.reports.setdefault(referenced, {})[key_for_report] = deepcopy(
                        self.cached_reports[key]
                    )
            else:
                key_for_report = report_key(name, arguments)
                if key_for_report:
                    self.reports.setdefault(referenced, {}).pop(key_for_report, None)
                with (
                    self.geometry_lock
                    if self.geometry_lock is not None
                    else nullcontext()
                ):
                    result = self._dispatch(name, arguments)
                if name not in ("finish_design", "record_strategy"):
                    self.cache[key] = deepcopy(result)
                    key_for_report = report_key(name, arguments)
                    if key_for_report:
                        self.cached_reports[key] = deepcopy(
                            self.reports[referenced][key_for_report]
                        )
            result = {"ok": True, **result}
        except Exception as exc:
            # Native OCCT exceptions are not consistently ValueError/RuntimeError.
            # Return a failed tool result instead of terminating the agent job.
            result = {
                "ok": False,
                "error": f"{type(exc).__name__}: {str(exc)[:1200]}",
                "instruction": "Correct the arguments/design or report unsupported work; do not relax the user's requirements.",
            }
        event = {
            "tool": name,
            "arguments": requested_arguments,
            "resolved_arguments": deepcopy(arguments),
            "result": deepcopy(result),
            "cache_hit": hit,
            "elapsed_s": time.perf_counter() - start,
        }
        self.events.append(event)
        return result

    def _dispatch(self, name, a):
        if name == "record_strategy":
            options = a["alternatives"]
            if (
                not isinstance(options, list)
                or not 1 <= len(options) <= 4
                or any(
                    not isinstance(x, dict)
                    or set(x) != {"name", "benefit", "risk"}
                    or any(
                        not isinstance(v, str) or not 0 < len(v) <= 1000
                        for v in x.values()
                    )
                    for x in options
                )
            ):
                raise ValueError(
                    "Supply one to four concrete alternatives with name/benefit/risk"
                )
            if a["selected"] not in [x["name"] for x in options]:
                raise ValueError("Selected strategy must name one alternative")
            for key in ("assumptions", "steps"):
                if (
                    not isinstance(a[key], list)
                    or len(a[key]) > 12
                    or any(
                        not isinstance(x, str) or not 0 < len(x) <= 1000 for x in a[key]
                    )
                ):
                    raise ValueError("Invalid bounded strategy list")
            if not 2 <= len(a["steps"]) <= 8:
                raise ValueError(
                    "List two to eight incremental implementation/check steps"
                )
            self.strategy = deepcopy(a)
            self._write_json("strategy", "decision.json", a)
            return {
                "recorded": True,
                "strategy": a,
                "next_step": "Implement only the first manageable geometry step now, then inspect its result before later steps. Keep the full requirements.",
            }
        if name == "feature_reference":
            return {
                "reference": wa.MECHANICAL_SYSTEM,
                "feature_parameters": {
                    key: sorted(value) for key, value in wa.PARAMS.items()
                },
                "missing_tools": [
                    "arbitrary sketch constraint solver",
                    "force/friction/fatigue solver",
                    "physical print test",
                    "general web browser",
                    "arbitrary Python execution",
                ],
            }
        if name == "mechanism_reference":
            return deepcopy(MECHANISM_REFERENCE)
        if name == "draft_candidate":
            if len(self.candidates) >= 13:
                raise ValueError("Session supports at most twelve trial candidates")
            base = self._candidate(a["base_candidate_id"])
            proposal = wa.apply_plan(
                base["document"], a["plan"], self.instruction, self.asset_loader
            )
            ident = (
                "candidate-"
                + hashlib.sha256(
                    json.dumps(
                        proposal["document"], sort_keys=True, allow_nan=False
                    ).encode()
                ).hexdigest()[:16]
            )
            self.candidates[ident] = {
                **proposal,
                "changes": base["changes"] + proposal["changes"],
            }
            built = self._build(ident)
            screen = {
                "checked": False,
                "scope": "Explicit check_interference required for larger candidates",
            }
            if built["checks"]["passed"] and len(built["parts"]) <= 24:
                from .folding import collisions

                screen = collisions(built["parts"], details=True)
                screen.update(
                    checked=True,
                    passed=not screen["overlaps"],
                    scope="Default source pose only; shared with explicit interference check. Fix default-pose overlap before an expensive motion sweep.",
                )
                self.reports.setdefault(ident, {})["interference"] = deepcopy(screen)
                self.native_interference[ident] = {
                    "assets": asset_identity(proposal["document"], self.asset_loader),
                    "result": deepcopy(screen),
                }
            return {
                "candidate_id": ident,
                "status": proposal["status"],
                "result": proposal["result"],
                "parts": self._metrics(built),
                "interference_screen": screen,
                "note": "Trial geometry only; not an applied project or a verified physical mechanism",
            }
        ident = a["candidate_id"]
        candidate = self._candidate(ident)
        doc = candidate["document"]
        built = self._build(ident)
        reports = self.reports.setdefault(ident, {})
        if name == "inspect_project":
            return {
                "candidate_id": ident,
                "geometry_signature": geometry_signature(doc),
                "document": wa._model_document(doc),
                "geometry": wa._public_result(built),
                "parts": self._metrics(built),
            }
        if name == "inspect_topology":
            if a["part_id"] not in {p["id"] for p in built["parts"]}:
                raise ValueError("Unknown part ID")
            return {
                "faces": [
                    {k: v for k, v in f.items() if k not in ("vertices", "triangles")}
                    for f in built["face_meshes"]
                    if f["part_id"] == a["part_id"]
                ],
                "edges": [
                    {k: v for k, v in f.items() if k != "polyline_points"}
                    for f in built["edge_meta"]
                    if f["part_id"] == a["part_id"]
                ],
            }
        if name == "measure_parts":
            parts = {p["id"]: p["shape"] for p in built["parts"]}
            if (
                a["part_a"] not in parts
                or a["part_b"] not in parts
                or a["part_a"] == a["part_b"]
            ):
                raise ValueError("Select two different existing bodies")
            return {
                "distance_mm": float(parts[a["part_a"]].distance(parts[a["part_b"]])),
                "parts": [
                    p
                    for p in self._metrics(built)
                    if p["id"] in (a["part_a"], a["part_b"])
                ],
            }
        if not built["checks"]["passed"]:
            raise ValueError(
                "Candidate geometry failed; revise it before qualification"
            )
        if name == "check_interference":
            from .folding import collisions

            cached = self.native_interference.get(ident)
            if cached and cached["assets"] == asset_identity(doc, self.asset_loader):
                reports["interference"] = deepcopy(cached["result"])
                return {**reports["interference"], "native_work_reused": True}
            value = collisions(built["parts"], details=True)
            reports["interference"] = {**value, "passed": not value["overlaps"]}
            self.native_interference[ident] = {
                "assets": asset_identity(doc, self.asset_loader),
                "result": deepcopy(reports["interference"]),
            }
            return reports["interference"]
        if name == "check_floor":
            from .floor_check import floor_coverage, render_coverage
            from .mechanism_study import validate_spec, pose_matrices, moved_parts

            parts = built["parts"]
            spec = None
            if a["mechanism_spec"] is not None:
                spec = validate_spec(a["mechanism_spec"], [p["id"] for p in parts])
                matches = [s for s in spec["states"] if s["name"] == a["state_name"]]
                if not matches:
                    raise ValueError("Choose an existing named mechanism state")
                parts = moved_parts(parts, pose_matrices(spec, matches[0]["values"]))
            elif a["state_name"] is not None:
                raise ValueError("A named state requires its complete mechanism_spec")
            value, target, support, missing = floor_coverage(parts, a["footprint"])
            value.update(
                geometry_signature=geometry_signature(doc),
                mechanism_spec=spec,
                state_name=a["state_name"],
            )
            folder = self.folder / ident
            folder.mkdir(parents=True, exist_ok=True)
            stem = (
                "floor-"
                + hashlib.sha256(
                    json.dumps(a, sort_keys=True, allow_nan=False).encode()
                ).hexdigest()[:12]
            )
            image_path = folder / (stem + ".png")
            render_coverage(
                target,
                support,
                missing,
                image_path,
                "Support coverage · " + str(a["state_name"] or "current pose"),
            )
            value["image_artifact"] = f"{ident}/{stem}.png"
            value["image_sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
            reports[report_key(name, a)] = value
            self._write_json(ident, stem + ".json", value)
            return value
        if name in ("check_motion", "check_folding"):
            if reports.get("interference", {}).get("passed") is False:
                raise ValueError(
                    "Default source pose has interference; fix the draft's interference_screen before running a motion sweep"
                )
            if name == "check_motion":
                from .mechanism_study import mechanism_study

                value = mechanism_study(doc, built, a["spec"])
            else:
                from .folding_study import folding_study

                value = folding_study(
                    doc,
                    {
                        "family": "panel_hinges",
                        "max_angle_deg": a["max_angle_deg"],
                        "samples": a["samples"],
                    },
                )
            reports["motion"] = value
            self._write_json(ident, "motion.json", value)
            return {
                k: v for k, v in value.items() if k not in ("parts", "frames", "graph")
            } | {
                "failed_frames": [
                    f
                    for f in value["frames"]
                    if f.get("overlaps")
                    or f.get("loop_position_error_mm", 0) > 1e-6
                    or f.get("loop_axis_error_deg", 0) > 1e-5
                ][:4],
                "evidence": f"{ident}/motion.json",
            }
        if name == "render_views":
            return self._render(ident, built)
        if name == "probe_translation":
            from .motion_probe import translation_probe

            value = translation_probe(
                built["parts"],
                a["moving_part_ids"],
                a["direction"],
                a["max_distance_mm"],
                a["samples"],
                a["mechanism_spec"],
                a["state_name"],
            )
            stem = (
                "probe-"
                + hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()[
                    :12
                ]
            )
            self._write_json(ident, stem + ".json", value)
            return {**value, "evidence": ident + "/" + stem + ".json"}
        if name == "probe_prismatic_pair":
            from .motion_probe import prismatic_pair_probe

            value = prismatic_pair_probe(
                built["parts"],
                a["mechanism_spec"],
                a["joint_id"],
                a["state_name"],
                a["max_distance_mm"],
                a["samples"],
            )
            stem = (
                "pair-probe-"
                + hashlib.sha256(json.dumps(a, sort_keys=True).encode()).hexdigest()[
                    :12
                ]
            )
            self._write_json(ident, stem + ".json", value)
            return {**value, "evidence": ident + "/" + stem + ".json"}
        if name == "render_state":
            from .mechanism_study import validate_spec, pose_matrices, moved_parts
            from .workspace_geometry import _mesh
            import cadquery as cq

            spec = validate_spec(a["mechanism_spec"], [p["id"] for p in built["parts"]])
            selected = [
                state for state in spec["states"] if state["name"] == a["state_name"]
            ]
            if not selected:
                raise ValueError("Choose an existing named mechanism state")
            parts = moved_parts(
                built["parts"], pose_matrices(spec, selected[0]["values"])
            )
            bounds = _bounds(cq.Compound.makeCompound([p["shape"] for p in parts]))
            metrics = {
                "bounds_mm": bounds,
                "size_mm": [bounds[1][i] - bounds[0][i] for i in range(3)],
                "solid_count": len(parts),
                "volume_mm3": sum(p["shape"].Volume() for p in parts),
            }
            posed = {
                "mesh": [{"id": p["id"], **_mesh(p["shape"])} for p in parts],
                "metrics": metrics,
            }
            stem = (
                "state-"
                + hashlib.sha256(
                    json.dumps([spec, a["state_name"]], sort_keys=True).encode()
                ).hexdigest()[:12]
            )
            key = report_key(name, a)
            result = self._render(
                ident,
                posed,
                stem=stem,
                report_name=key,
                heading="Named state · " + a["state_name"],
            )
            result.update(
                state_name=a["state_name"],
                metrics=metrics,
                mechanism_spec=spec,
                visual_report_key=key,
            )
            reports[key] = result
            return result
        if name == "verify_exports":
            from .workspace_drawing import export_drawings
            from .component_exports import export_components

            folder = self.folder / ident / "exports"
            value = export_document(doc, self.asset_loader, folder)
            try:
                components = export_components(built, folder)
            except ValueError as error:
                path = folder / "components.json"
                components = (
                    json.loads(path.read_text(encoding="utf-8"))
                    if path.is_file()
                    else {"passed": False, "error": str(error)}
                )
                # A previous artifact must never turn a fresh exporter error
                # into success. Preserve diagnostics with an explicit failure.
                components.update(passed=False, error=str(error))
            value["checks"]["components"] = components
            value["checks"]["passed"] = (
                value["checks"]["passed"] and components["passed"]
            )
            if value["checks"]["passed"]:
                export_drawings(doc, built["parts"], folder)
            files = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in folder.iterdir()
                if p.is_file()
            }
            reports["exports"] = {
                "passed": value["checks"]["passed"],
                "checks": value["checks"],
                "sha256": files,
                "scope": "STEP/STL native/mesh read-back checks; deterministic drawings generated from the same native solids. Drawing visual approval and physical suitability are separate.",
            }
            return reports["exports"]
        if name == "finish_design":
            if ident == "base" or candidate.get("status") != "ready":
                raise ValueError("Select a ready trial candidate")
            for gate in ("interference", "exports", "visual"):
                if not reports.get(gate, {}).get("passed"):
                    raise ValueError(
                        f"Run and pass {gate} before selecting this candidate"
                    )
            if "motion" in reports and not reports["motion"]["passed"]:
                raise ValueError("Selected candidate has a failed motion study")
            for key, value in reports.items():
                if not key.startswith("floor:"):
                    continue
                if not value["passed"]:
                    raise ValueError(
                        "Selected candidate has a failed floor coverage check"
                    )
                if value["mechanism_spec"] is not None:
                    if "motion" not in reports or "spec" not in reports["motion"]:
                        raise ValueError(
                            "Named-state floor coverage requires a passing general motion study"
                        )
                    without_samples = lambda spec: {
                        k: v for k, v in spec.items() if k != "samples_per_segment"
                    }
                    if without_samples(value["mechanism_spec"]) != without_samples(
                        reports["motion"]["spec"]
                    ):
                        raise ValueError(
                            "Floor coverage and motion use different mechanism definitions"
                        )
            if any(key.startswith("floor:state:") for key in reports):
                missing = [
                    state["name"]
                    for state in reports["motion"]["spec"]["states"]
                    if "floor:state:" + state["name"] not in reports
                ]
                if missing:
                    raise ValueError(
                        "Missing floor coverage for mechanism states: "
                        + ", ".join(missing)
                    )
                for state in reports["motion"]["spec"]["states"]:
                    view = reports.get("visual:state:" + state["name"], {})
                    if not view.get("passed"):
                        raise ValueError(
                            "Render and review the actual named state before selecting: "
                            + state["name"]
                        )
                    if without_samples(view["mechanism_spec"]) != without_samples(
                        reports["motion"]["spec"]
                    ):
                        raise ValueError(
                            "Named-state visual review uses a different mechanism definition"
                        )
            for key in ("summary", "visual_review"):
                if not isinstance(a[key], str) or not 10 <= len(a[key]) <= 3000:
                    raise ValueError(f"{key} requires a concrete bounded explanation")
            for key in ("alternatives", "assumptions", "unresolved"):
                if (
                    not isinstance(a[key], list)
                    or len(a[key]) > 20
                    or any(
                        not isinstance(x, str) or not 0 < len(x) <= 1200 for x in a[key]
                    )
                ):
                    raise ValueError("Invalid design review list")
            if not a["alternatives"]:
                raise ValueError("Record at least one considered alternative/trade-off")
            review = {
                key: deepcopy(a[key])
                for key in (
                    "alternatives",
                    "assumptions",
                    "unresolved",
                    "visual_review",
                )
            }
            review.update(
                geometry_signature=geometry_signature(doc),
                geometry_only=True,
                physical_validation=False,
                locking_verified=False,
                reports=deepcopy(reports),
                strategy=deepcopy(self.strategy),
            )
            # Keep large per-pose matrices in evidence, not every subsequent prompt.
            if "motion" in review["reports"]:
                review["reports"]["motion"] = {
                    k: v
                    for k, v in review["reports"]["motion"].items()
                    if k not in ("frames", "parts", "graph")
                }
            chosen = deepcopy(candidate)
            chosen["summary"] = a["summary"]
            chosen["design_review"] = review
            chosen["document"].setdefault("metadata", {})["design_review"] = review
            if "motion" in reports and "spec" in reports["motion"]:
                chosen["document"]["metadata"]["design_mechanism"] = reports["motion"][
                    "spec"
                ]
            review["source_identity"] = review_identity(
                chosen["document"], self.asset_loader
            )
            self.finished = chosen
            return {
                "selected": ident,
                "status": "geometry_proposal_for_review",
                "physical_validation": False,
            }
        raise ValueError("Tool has no implementation")

    def _write_json(self, ident, filename, value):
        folder = self.folder / ident
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_text(
            json.dumps(value, indent=2, allow_nan=False), encoding="utf-8"
        )

    def acknowledge_views(self, ident, report_name="visual"):
        """Driver calls only after a successful model request containing this image."""
        self.reports[ident][report_name].update(
            passed=True, image_delivered_to_model=True
        )

    def _render(
        self,
        ident,
        built,
        stem="views",
        report_name="visual",
        heading="Native CAD review · dimensions in mm",
    ):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        folder = self.folder / ident
        folder.mkdir(parents=True, exist_ok=True)
        fig = plt.figure(figsize=(8, 6), facecolor="#f7f5f0")
        bounds = np.array(built["metrics"]["bounds_mm"])
        center, half = bounds.mean(axis=0), max(np.ptp(bounds, axis=0)) * 0.6
        colors = ("#8babb6", "#cfad7d", "#98b79a", "#b19bb8")
        for i, (elev, azim, title) in enumerate(
            (
                (28, -55, "Perspective"),
                (90, -90, "Top"),
                (0, -90, "Front"),
                (0, 0, "Right"),
            )
        ):
            ax = fig.add_subplot(2, 2, i + 1, projection="3d", computed_zorder=False)
            ax.set_facecolor("#f7f5f0")
            all_faces, face_colors = [], []
            for j, mesh in enumerate(built["mesh"]):
                vertices = np.array(mesh["vertices"]).reshape(-1, 3)
                faces = np.array(mesh["triangles"]).reshape(-1, 3)
                all_faces.extend(vertices[faces])
                face_colors.extend([colors[j % len(colors)]] * len(faces))
            # Sort all faces together. Drawing one opaque collection per body
            # in source order can paint a rear floor over a nearer wall/pin.
            ax.add_collection3d(
                Poly3DCollection(
                    all_faces, facecolors=face_colors, zsort="average",
                    edgecolor="#4b5a60", linewidth=0.15, alpha=1,
                )
            )
            for setter, value in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center):
                setter(value - half, value + half)
            ax.set_box_aspect((1, 1, 1))
            ax.view_init(elev=elev, azim=azim)
            ax.set_axis_off()
            ax.set_title(title, fontsize=10)
        fig.suptitle(heading, fontsize=12)
        path = folder / (stem + ".png")
        fig.savefig(path, dpi=95, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        report = {
            "passed": False,
            "rendered": True,
            "artifact": f"{ident}/{stem}.png",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "image_delivered_to_model": False,
            "scope": "Image generated; driver must deliver it to the model before final selection. Delivery and written review are not automatic aesthetic approval.",
        }
        self.reports.setdefault(ident, {})[report_name] = report
        return report
