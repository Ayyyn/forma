from pathlib import Path
from typing import Literal
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import available, run_agent
from .geometry import Design, Requirements, dimensions, evaluate, export_fold, export_svg, mesh, validate_geometry
from .search import search

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Design Continuum / Discover", version="0.1.0")


class SearchRequest(BaseModel):
    requirements: Requirements = Field(default_factory=Requirements)
    count: int = Field(384, ge=16, le=512)
    seed: int = Field(27, ge=0, le=10000)


class InspectRequest(BaseModel):
    design: Design = Field(default_factory=Design)
    requirements: Requirements = Field(default_factory=Requirements)


class AgentRequest(BaseModel):
    brief: str = Field("Fit the pocket, preserve the deployed extent, and prefer fewer crease segments among feasible designs.", min_length=10, max_length=1400)
    requirements: Requirements = Field(default_factory=Requirements)
    provider: Literal["baseten", "meta"] = "baseten"
    mode: Literal["single_pass", "feedback"] = "single_pass"
    objective: Literal["creases", "material"] = "creases"
    seed: int = Field(101, ge=0, le=10000)


class ExportRequest(BaseModel):
    design: Design
    format: Literal["svg", "fold", "folded"] = "svg"


@app.get("/api/health")
def health():
    return {"status": "ok", "providers": available(), "version": "0.1.0", "physical_validation": "pending"}


@app.get("/api/defaults")
def defaults():
    return {"requirements": Requirements().model_dump(), "design": Design().model_dump(), "planning_mode": "single_pass", "planning_budget": 64}


@app.post("/api/search")
def explore(body: SearchRequest):
    result = search(body.requirements, body.count, body.seed)
    for candidate in [*result["candidates"], result["baseline"]]:
        candidate["preview"] = mesh(Design(**candidate["design"]), 40)
    return result


@app.post("/api/inspect")
def inspect(body: InspectRequest):
    design = body.design
    data = mesh(design, design.deployed_theta_deg)
    angles = np.linspace(design.deployed_theta_deg, design.packed_theta_deg, 81)
    return {"candidate": evaluate(design, body.requirements), "mesh": data,
            "frames": [{"vertices": mesh(design, float(angle))["vertices"], "theta_deg": float(angle),
                        "dimensions": dimensions(design, float(angle))} for angle in angles],
            "flat_mesh": mesh(design, 0), "validation": validate_geometry(design)}


@app.post("/api/agent")
def agent(body: AgentRequest):
    try:
        return run_agent(body.requirements, body.brief, body.provider, body.mode, body.objective, body.seed)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@app.get("/api/runs")
def runs():
    import json
    directory = ROOT / "artifacts" / "runs"
    paths = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
    return [{k: report.get(k) for k in ("run_id", "created_at_utc", "model", "mode", "status", "rationale", "tool_calls")}
            for report in (json.loads(path.read_text(encoding="utf-8")) for path in paths)]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    import re
    if not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise HTTPException(404)
    path = ROOT / "artifacts" / "runs" / (run_id + ".json")
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="application/json")


@app.post("/api/export")
def export(body: ExportRequest):
    import json
    if body.format == "svg":
        content, media, suffix = export_svg(body.design), "image/svg+xml", "svg"
    else:
        content, media, suffix = json.dumps(export_fold(body.design, body.format == "folded"), indent=2), "application/json", "fold"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="continuum-{body.design.family}.{suffix}"'})


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="studio")
