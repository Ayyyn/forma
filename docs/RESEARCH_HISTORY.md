> Historical research directions and results, preserved November 1, 2026. Current product: Forma CAD.

# Design Continuum — Discover

**Structural R&D experiment:** [non-folding structure design with Meta tools and numerical controls](docs/STRUCTURE_LAB_RESULTS.md). The first broader pilot generates and independently checks useful candidate graphs, but does not establish general AI optimization or physical-prototype savings. A wider-catalogue diagnostic exposes an important baseline-coverage confound. Run `python -m structure_lab verify` and `python -m structure_lab report` to inspect the retained v3 experiment offline. Earlier project directions and results are preserved below.

**Latest pivot research:** [execution-backed bug reproduction](docs/PIVOT_BUG_REPROOF.md). Meta generated verified suites in 13/16 runs on eight historical issues, versus 6/16 for limited literal rules, plus a successful fresh local-code example. The overall pilot gate still failed on structured clarification reliability; the main product/UI build is on hold. This is a bounded capability study, not a claim of a novel testing method or superiority over current coding agents.

A local computational design studio for exploring a printable panel that opens to a useful extent and fits a pocket. The first prototype compares established accordion and Miura-ori mechanisms, checks exact ideal kinematics, searches dimensional trade-offs, and lets a real Meta model direct bounded geometry experiments.

**Current decision: no-go for a Meta-led Kresling experiment-selection demo.** The [mechanical proof](docs/KRESLING_PROOF.md) reproduces published reduced-order mechanics, but the [new frozen benchmark](docs/KRESLING_META_VALUE.md) does not demonstrate meaningful additional Meta selection value: 1.48% lower primary loss, an uncertainty interval spanning zero, and substantially greater latency. All 192 real Meta calls and 144 scored runs are retained in [the evidence archive](benchmarks/kresling-selection-v1/README.md). Physical validation remains unperformed. The older studio below is preserved; it is not the recommended direction to expand.

**October 29 reassessment:** at the user's request, [researched a more capable actuator-design experiment](docs/ACTUATOR_SECOND_ATTEMPT.md) with optimization, geometry and constrained-stability tools. A new offline assembly probe demonstrates geometric twist cancellation with an unstable intermediate configuration, and an ideal-spring numerical repair with a force penalty. This supports a bounded new investigation; it is not a new Meta success or a replacement of the frozen result. No additional Meta calls were made for this reassessment.

```powershell
python -m pip install -r requirements-science.txt
python -m kresling_proof all --output artifacts/kresling-proof
python -m kresling_bench summarize
```

## Run

Python 3.12 is the tested runtime. From this directory:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn continuum.server:app --host 127.0.0.1 --port 8765
```

Open [the local studio](http://127.0.0.1:8765). No Node build or frontend package installation is required. Optional Google Fonts have system-font fallbacks. Keep `.env` in this project root; never publish it. The static server exposes only `web/`, not the project directory.

The deterministic exploration, 3D folding viewer, parameter editing, constraints, and downloads work without model credentials. Live agent runs require `BASETEN_API_KEY` or `MODEL_API_KEY` as documented in `.env.example`. Baseten uses the hackathon-specific `meta-models/muse-spark-open-1026`; direct Meta uses Standard `muse-spark-1.3`. There is no silent provider fallback.

**The default is single-pass Meta planning plus deterministic verification:** one model request proposes a search region, then the shared numerical sampler evaluates 64 candidate attempts including a common starting candidate. Invalid and duplicate proposals consume budget. The declared objective selects the feasible winner; an independent scoring oracle and rigid-facet checks must pass. There is no retry, provider substitution, or relaxation of requirements. Usage is recorded; dollar cost and remaining account credits are not inferred. The older loop is available only through explicit API `mode: "feedback"`.

The default was exercised with a real Baseten call: run `ebd847afdf79` used one model request and 64 attempts, selecting design `bbbf31e211` with all eight ideal constraints passing. Its computed deployed envelope is 244.06 × 151.53 × 3.11 mm, packed envelope 110.69 × 22.93 × 22.29 mm, and crease count 66. The printable pack at `output/pdf/paper-model-print-pack.pdf` contains an A4 pattern, illustrated folding instructions and a blank worksheet. Follow [the physical protocol](docs/PHYSICAL_PROTOCOL.md); actual paper measurements remain pending.

## Earlier feedback-loop example

The actual Muse Spark Open run `42afc07e0679` used five geometry tool calls and selected `d1f407d095`:

| Computed quantity | Value |
|---|---:|
| Deployed envelope | 254.13 × 151.14 × 2.73 mm |
| Packed envelope | 113.62 × 34.63 × 19.57 mm |
| Required deployed extent | at least 240 × 150 mm |
| Maximum pocket | 120 × 45 × 24 mm |
| Crease segments | 57 |
| Material area | 367.64 cm² |
| Constraints satisfied | 8 / 8 |

The run diagnoses the accordion's retained width, invokes actual search/evaluation tools, reads the results, and selects an ID whose geometry is recomputed and checked. This is an improvement over one naive starting design. It is **not evidence of superiority over a broad deterministic optimizer**, and neither family is our invention. The search includes a known reference candidate as well as seeded random proposals; it is not an exhaustive search.

See `examples/verified-agent-run.json` for the public trace, `examples/agent-selected-pattern.svg` for the printable pattern, and `examples/agent-selected.fold` for the crease geometry. In the current local session, “Load latest saved run” reads actual saved traces without making another API call.

## Verify

```powershell
python -m unittest discover -s tests -v
node --check web/app.js
python scripts/run_experiment.py --provider baseten
```

The first command runs software and independent geometry checks, including facet distances/diagonals, polygon area, planarity, an alternative edge-tilt construction, known configurations, topology, crease signs, invalid inputs, impossible requirements, fixed-seed search and export/API consistency. The final command makes real model calls and spends API credits. Local run traces are written under ignored `artifacts/runs/`; only deliberately selected public examples are retained in `examples/`.

## Scope of validation

This is **zero-thickness, ideal rigid-folding geometry**. The operating domain has a continuous analytical construction and a positive planar Jacobian; the sheet's projected facet interiors do not overlap there. Finite-thickness interference, crease torque, bending, strength, stability and locking are not modeled. SVG/FOLD exports agree with the mesh, but fabrication and physical measurements remain pending. No simulation output is presented as a physical measurement.

- [Feasibility comparison and references](docs/FEASIBILITY.md)
- [Equations and nonintersection argument](docs/GEOMETRY.md)
- [Decision record](ADR/0001-analytic-deployable-panel.md)
- [Paper prototype protocol](docs/PHYSICAL_PROTOCOL.md)
- [API access results](API_ACCESS_RESULTS.md)
- [Dated new contributions](HACKATHON_WORK.md)

Research and mathematical attribution are in the feasibility report. No simulator source code was copied. Runtime dependency licenses: FastAPI/uvicorn MIT, NumPy BSD-3-Clause, Pydantic MIT. The FOLD interchange specification is credited to Erik Demaine, Jason Ku and Robert Lang; exported custom properties use a `continuum:` namespace.

## Next competition milestones

Measure a real paper prototype; extend the completed equal-budget comparison to independent tasks and additional numerical optimizers; test changed design goals and robustness to fabrication tolerances; prepare live hosting, public source repository and the three-minute demo. Current judging weights from the supplied participant guide are impact 30%, Meta tooling 25%, technical execution 20%, demo 25%. Submission is November 5, 2026 at 07:30 India time.

## Controlled benchmark and independent audit

The subsequent benchmark uses 64 candidate attempts per method, six tasks and three seeds. It compares constructive adaptive numerical search, a one-pass Meta search planner, and a three-turn feedback planner using the same sampler and independent scoring checks. The final reasoning-enabled protocol and preserved diagnostic conditions are explained in [the protocol](docs/BENCHMARK_PROTOCOL.md). This benchmarks a restricted search-planning role, not arbitrary physical invention.

```powershell
python -m pip install -r requirements-audit.txt
python scripts/audit_geometry.py
python scripts/summarize_benchmark.py --version 5
```

Existing public result ledgers are replayed without new API calls by the summary command. `python scripts/run_benchmark.py --run --workers 2` makes real API calls only for missing cells; it never overwrites an existing result. Frozen manifest hashes reject unnoticed source changes. Do not pool results from different protocol conditions. [Correctness audit and remaining uncertainty](docs/CORRECTNESS_AUDIT.md) distinguish checkable mathematical evidence from unmeasured physical behavior.

The [final results](benchmarks/RESULTS-v5.md) are 15/15 feasible instances for both reasoning-enabled model policies and 12/15 for the numerical baseline. Every run used exactly 64 attempts. Single-pass planning beat the feedback agent on the declared lexicographic objective in 12/15 paired cases, so the benchmark does not justify the more complex feedback policy as the default. The geometry audit and all benchmark ledger replays passed; physical validation remains pending.
