# External mechanics validation and prospective revision results

October 29, 2026. **The spatial mechanics passes independent external checks. The current Muse-led structural search did not pass its predeclared value gate. Do not expand this search loop into the hackathon centerpiece on the evidence we have.** This finding concerns a bounded graph/sizing task; it is not a result about all AI engineering assistance.

## External-solver gate: passed

Installed OpenSeesPy 3.8.0.0 / OpenSees 3.8.0 into an isolated optional local research runtime. Compared its `elasticBeamColumn` and `Linear` transformation with our spatial beam implementation under matching assumptions: circular sections, axial/biaxial bending/torsion, rigid ideal joints, clamps, nodal forces/moments and grounded output springs. Neither solver includes geometric stiffness, shear flexibility or contact in this comparison.

All 272 comparisons pass: the 254 valid candidates from the previous proof and 18 additional cases spanning six tip-load DOFs and three beam orientations. Maximum absolute displacement/rotation discrepancy: **4.54e-14** across mixed mm/radian DOFs. Maximum anchor force/moment discrepancy: **6.44e-15** across mixed N/Nmm DOFs. This provides external numerical agreement; it does not validate a fabricated joint or real material. No published Frame3DD example is claimed reproduced.

Receipts: `research/spatial-opensees-check.json`, `research/opensees-install-receipt.json`, `research/spatial_external_check.py`. Binary SHA-256 is recorded. The optional runtime and its licenses are kept locally in `research/vendor/opensees-runtime/` and excluded from Git/source snapshots. We are not redistributing it or deploying a service using it. Upstream [element documentation](https://openseespydoc.readthedocs.io/en/latest/src/elasticBeamColumn.html) and [linear coordinate transformation](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/geomTransf/Linear.html) are attributed.

## Prospective study: protocol and source frozen first

Implemented an isolated `spatial_revision/` adapter and tested it on development fixtures. Full workspace suite: **98 tests passed** before source/case freeze. Old spatial, planar and Kresling snapshots remain unchanged.

Only then generated eight fresh reproducible revisions: material modulus, resisting load stiffness, dimensions, asymmetric port placement, reverse output direction, material+load, shape+reverse direction, and combined changes. Generation used no forward solves, label filtering, feasibility filtering or target tuning. The family/distribution was developer-designed; these are synthetic unseen instances, not eight independent real customer briefs. There is one stochastic model trajectory per case.

Both methods received the same previous task/design, exact changed task, nodes/edge language, geometrically eligible conventional catalogue, constrained sizing optimizer and **256 charged-candidate cap**. Every new optimizer sample consumes a slot. Initial evaluation consumes the same first slot. Numerical control repairs the starter, screens a broader set of conventional spatial graphs, sizes promising graphs and removes members; it is not restricted to the small old template prefix. It is still a bounded control, not a global optimum guarantee.

Muse Wonder had at most four real API requests per case, with custom evaluation, analytic sizing, cached geometry/deformation views and radius sensitivities. It could not modify task requirements. Exact contracts enforce requirement preservation; semantic interpretation of an informal brief was **not** measured. Neither method was shown the other's results. Cases and source were not changed after scores appeared.

Frozen protocol: `docs/SPATIAL_REVISION_PROTOCOL.md`. Manifest, exact source, all candidates and raw public provider/tool records: `benchmarks/spatial-revision-v1/`.

## Results: no demonstrated search advantage

| Outcome | Stronger numerical control | Muse Wonder with tools |
|---|---:|---:|
| Verified feasible revisions | **5/8** | **5/8** |
| Median charged candidates to first feasibility, successful cases | **8** | **8** |
| Median cell wall time | **16.2 s** | **87.0 s** |
| Total charged candidate slots | 2,048 | 1,363 |
| Total online frame assemblies | 2,048 | 1,360 |

Four workers ran the matrix locally; wall times include concurrent work and model/inspection overhead, not isolated hardware latency benchmarks. Muse made three invalid custom-design evaluations; they consumed slots but not frame assemblies. Fewer total used slots alone does not establish query efficiency: Muse stopped earlier, neither first-feasible counts nor completion improved, and numerical control sometimes used its remaining work to improve the final design.

| Revision | Numerical volume proxy (mm³) | Muse volume proxy (mm³) | Interpretation |
|---|---:|---:|---|
| Material modulus | **59.349** | 65.224 | Muse about 9.9% larger |
| Resisting load | 60.616 | 60.616 | Effectively tied |
| Dimensions | 60.033 | 60.033 | Effectively tied; supplied starter already feasible |
| Asymmetric ports | **53.566** | 54.159 | Muse about 1.1% larger |
| Reverse direction | Failed | Failed | No accepted design found |
| Material + load | Failed | Failed | No accepted design found |
| Shape + reverse direction | Failed | Failed | No accepted design found |
| Combined changes | 59.446 | 59.446 | Effectively tied |

There was **no Muse-only success** and no smaller accepted Muse design. Differences below 0.001% are treated as effectively tied in this readable table. No averaged volume across unlike cases is presented as a meaningful objective.

All four initially failing cases that both methods repaired reached their first feasible candidate at the same counts: 15, 8, 7 and 18. The dimensions case was feasible at the shared first evaluation and is not credited as a model discovery. Median paired feasible volume reduction favoring Muse is approximately zero/slightly negative; descriptive case-bootstrap 95% interval is **[-9.90%, 0.00%]**, n=5. Query reduction is zero, n=4. The protocol required a positive improvement with at least six relevant pairs; **both quality and query routes fail**, while completion is tied. Eight cases/one trajectory and conditional paired metrics do not support a general negative claim about every model or task.

## Real API calls and numerical audit

**32 real requests**, all HTTP 200, **32 distinct provider IDs**, all native tool-call finishes. Muse actually invoked optimization, custom evaluation and numerical-geometry inspection. Twenty image inputs include repeated history; that is not twenty distinct views and does not isolate a causal vision benefit. The raw records remain available; no private reasoning text or credentials is saved.

Reported usage: 399,180 input tokens, including 168,136 cached, and 48,818 output tokens. Estimated cost **$1.9342**, using the [official listed Wonder rates](https://dev.meta.ai/products/meta-model-api) checked October 29 ($4/M uncached input, $0.20/M cached, $20/M output). Actual promotional-credit deduction is unverified.

All **3,408 valid candidates** replayed and matched a separately assembled Hermite strain-energy solution. Maximum absolute displacement/rotation discrepancy: **2.33e-11** across mixed units. All **16 selected results**, including best failed candidates, also matched external OpenSees; maximum absolute discrepancy **3.46e-14**. These audit solves were additional offline work, not supplied to controllers. `summary.json` records 6,816 candidate replay/oracle assemblies plus the selected external comparisons; each run's common final production/oracle check is separately recorded. Independent numerical verification is not physical validation.

## Failed cases: kept, not relabeled

A separate **post-hoc** diagnostic gave each of the three shared failures up to 1,024 additional candidate slots, used candidates from both scored methods as seeds, and screened/sized the full geometrically eligible conventional catalogue. It made **zero new API calls** and found **no feasible witness** in any of the three cases. This is not proof of infeasibility or an independent replacement baseline. The scored failures remain failures; feasibility within the bounded graph remains unresolved. The study therefore cannot attribute those failures solely to reasoning rather than the available design space/constraints/search.

See `research/spatial-revision-failure-diagnostic.json` and `research/spatial_revision_failure_check.py`. This extra diagnostic work is explicitly separate from the matched online budgets and is not pooled with the score matrix.

## Recommendation

**Go:** retain the verified numerical workbench, current physics adapter, receipts, revision contracts and actual Muse tool integration. They provide a defensible foundation for further experiments.

**No-go:** presenting this implementation as evidence that AI discovers better structures, speeds up engineering, reduces physical prototypes, or justifies a broad CAD/product build. More agent roles or RL training have no demonstrated benefit here; adding them now would increase scope before identifying a specific failure they can resolve.

The remaining plausible AI contribution is upstream: translating a genuinely informal/sketched requirement into a correct model/design space, selecting between mechanism families, or choosing physical measurements under uncertainty. This study supplied a model, exact requirements and a bounded geometry language. Testing one of those other responsibilities would require a new explicit benchmark and suitable comparators; this result neither validates nor rules them out. Do not keep changing the search benchmark until an AI win appears.

Physics still excludes finite motion, active power-source behavior, real joint concentrations/manufacturing error, material calibration, contact, fatigue and loaded-system buckling certification. All material coefficients and requirements are synthetic. **Physical experiments: zero. Avoided prototypes and human time savings: unmeasured.** No clinical or new-to-science mechanism claim.

## Reproduce

```powershell
python -m spatial_revision report
python -m unittest discover -s tests -p test_spatial_revision.py
python research/spatial_external_check.py --help
```

The report replays existing records without model calls and needs the optional OpenSees runtime. Install it separately for local research using `python -m pip install --target research/vendor/opensees-runtime openseespy==3.8.0.0`. Original receipts and license files are retained; deployment/redistribution is not part of this prototype. `run` skips completed cells and refuses to silently repeat a partial paid journal. `freeze` requires a fresh directory. The post-hoc failure script preserves an existing diagnostic rather than overwriting it.

Inspect `benchmarks/spatial-revision-v1/README.md`, `summary.json`, `comparison.png`, `manifest.json`, and `runs/` for the complete matrix, plots, exact generated tasks and actual provider outputs.
