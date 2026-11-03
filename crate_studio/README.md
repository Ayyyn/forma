# Forma

The feature-based CAD editor is available at `/studio`. See `docs/FORMA_STUDIO.md` for its human/AI editing, import, assembly and drawing workflows and scope.

Studio reuses exact validated proposals and shares CAD builds with the AI path.
`New proposal` requests fresh generation. Provider cached-input pricing is now
accounted for in new receipts; prior budget reservations are preserved. See
`docs/FORMA_PERFORMANCE.md` for measurements, quality gates and limitations.

Forma turns engineering intent into a checked revision of a rectangular panel enclosure. It combines a live Meta model with a deterministic design environment, real OpenCascade solids, immutable revisions and reproducible exports.

## Start

From the workspace:

```powershell
./crate_studio/start.ps1
```

Open http://127.0.0.1:8770. The API binds to loopback only. The local CAD runtime used during development lives in `research/vendor/cad-runtime` and is not part of the application source.

For a fresh installation with Python 3.12:

```powershell
python -m venv .venv-forma
./.venv-forma/Scripts/python.exe -m pip install -r requirements-forma.txt
./.venv-forma/Scripts/python.exe -m crate_studio --port 8770
```

For live Meta proposals, set `MODEL_API_KEY` in the workspace `.env` or process environment. Existing API transport reads it server-side; keys never enter the browser, project exports or request receipts. Do not include `.env` in a public repository. Without a key, manual design, stock search, verification and exports remain available.

## Workflow

1. Edit internal dimensions, material, stock thickness and optional lid in Properties. Preview, inspect checks, then save a version.
2. Edit capacity, outside envelope, mass and optional idealized floor-deflection requirements.
3. Use Find stock design for numerical inverse sizing, or ask Meta to interpret a revision and invoke that search.
4. Inspect the proposal and changed requirements before applying it. Ambiguous and unsupported requests withhold a revision.
5. Inspect Model, Drawing, Cut list and Verification; download the complete design package or individual formats.

Orbit by dragging, pan with right drag, and zoom with the wheel. F fits the model; 1/2/3 select front/top/right. Explorer and Properties become drawers in a narrow window. History allows branching from any saved revision. Saved files live under `output/forma`.

## Supported design family

- Five rectangular uniform-thickness panels, or six with a full-footprint top panel.
- Full-footprint base; front/back span the outside width; side panels fit between them. Clear dimensions are independent of thickness.
- Ideal butt joints, no gaps, hardware, glue specification, kerf or manufacturing allowances.
- Four reference material profiles and explicit configured stock lists. Density and elastic modulus are reference assumptions, not supplier/grade certificates. Stock lists do not assert availability.
- Capacity and envelope constraints, nominal empty mass, and optional floor-deflection screening.

The floor model is a full-depth, simply supported, linear elastic beam strip spanning the clear width with a uniform distributed payload. It assumes ideal supports and excludes joint compliance, creep and plate-specific behavior. For total load P, span L, breadth b, thickness t and modulus E, maximum deflection is `5 P L^3 / (32 E b t^3)`. It is an engineering screening calculation, not FEA or a safe load rating.

The inverse solver enumerates listed stock thicknesses. Locked dimensions remain fixed. Unlocked minimum-mass sizing follows the original proportional/clipped dimension family; maximum-capacity sizing scales the envelope aspect ratio. Results are optimal among supported evaluated candidates, not arbitrary shapes or globally optimized enclosure geometry.

## Outputs and verification

- STEP: distinct, valid BREP panel solids, reimported and checked for count and volume. Neutral solids can be edited in a CAD system; STEP does not contain a native SolidWorks feature tree.
- Parametric Python + design JSON: regenerable CAD construction source.
- STL: geometric union of the touching panels, independently checked as a watertight volume. The fused mesh does not specify how physical panels are joined. Import units are millimetres.
- DXF: separate closed 1:1 rectangular panel profiles in millimetres.
- SVG/PDF: dimensioned geometry-review sheets; not released manufacturing drawings.
- CSV: panel cut list.
- ZIP: project, constraints, checks, artifacts and SHA-256 manifest. Live model receipts are retained locally, not included in vendor files.

BREP validity, pairwise positive-volume collisions, clear-cavity intrusion, panel count, bounding dimensions and independent volume arithmetic are checked. These checks do not certify assembly strength, impact resistance, creep, tolerances or manufacturing suitability. No prototype has been physically validated.

## Meta contribution

`agent.py` uses `muse-wonder-1.0` to interpret revisions, preserve retained requirements, cite source text and choose a stock-size search. It can review checker feedback in one additional call. Geometry and numerical verdicts are computed by fixed code; the model cannot execute arbitrary source code or claim its own numerical result passed.

Exact source quotes establish provenance, not proof that intent was correctly interpreted. The interface shows a proposal before approval. A configurable shared application guard covers persisted calls in `output/forma/agent` and `output/forma/studio/agent`; estimates and conservative reservations are not verified provider billing. A missing usage response consumes its full request reservation. Calls are serialized in the server process. Remaining provider credits were not verified. See [Muse design tools](../docs/FORMA_DESIGN_TOOLS.md) for the opt-in native inspection, floor, motion and visual-review loop.

## Verification commands

```powershell
./research/vendor/cad-runtime/Scripts/python.exe -m unittest discover -s tests -p 'test_crate_*.py' -v
python -m crate_studio.evaluation
python -m research.verify_forma_http
```

The HTTP command requires the server. It creates a clearly labeled verification revision. It makes no model calls. The eight frozen live integration cases and actual responses are in `output/forma/acceptance-v1`; they are constructed application acceptance cases, not customer validation or an external CAD benchmark. Do not rerun them and label the same tasks unseen.

## Attribution and event scope

New in this implementation: the panel design contract and solver, CAD adapter and checks, export pipeline, app server, Meta planner, complete interface, project history and verification harnesses.

Reused: `scripts/api_preflight.py` for server-side environment loading and API transport; previously downloaded Three.js 0.170.0 and OrbitControls, with MIT license and original download receipt included under `web/vendor`. CadQuery/OpenCascade, trimesh, ezdxf, FastAPI and Uvicorn are dependencies. Earlier folding, actuator and revision-intent studies were not rewritten or claimed as new results. No external CAD dataset was used to train this system.

Before hackathon submission: a designer review of a real revision and a physical prototype would strengthen impact evidence. Public repository publication and the three-minute demo submission are separate remaining submission tasks. This project does not yet establish customer time savings or winning probability.

Full public CAD-bench coverage, native editable gears/threads, controlled Meta-only results and limitations: [full evaluation](../docs/FORMA_FULL17.md). Open `/full17` in the running app for all 17 results and retained evidence.
