# Forma

Forma is a human-editable design workspace for foldable, adjustable and articulated physical products. Meta's Muse Wonder proposes parametric CAD features and revisions; CadQuery/OpenCascade computes and checks the geometry. The Studio connects requirements, editable models, sampled motion, drawings and fabrication exports.

## Run locally

Use Python 3.12 in an isolated environment:

```powershell
python -m venv .venv-forma
.\.venv-forma\Scripts\python.exe -m pip install -r requirements-forma.txt
.\.venv-forma\Scripts\python.exe -m crate_studio --port 8770
```

Open http://127.0.0.1:8770/studio. The browser assets are included; no Node build is required. Native CAD dependencies require platform-compatible binaries. Copy `.env.example` to `.env` and set `MODEL_API_KEY` locally for Muse proposals. Manual editing and deterministic geometry/export operations do not need an API key. This is a local application; internet hosting needs a separate authentication and execution-isolation design.

## Workflow

- Describe a product and its dimensional and functional requirements.
- Review the proposed parametric design before applying it.
- Edit feature parameters manually or request a targeted AI revision; retain revision history and undo/redo.
- Inspect geometry, measurements, component placement and sampled motion. Checks are tied to the model revision.
- Generate geometry-derived drawings and export STEP, STL, DXF, SVG, PDF and editable JSON where supported.
- Import existing meshes or native supported geometry and use the supported inspection/edit operations.

The adjustable-box prototype has four configurations and seven printed components. It uses a sliding mechanism. Separate supported rigid-panel folding families include Miura, concertina, annular half-fan, triangle strip and staged cube net.

Native-solid validity, interference and sampled motion checks do not certify friction, strength, fatigue, manufacturing tolerances or physical fit. The enclosure load estimate is an idealized beam screen, not FEA or a safe load rating. General crease-pattern discovery and arbitrary physical simulation are outside the current implementation.

## Source and evaluation

`crate_studio` contains the application. `tests` contains related offline checks. Selected `research` helpers and benchmark task definitions support reproducibility; generated runs and model receipts are not included. Some optional studies require local runtime tools or evidence outside this public checkout. Live evaluation helpers may make paid model calls; ordinary offline tests use mocks where appropriate.

The harness was developed against the 17 public CAD-bench tasks under an adapted STEP-based protocol. These are development diagnostics, not held-out generalization or an official leaderboard result.

```powershell
python -m unittest discover -s tests -p 'test_crate_engine.py' -v
python -m unittest discover -s tests -p 'test_workspace_requirements.py' -v
```

Public scope is explicitly listed in `.gitignore`; additions need a publication review. Internal planning, experiment journals, credentials, generated projects and recordings are local-only. Third-party notices are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No project-wide license has been selected.
