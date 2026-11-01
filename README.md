# Forma CAD

A local, human-editable CAD workspace with Meta-assisted feature proposals, enclosure sizing, engineering drawings and neutral solid exports. Built with CadQuery/OpenCascade, FastAPI and Three.js.

## Run

Use Python 3.12 in an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-forma.txt
.\.venv\Scripts\python.exe -m crate_studio --port 8770
```

Open http://127.0.0.1:8770/ for enclosure design and http://127.0.0.1:8770/studio for the CAD editor. The existing local CAD runtime can also run the app: `research/vendor/cad-runtime/Scripts/python.exe -m crate_studio --port 8770`.

Manual editing, deterministic optimization and exports work without credentials. Optional Meta credentials belong in the ignored `.env`; see `.env.example`. AI proposes changes for review and explicit Apply.

## Current capabilities

- Parametric solid features, sketches, planar push/pull, assembly placement, measurements and interference checks.
- Editable feature history, revisions, undo/redo and named configurations.
- Enclosure stock optimization with selectable feasible alternatives.
- Geometry-derived drawings; STEP, STL, DXF, SVG, PDF and portable JSON exports.
- Shared brief, enclosure specification and requirements inside Studio; deterministic panel regeneration and revision-bound checks.
- Finite-thickness wall folding with local playback, sampled overlap checks and envelope plots.
- Large stage canvas with pan/zoom, minimap and model overview.
- Separate flat panel STEP/STL components and revision-bound workflow reports in the export package.

[Shared workflow and physical mockup guide](docs/FORMA_WORKFLOW.md) · [Studio capabilities and limits](docs/FORMA_STUDIO.md) · [Implementation plan](docs/FORMA_BUILD_PLAN.md) · [Demo](docs/FORMA_DEMO.md)

The supported enclosure load check is an ideal beam-deflection screen. General FEA, engineered hinge hardware and physical validation are still pending. Wall folding is a prescribed rigid-panel motion with sampled thickness-aware overlap checks. The separate `continuum` prototype contains ideal Miura/accordion kinematics; it is not yet integrated with Studio.

## Verify

```powershell
python -m unittest discover -s tests -p 'test_workspace_*.py' -v
python -m unittest discover -s tests -p 'test_crate_*.py' -v
python -m research.verify_studio_http --directory output/forma/studio/NEW_RUN
python -m research.profile_forma --output output/forma/performance.json
```

The HTTP harness expects the local application running on port 8770. These are constructed engineering checks; they are not external benchmark scores or physical test results.

## Repository and retained experiments

Source, tests, documentation and required browser assets are tracked. Local secrets, generated projects/exports, runtime dependencies, benchmark receipts and downloaded competition snapshots are ignored and retained on disk. Git is local until a remote is configured; ignored evidence needs its own backup.

Earlier experiments are preserved as research modules and in [the historical README](docs/RESEARCH_HISTORY.md). Their findings and limitations remain applicable to those experiments, rather than the current product roadmap. Third-party browser assets retain their licenses under the corresponding vendor directories. Previous-work attribution is in [crate_studio/README.md](crate_studio/README.md).
