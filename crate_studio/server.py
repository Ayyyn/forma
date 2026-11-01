"""Local Forma application. Credentials stay server-side; revisions are immutable."""

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import uuid
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .engine import (
    DEFAULT_SPEC,
    DEFAULT_REQUIREMENTS,
    MATERIALS,
    evaluate,
    optimize,
    changes,
)
from .cad import build_parts, mesh_data, verify_geometry
from .exports import export_bundle, cut_list, drawing_svg
from . import agent

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "forma"
PROJECTS = DATA / "projects"
WEB = Path(__file__).parent / "web"
app = FastAPI(title="Forma Design Studio", docs_url=None, redoc_url=None)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)
cad_lock = threading.RLock()
project_lock = threading.RLock()
jobs = {}
job_lock = threading.Lock()
apply_lock = threading.Lock()


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method in ["POST", "PUT", "DELETE"]
        and origin
        and origin not in ["http://" + request.headers.get("host", "")]
    ):
        return JSONResponse({"detail": "Cross-origin writes are disabled"}, 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api") else "no-cache"
    )
    return response


@app.exception_handler(ValueError)
async def invalid(request, error):
    return JSONResponse({"detail": str(error)}, 422)


class DesignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: dict
    requirements: dict | None = None


class SaveBody(DesignBody):
    parent_id: str | None = None
    label: str = Field(default="Manual revision", max_length=120)
    source: str = "manual"


class AgentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    prompt: str = Field(min_length=1, max_length=6000)
    previous_job_id: str | None = None


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
        raise HTTPException(404, "Unknown revision")
    return value


@lru_cache(maxsize=80)
def geometry(encoded):
    spec = json.loads(encoded)
    with cad_lock:
        parts = build_parts(spec)
        verification = verify_geometry(spec, parts)
        meshes = mesh_data(parts)
    if not verification["passed"]:
        raise ValueError("Solid geometry verification failed")
    return {"parts": meshes}, verification, cut_list(spec, parts)


def snapshot(spec, requirements=None):
    result = evaluate(spec, requirements)
    g, v, rows = geometry(json.dumps(result["spec"], sort_keys=True))
    result.update(
        {
            "geometry": g,
            "geometry_verification": v,
            "cut_list": rows,
            "drawing_svg": drawing_svg(result["spec"]),
        }
    )
    result["checks"] += [
        {
            "id": "brep",
            "label": "Valid solid geometry",
            "status": "pass",
            "actual": v["part_count"],
            "limit": v["part_count"],
            "unit": "parts",
            "detail": "OpenCascade BREP validity, outside bounds, cavity intrusion and pairwise intersection checks.",
        }
    ]
    return result


def read_project(id):
    path = PROJECTS / (identifier(id) + ".json")
    if not path.exists():
        raise HTTPException(404, "Revision not found")
    record = json.loads(path.read_text(encoding="utf-8"))
    return {**snapshot(record["spec"], record["requirements"]), **record}


def summaries():
    if not PROJECTS.exists():
        return []
    result = []
    for path in PROJECTS.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        result.append(
            {
                k: record[k]
                for k in ["id", "parent_id", "label", "source", "created_at", "spec"]
            }
        )
    return sorted(result, key=lambda r: r["created_at"], reverse=True)


def save_project(
    spec,
    requirements=None,
    parent_id=None,
    label="Manual revision",
    source="manual",
    provenance=None,
):
    result = snapshot(spec, requirements)
    before = read_project(parent_id) if parent_id else {}
    record = {
        "id": "rev-" + uuid.uuid4().hex[:12],
        "parent_id": parent_id,
        "label": label,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "spec": result["spec"],
        "requirements": result["requirements"],
        "changes": changes(before, result),
        "provenance": provenance,
    }
    PROJECTS.mkdir(parents=True, exist_ok=True)
    with project_lock:
        path = PROJECTS / (record["id"] + ".json")
        path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
    return {**result, **record}


def initial():
    with project_lock:
        found = summaries()
        return (
            read_project(found[0]["id"])
            if found
            else save_project(
                DEFAULT_SPEC,
                DEFAULT_REQUIREMENTS,
                label="Initial design",
                source="template",
            )
        )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "application": "Forma",
        "cad_kernel": "OpenCascade / CadQuery",
        "model": agent.MODEL,
    }


@app.get("/api/bootstrap")
def bootstrap():
    return {
        "project": initial(),
        "projects": summaries(),
        "materials": list(MATERIALS.values()),
        "model": {
            "name": agent.MODEL,
            "configured": agent.configured(),
            "budget_usd_estimated": agent.CAP_USD,
            "spent_usd_estimated": agent.estimated_spend(),
            "billing_verified": False,
        },
        "examples": [
            {
                "label": "Lighter design",
                "prompt": "Find the lightest stock thickness in birch plywood. Preserve all internal dimensions and existing requirements.",
            },
            {
                "label": "Material revision",
                "prompt": "Switch to polypropylene at 8 mm. Keep all clear internal dimensions and existing requirements.",
            },
            {
                "label": "Inverse design",
                "prompt": "Use polypropylene. Resize as needed to provide at least 80 litres within the existing outside envelope. Find the lightest stock-size design.",
            },
            {
                "label": "Load screening",
                "prompt": "Keep birch plywood and all internal dimensions. Screen a uniformly distributed payload of 20 kg with floor deflection no more than 2 mm. Find the lightest stock thickness.",
            },
        ],
    }


@app.post("/api/design")
def design(body: DesignBody):
    return snapshot(body.spec, body.requirements)


@app.post("/api/optimize")
def optimize_design(body: DesignBody):
    return optimize(body.spec, body.requirements)


@app.get("/api/projects")
def projects():
    return summaries()


@app.post("/api/projects")
def create(body: SaveBody):
    if body.source not in ["manual", "import", "template"]:
        raise ValueError("Source must be manual, import or template")
    return save_project(
        body.spec, body.requirements, body.parent_id, body.label, body.source
    )


@app.get("/api/projects/{id}")
def project(id: str):
    return read_project(id)


@app.post("/api/agent", status_code=202)
def start_agent(body: AgentBody):
    project = read_project(body.project_id)
    if not agent.configured():
        raise HTTPException(503, "Meta API is not configured")
    with job_lock:
        if any(j["status"] in ["queued", "running"] for j in jobs.values()):
            raise HTTPException(409, "A design proposal is already running")
        prior = []
        if body.previous_job_id:
            previous = jobs.get(body.previous_job_id)
            if not previous or previous["project_id"] != body.project_id:
                raise HTTPException(
                    409, "The earlier proposal belongs to a different design or session"
                )
            if previous["status"] == "completed":
                prior = [*previous.get("context_instructions", []), previous["prompt"]][
                    -3:
                ]
        id = "job-" + uuid.uuid4().hex[:12]
        jobs[id] = {
            "id": id,
            "status": "queued",
            "stage": "Queued",
            "events": [],
            "project_id": body.project_id,
            "prompt": body.prompt,
            "context_instructions": prior,
        }

    def event(kind, message):
        with job_lock:
            jobs[id]["stage"] = message
            jobs[id]["events"].append({"kind": kind, "message": message})

    def work():
        try:
            with job_lock:
                jobs[id]["status"] = "running"
            proposal = agent.propose(
                project, body.prompt, event, run_id=id, context_instructions=prior
            )
            if proposal["status"] != "clarify":
                proposal["result"] = snapshot(
                    proposal["spec"], proposal["requirements"]
                )
            with job_lock:
                jobs[id].update(
                    status="completed",
                    stage=(
                        "Proposal ready"
                        if proposal["status"] == "ready"
                        else "Review required"
                    ),
                    proposal=proposal,
                )
        except Exception as error:
            with job_lock:
                jobs[id].update(
                    status="failed", stage="Unable to complete", error=str(error)
                )

    threading.Thread(target=work, daemon=True).start()
    return deepcopy(jobs[id])


@app.get("/api/jobs/{id}")
def job(id: str):
    with job_lock:
        if id not in jobs:
            raise HTTPException(404, "Proposal not found")
        return deepcopy(jobs[id])


@app.post("/api/proposals/{id}/apply")
def apply(id: str):
    with apply_lock:
        return apply_once(id)


def apply_once(id):
    with job_lock:
        if id not in jobs:
            raise HTTPException(404, "Proposal not found")
        j = deepcopy(jobs[id])
    p = j.get("proposal")
    if j["status"] != "completed" or not p or p["status"] != "ready":
        raise HTTPException(409, "Only a verified ready proposal can be applied")
    if j.get("applied_id"):
        return read_project(j["applied_id"])
    if not snapshot(p["spec"], p["requirements"])["passed"]:
        raise HTTPException(409, "Proposal no longer passes verification")
    # Applying is explicit and every proposal retains its own original parent.
    result = save_project(
        p["spec"],
        p["requirements"],
        j["project_id"],
        p["summary"][:120],
        "meta",
        {
            "model": p["model"],
            "run_id": p["run_id"],
            "response_ids": p["response_ids"],
            "prompt": j["prompt"],
            "context_instructions": j.get("context_instructions", []),
            "assumptions": p["assumptions"],
            "evidence": p["evidence"],
        },
    )
    with job_lock:
        jobs[id]["applied_id"] = result["id"]
    return result


FORMAT_MAP = {
    "bundle": "crate-bundle.zip",
    "step": "assembly.step",
    "stl": "assembly.stl",
    "svg": "drawing.svg",
    "pdf": "drawing.pdf",
    "csv": "cut-list.csv",
    "source": "parametric_model.py",
    "json": "project.json",
    "dxf": "panel-profiles.zip",
}


@app.get("/api/projects/{id}/export/{format}")
def export(id: str, format: str):
    p = read_project(id)
    if format not in FORMAT_MAP:
        raise HTTPException(404, "Unknown export format")
    revision = hashlib.sha256(
        b"".join(
            Path(__file__).with_name(name).read_bytes()
            for name in ["exports.py", "cad.py", "engine.py", "server.py"]
        )
    ).hexdigest()[:12]
    folder = DATA / "exports" / identifier(id) / revision
    with cad_lock:
        if not (folder / "complete.json").exists():
            manifest = export_bundle(p["spec"], folder)
            (folder / "project.json").write_text(
                json.dumps(
                    {k: v for k, v in p.items() if k != "geometry"},
                    indent=2,
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
            (folder / "design-checks.json").write_text(
                json.dumps(
                    {
                        "checks": p["checks"],
                        "metrics": p["metrics"],
                        "requirements": p["requirements"],
                        "notes": p["notes"],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with zipfile.ZipFile(
                folder / "panel-profiles.zip", "w", zipfile.ZIP_DEFLATED
            ) as z:
                for f in folder.glob("panel-*.dxf"):
                    z.write(f, f.name)
            # Repackage the complete reproducible design with its retained requirements.
            files = [
                f
                for f in folder.iterdir()
                if f.is_file() and f.name not in ["crate-bundle.zip", "complete.json"]
            ]
            hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
            (folder / "sha256.json").write_text(
                json.dumps(hashes, indent=2), encoding="utf-8"
            )
            with zipfile.ZipFile(
                folder / "crate-bundle.zip", "w", zipfile.ZIP_DEFLATED
            ) as z:
                for f in files + [folder / "sha256.json"]:
                    z.write(f, f.name)
            (folder / "complete.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
    path = folder / FORMAT_MAP[format]
    types = {
        "svg": "image/svg+xml",
        "pdf": "application/pdf",
        "json": "application/json",
        "csv": "text/csv",
    }
    return FileResponse(
        path,
        media_type=types.get(format),
        filename=None if format == "svg" else path.name,
    )


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


app.mount("/assets", StaticFiles(directory=WEB), name="assets")

from .workspace_server import create_router

app.include_router(create_router(cad_lock, read_project))


@app.get("/studio")
def studio_home():
    return FileResponse(WEB / "studio.html")


@app.get("/evaluation")
def evaluation_home():
    path = DATA / "evaluation" / "review.html"
    if not path.is_file():
        raise HTTPException(404, "Evaluation report has not been generated")
    return FileResponse(path)


@app.get("/evaluation-evidence")
def evaluation_evidence():
    path = DATA / "evaluation" / "evidence.zip"
    if not path.is_file():
        raise HTTPException(404, "Evaluation evidence has not been packaged")
    return FileResponse(path, filename="forma-evaluation-evidence.zip")


@app.get("/performance")
def performance_home():
    path = DATA / "evaluation" / "performance" / "review.html"
    if not path.is_file():
        raise HTTPException(404, "Performance review has not been generated")
    return FileResponse(path)


@app.get("/performance-evidence")
def performance_evidence():
    path = DATA / "evaluation" / "performance" / "evidence.zip"
    if not path.is_file():
        raise HTTPException(404, "Performance evidence has not been generated")
    return FileResponse(path, filename="forma-performance-evidence.zip")


@app.get("/demo-package")
def demo_package():
    path = DATA / "demo-v1" / "instrument-case-package.zip"
    if not path.is_file():
        raise HTTPException(404, "Demo package has not been generated")
    return FileResponse(path, filename="forma-instrument-case.zip")
