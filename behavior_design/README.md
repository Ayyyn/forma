# Nonlinear behavior design — development proof

Implemented October 30, 2026, separately from the earlier origami research and
spatial-frame workbench. Open <http://127.0.0.1:8780/> after starting the server.
This is an honest scientific integration milestone, **not an AI discovery win**.

The application connects an explicit mechanical architecture library, an energy
solver, target-curve fitting, independent checks, actual Muse tool calls and a
3D inspection interface. There is no chat interface or invented model output.

## Run, replay and reproduce

From the repository root, with the existing scientific Python environment:

```powershell
python -m pip install -r requirements-behavior.txt
python -m behavior_design serve --port 8780
```

Viewing the app, switching controllers, moving the travel slider, inspecting
candidates and replaying results make **zero API calls**. Manual edits run the
deterministic solver and save separate JSON branches. The original applications
on 8767/8770 and all older raw results remain intact.

Reproduce numerical search and freeze a NEW study directory:

```powershell
python -m behavior_design.runs --policy numerical
```

The console prints its study ID. To perform new paid experiments against that
frozen version, using a local `.env` with `MODEL_API_KEY`:

```powershell
python -m behavior_design.runs --study NEW_STUDY_ID --policy single_pass
python -m behavior_design.runs --study NEW_STUDY_ID --policy adaptive
python research/behavior_report.py NEW_STUDY_ID
```

These commands make real API requests. Existing run directories are skipped,
never overwritten. Source-hash mismatches are refused. Frozen source copies,
public tasks, constructed target generator and compact feasibility witness are
inside each study. Saved study:
`output/behavior-design/studies/20261030T041339Z-df03fcea/`.

The original comparison source is in that study's `source/` directory; later
viewer/reporting code is separate. Use the pinned environment from the complete
workspace. The viewer reuses the already-attributed Three.js 0.170.0/OrbitControls
files in `mechanical_workbench/web/vendor`; their MIT license and receipt remain
there. No installed OpenSees runtime is redistributed as project source.

Verification:

```powershell
python -m unittest discover -s tests -p test_behavior_design.py -v
python -m unittest discover -s tests -p test_behavior_viewer.py -v
python -m unittest discover -s tests -p test_kresling.py -v
python research/behavior_component_check.py
python research/behavior_report.py 20261030T041339Z-df03fcea
```

FastAPI's in-process test client needs the unrestricted local execution context
on this host. It hung in the restricted sandbox; the blocked process was
identified and stopped, and all five viewer checks passed outside that sandbox.
This is an environment limitation, not a passing result attributed to a hung run.

For the optional external check the installed isolated directory is
`research/vendor/opensees-runtime`; distributions are `openseespy==3.8.0.0` and
`openseespywin==3.8.0.0`. An equivalent Windows environment can install them there
with `python -m pip install --target research/vendor/opensees-runtime openseespy==3.8.0.0`.
The independent software is an audit tool; consult its license before any
redistribution or commercial use. The normal app requires no OpenSees process.

## Mechanical law and supported stability statements

For a guided apex and two bilateral ideal axial springs, let half-span be `a`,
initial rise `H`, axial spring constant `k`, orientation `s=+1/-1` and prescribed
downward stage travel `u`. Units are mm, N and N mm. Define

```text
q = s H - u
L0 = sqrt(a² + H²)
l = sqrt(a² + q²)
E(u) = k(l-L0)² + 0.5 kr u²
F(u) = dE/du = -2k(l-L0)q/l + kr u
K(u) = dF/du = 2k(1-L0 a²/l³) + kr
```

The established two-bar/von-Mises geometry is not our invention. The elements
here are ideal spring links, **not solid bars that resist arbitrary compression
without buckling**. Springs can be bilateral in this ideal model; real hardware,
coil dimensions, guides, bearings and joints have not been designed or measured.
With `s=+1,kr=0`, free guided minima occur at `u=0,2H` and an unstable maximum
occurs at `u=H`, of height `k(L0-a)²`. Changing rise20 → 15 mm moves the second free
minimum40 → 30 mm and changes the energy maximum 68.629 → 25N mm (`a=20,k=1`). This is
an analytic reference, not a measured switching event or a new multistability claim.

Production stages are deliberately convex:

- Upright stage: `kr = b + 2k(L0/a-1)`, so the exact global tangent floor is `b>0`.
- Inverted stage, driven away from the anchor line: `kr=b>0`; travel `u>=0` makes
  its stage energy strictly convex.
- Parallel copies multiply energy, force and tangent by their count.
- Series stages minimize total energy subject to `sum(u_i)=U`. The reduced
  gradient is `F_i-F_last`; Hessian is `diag(K_i)+K_last 11ᵀ`. Positive stage
  tangents imply a unique constrained internal minimum. Effective drive tangent
  is `(sum(1/K_i))^-1`.

Newton plus backtracking resolves internal travel with a 1e-9 N target force-balance
residual; results above 1e-7 N or with nonpositive constrained Hessians are rejected.
Reported trajectories are quasistatic displacement-controlled configurations.
A positive internal Hessian does **not** establish a freely released equilibrium;
a prescribed coordinate is not itself a stable state. No dynamic snap-through,
retention, damping or hysteresis is simulated.

Independent endpoint vectors and axial forces check the assembly's energies and
reactions, and re-equilibrated energy finite differences check drive force.
OpenSees `corotTruss` with elastic engineering strain independently reproduces12
component cases, including imposed negative-slope states, with maximum absolute
force discrepancy 7.54e-14N. This verifies the same ideal law in independent code;
it cannot establish that the ideal law describes real manufactured hardware.
See [OpenSees documentation](https://openseespydoc.readthedocs.io/en/latest/src/corotTruss.html)
and [its element implementation](https://github.com/OpenSees/OpenSees/blob/master/SRC/element/truss/CorotTruss.cpp).

The second family imports the **unchanged** Kresling effective bar/hinge law from
Zang et al., JMPS 188 (2024), 105630,
[DOI 10.1016/j.jmps.2024.105630](https://doi.org/10.1016/j.jmps.2024.105630).
Earlier published-result reproduction and 70-digit/vertex checks are documented
in `kresling_proof/`, not newly claimed here. At each imposed axial travel, a
sampled twist scan brackets stationary points, Brent resolves zero torque and a
positive twist Hessian selects local minima. The relaxed axial tangent is the
Hessian Schur complement. Online scans use 49points and selected-design audits 193;
ambiguous/absent sampled minima are rejected. **This does not prove completeness
of all twist roots.** Parallel units require independent ideal rotational bearings.
Uniform effective stiffness scaling is a numerical design parameter, not a
calibrated material replacement or an engineered spring specification.

The eight public motifs contain at most three linkage stages/two internal
translation DOFs, or two Kresling twist DOFs. This slice does not yet solve an
arbitrary mixed nonlinear graph. The preserved spatial adapter handles up to 90
nodes / 300 members under its separate linear beam assumptions. Its larger graph
capacity cannot be used to claim equivalent nonlinear or fabrication coverage.

## Fixed task, fair controls and actual outcome

A known-feasible synthetic resistance target increases 0 → 9.99643 N through 12 mm.
It is generated by a specified graded linkage, disclosed in `reference.json` for
reproduction but not sent to the controllers. Controllers see 17force/travel pairs,
eight motifs, identical public parameter domains and fixed mechanical screens.
There is no dataset of real experiments and no hidden hardware truth.

Two independent requirement variants use100 × 75 mm and50 × 30 mm ideal envelopes. The
original target-generating design is 80 mm wide; an algebraically equivalent
consolidation of parallel springs has width 45.6 mm. This is established mechanics
and a constructed feasibility witness, not AI-invented geometry. The compact run
starts from its own task rather than continuing its controller's initial winner;
in fact those winners already fit the compact envelope. No revision-time saving
can be inferred. Reserved plate/coupler allowances do not constitute a collision-
checked packaged assembly. The app explicitly uses an exploded stage schematic.

Each controller gets240 new candidate queries per task. Every new least-squares
callback and invalid candidate is charged; exact cached repetitions are free.
Same fitter, same model, same bounds, same target and screens:

- Numerical control enumerates every feasible motif with 24queries each, then
  refines/restarts its best. Sobol restarts are fixed, unscrambled and deterministic.
- Single-pass Muse gets one actual model request to plan a sequence of shared
  fits, without solver feedback.
- Adaptive Muse can inspect outputs and choose further fits, at most six requests.

Each Meta task/controller has a conservative estimated $10cap, max 4096output
tokens/request, Muse Wonder 1.0/high reasoning/temperature0.2. Model estimates use
the previously configured $4/M uncached input,$0.20/M cached input,$20/M output;
these are **estimates, not verified invoices or guarantees**. Actual usage and
response IDs are preserved. No retries or fallback designs are hidden.

| Task | Numerical | Single-pass Muse | Adaptive Muse |
|---|---:|---:|---:|
| Initial, independently audited RMS |0.002760%|0.027800%|0.002761%|
| Compact, independently audited RMS |<0.0001%|No executable command|<0.0001%|
| Initial new candidate queries |240|240|240|
| Compact new candidate queries |240|0|229|
| First nominal success query, each successful task |16|16(initial only)|16|

RMS and max errors normalize by the target's **full-stroke maximum**, not by
pointwise force. Acceptance requires RMS<=5%, max<=10%, nonnegative force,
positive tangent>=.005 N/mm, the declared envelope and the linkage 8 mm extension/
20N axial-force limits. Final audits use 96travel points disjoint from all 17fit
points and independently check force/energy. These are additional same-model
numerical checks, not experiments or a new physical test distribution.

Eight actual HTTP200responses have eight distinct provider IDs. Estimated total
API cost $0.2772592, billing unverified. Five of six task/controller runs pass their
independent audit. The compact single-pass response returned no executable
command: it stays a failure, with no imaginary geometry or silent numerical repair.
End-to-end times include API latency and some concurrent execution; they are not
a controlled speed comparison or an equal-CPU experiment.

**Reporting correction:** the frozen raw held-out evaluator divided errors by
its held-out maximum, about 0.93% below the full-stroke maximum specified in the
protocol. The derived report recomputes both metrics with the correct full-stroke
denominator for every policy. Raw errors are retained in named fields and all raw
files stay untouched. No candidate, Meta call or acceptance decision changed.
Manual branches interpolate the 17target pairs between samples and explicitly
carry no held-out benchmark claim. The known reference generator has zero error
by definition; it is labeled separately from controllers' designed candidates.

## Recommendation and next gate

Continue this as a verified mechanics/workbench foundation. **Do not present
this result as frontier AI discovery or spend more credits tuning this brief.**
Even the first single-linkage fit meets the 5% criterion. The test is too easy to
establish necessary architecture discovery; adaptive Muse essentially follows
the supplied strong control strategy and ties its final numerical accuracy.
One incomplete single-pass output is evidence about this run, not a general
model-capability verdict. No measured prototype/time savings or novel optimized
structure has been established.

The next useful test must be frozen before model calls and contain multiple
independent briefs where different mechanism families are actually necessary,
an infeasible control, validated packaging/joint assumptions, and either a
separately checked higher-fidelity oracle or real bench observations. Give a
strong family-enumerating numerical controller the same tools and information.
Set a stopping rule for meaningful improvement in accepted designs or experiment
count. If Muse cannot clear it, present the verified assisted design workflow
honestly or pivot the AI role to a task with genuine information uncertainty.
Adding agents, vision or RL alone does not fix an uninformative objective.

## Attribution, preserved work and submission scope

All 1525files from the verified earlier-direction checkpoint remain byte-identical.
The new nonlinear package, model equations/derivatives, independent component
checks, frozen tool-controller comparison, plots and viewer were implemented on
October 30, 2026. Existing published Kresling mechanics, earlier reproductions,
previous candidate results and third-party numerical/graphics software remain
attributed as earlier work or dependencies. No claim that we invented Kresling
inverse design, multistability, von-Mises linkages or spring consolidation.

The user-supplied participant guide requires public repositories, licensed
assets and a demo that clearly distinguishes event-built contributions from
pre-existing work. This local workspace is not yet a public submission and no
publication/submission has been performed. Exclude credentials and installed
runtimes when preparing a future public repository. Keep a dated contribution
ledger and attribution. User's deadline: November 4, 2026, 9 PM Eastern Time.
