# Mechanical investigation workbench — first working slice

This is a separate project direction. The earlier research, sources, results,
exports and viewer on port 8767 are preserved byte-for-byte and additionally
checkpointed. See `docs/DIRECTION_HISTORY.md` for restoration instructions.

## What is implemented

A structured workbench with a real WebGL assembly viewport, member picking,
load-case selection, scaled Hermite displacement views, relative member-strain
colors, fixed requirements, an inspector, immutable design branches, saved
investigations, tool/experiment traces and numerical checks. There is no chat UI.
The frontend bundles pinned Three.js 0.170.0 / OrbitControls and their MIT license.

The graph adapter accepts 2–90 nodes, up to 300 circular beam members and eight
explicit force/moment load cases. Arbitrary valid connectivity is supported,
not the old ten-node catalogue. Geometry must pass slenderness, unsupported-
component and unjoined-member collision checks. This is a software/model domain,
not an accuracy guarantee for every possible graph.

The default solved example has 45 nodes, 112 members, 216 free DOFs and three
load cases. A separate procedural twisted example has 90 nodes, 237 members,
486 free DOFs and three load cases. Both were checked against independent
strain-energy quadrature and OpenSees. The larger example is human-written
procedural geometry, **not an AI-discovered structure**. It is available under
“Import another assembly → Load verified 90-node example” and in
`examples/mechanical-workbench/twisted-90-node.json`.

## The actual investigation

1. Show an original prediction and a synthetic material-change observation.
2. Muse chooses a tool-based investigation. The observed run requests assembly
   context, performs a virtual cantilever coupon, then invokes numerical sizing.
3. The shared optimizer makes immutable radius revisions. Every new candidate,
   production assembly and independent assembly is counted. Geometry, requirements
   and load cases are copied, not silently changed. Cached physics can receive a
   new evidence revision after calibration without mutating its earlier status.
4. A separate oblique load case decides final acceptance. Source snapshots,
   provider receipts, tool commands, data and rejected revisions are preserved.

The coupon is a **synthetic, noiseless, closed-form cantilever test**, not hardware.
The unknown modulus is 1200 N/mm² in the default fixture, versus an earlier assumed
2000 N/mm². The material-change data comes from the same ideal linear law.
An equivalent modulus could also be inferred from the assembly-response ratio
in this deliberately easy known-law case. This prototype requires an isolated
coupon as a calibration gate; it does not establish minimal experiment count,
general diagnosis, discovery, or avoided physical prototypes.

## A failure we retained and corrected

The first controller runs passed the three sizing cases but failed the withheld
oblique load. These runs remain in the history:

| Revision of the workbench | Policy | Radius, mm | Withheld displacement, mm | Acceptance |
|---|---|---:|---:|---|
| Explicit-case screen, initial | numerical | .4954102 | .1428862 | fail |
| Explicit-case screen, initial | Muse | .4953278 | .1429803 | fail |
| Added direction-envelope guard | numerical | .5296326 | .1097070 | pass |
| Added direction-envelope guard | Muse | .5296326 | .1097070 | pass |

The fixed displacement limit is .120 mm. The updated selected design has
1308.2633 mm³ member-volume proxy, .0874785 mm maximum displacement among the
three basis cases, and a .1199812 mm worst-direction displacement bound including
the declared 5% modulus uncertainty.

This correction is our engineering work, not attributed to Muse. Both controllers
use the same updated numerical tool and reach the same repair. No AI superiority
or efficiency advantage is claimed from this development case.

### Direction-envelope scope

When three orthogonal equal-norm forces act at a single port, each node has a
3×3 translational response matrix. Its largest singular value gives the exact
maximum displacement under any same-norm force direction for this linear model.
Taking the maximum across nodes gives the assembly displacement envelope. With
uniform E and fixed Poisson ratio and no grounded springs, response scales exactly
as 1/E, so a lower-E bound is also available without an extra solve. Explicit
worst-direction and lower-E solves check these identities in tests.

This is a **displacement-only** envelope. Strain, sampled section rotations and
local pinned-Euler ratios remain screens of the explicit cases; the withheld
case receives its own checks. The envelope does not cover arbitrary load locations,
simultaneous ports, torques, nonlinearities or real uncertainty distributions.
For other imported load bases it is explicitly unavailable, not silently assumed.

## Numerical evidence and real API receipts

Four selected investigations (including failures) have 16 additional offline
OpenSees load-case comparisons. All pass; maximum mixed displacement/rotation
error is 3.52e-14. The 90-node example has three further OpenSees checks and an
independent quadrature discrepancy of 6.78e-15. These compare the **same ideal
law**, not physical device performance.

Two development Muse runs made eight actual API requests: eight HTTP 200s,
distinct provider IDs and returned tools/usage. Estimated reported-usage total
is $0.3875304; actual billing is unverified. The corrected run used four calls,
estimated $0.2308976. No API call occurs on page load, inspection, replay or export.
Each explicitly requested new Muse run has a four-request and estimated $5 cap.
No private reasoning or credentials are stored in the public frontend or traces.

The corrected numerical and Muse runs each charge 16 candidates, 17 production
assemblies and 17 independent assemblies (the extra is the withheld case), and
one virtual test. Offline external audits and preparation of the development
fixture are separate work. Initial numerical sizing used 12 candidates, versus
16 for Muse; do not compare those initial runs as an equal-work benchmark.

Raw records: `output/mechanical-workbench/runs/<id>/` contains `manifest.json`,
`source/`, `timeline.jsonl`, `result.json`, and `api-events.jsonl` for Meta runs.
`external-audit.json` is an added offline audit, not a change to raw outputs.

## Start, reproduce, inspect

From `C:/Users/LENOVO/meta_hack`, using the existing Python 3.12 scientific runtime:

```powershell
python -m mechanical_workbench serve --port 8770
python -m mechanical_workbench numerical
# Makes real, bounded Meta API calls using the local .env key:
python -m mechanical_workbench meta
python -m unittest discover -s tests -p test_mechanical_workbench.py -v
python research/workbench_external_audit.py
python research/workbench_large_example.py
```

The complete base suite passed 127 executed tests, including 19 workbench tests;
10 unchanged CAD tests are skipped in that runtime (they passed previously in
their isolated runtime). The full listing reports 137 tests including those skips.
Windows FastAPI TestClient needs execution outside this machine's restricted
sandbox. No test invokes a paid model API.

Fresh environment: install `requirements-workbench.txt`. The optional external
audit uses the previously installed isolated OpenSees research runtime, whose
license/receipts remain in the earlier project. It is not redistributed. Browser
vendor files are included; their URLs/hashes are recorded in
`mechanical_workbench/web/vendor/receipt.json`.

The browser can import JSON with `design`, `load_cases` and `requirements`.
Imported graphs are independently checked and then receive an explicitly synthetic
material-change fixture. Modulus values must remain in the adapter's supported
range after the virtual change. Manual inspector evaluations save independent
nominal predictions in `output/mechanical-workbench/explorations/`; they do not
inherit an unearned calibration/held-out acceptance claim. Saved investigations
retain their own graph/load/requirement context when opened or rerun.

## Scope still to build

- Natural-language/diagram-to-formulation with an audited specification contract.
- Stronger identification tasks with genuinely ambiguous failure hypotheses.
- Architecture/experiment-selection benchmarks on unseen requirements with
  comparable tools/budgets, rather than this known development fixture.
- Independently verified nonlinear force-response adapters and coupled mechanisms.
- Functional fabrication geometry, joint/fixture design, thickness/contact and
  measured physical behavior. Current frame JSON is an analysis model, not
  print-ready solid CAD. Earlier checked **static** STEP/STL/OBJ exports remain
  accessible through the preserved viewer.

Do not describe a larger graph as higher-fidelity physics. Current mechanics
remains small-displacement circular Euler–Bernoulli beams, rigid joints, no shear
deformation, contact, global buckling, material failure or fabrication calibration.
This first slice demonstrates the engineering workflow and infrastructure; it
does not establish a hackathon-winning discovery claim.
