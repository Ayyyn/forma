# Nonlinear repair, stronger controls, and checked solid exports

October 29, 2026. This is a development experiment using the established guided
Kresling model, not a new mechanical principle or a manufactured device.
Earlier frozen experiments remain unchanged. Protocol/source were frozen before
the new 32-query numerical and Meta searches in `benchmarks/robust-discovery-v1`.
All 21 frozen source/input hashes still match.

## Decision

Continue a bounded scientific workbench experiment, with a stronger numerical
optimizer inside the design loop. Do not present this as a scientific breakthrough,
new-to-science structure, proven general AI advantage, or validated actuator.
The current winner is a parameter revision of an established assembly motif;
it does not establish architectural novelty. More API spending alone would not
resolve those missing claims.

The next useful gate is an unseen-requirement/architecture-selection study:
give both controllers the same numerical sizing tool, charge every evaluation,
freeze tasks and stopping rules before seeing outcomes, and measure accepted
design quality and total numerical work. Muse should choose hypotheses,
architectures and informative tests; ordinary optimization should size continuous
parameters. Broader families require their own independent mechanics checks
before they can be ranked together. Physical prototype savings cannot be claimed
until measured against a real fabrication workflow.

## What improved, and what did not

The earlier high-bias Meta design requires about 30 Nmm of clamp torque.
With zero additional end twist, the two equal half-span torsion offsets add only
a constant constrained energy: `k*psi^2 + k*c^2`. Removing their common offset
preserves internal stationary coordinates, Hessians and energy differences while
removing the gratuitous holding torque. This analytical repair was shared with
both new controllers; it is not attributed to a new Meta discovery.

That repair alone is insufficient: the lowest identified sampled escape path
height is 0.020807 mJ, and only 2/8 local tolerance samples preserve the four
selected modes/guards. The new evaluator follows unstable directions away from
index-one saddles to locate additional minima, checks the descent endpoints,
and conservatively fails missing path coverage. This supplements identical
stationary root seeds; it is not exhaustive state enumeration.

| Candidate source | Smaller A/B found-state bias, mJ | Lowest identified sampled path height, mJ | Local samples passed | Max selected axial force, N |
|---|---:|---:|---:|---:|
| Earlier Meta, common-offset repair only | 47.1559 | 0.020807 | 2/8 | 1.3425 |
| Frozen numerical control r002 | 34.0644 | 3.20059 | 8/8 | 1.1269 |
| New Muse Wonder r028 | 45.3270 | 2.55389 | 8/8 | 1.3364 |
| Additional post-hoc numerical pattern search r027 | 44.3071 | 0.594774 | 8/8 | 1.3293 |

Both new frozen searches had 32 charged candidate queries (three shared seeds),
1,024 stationary starts, and the same evaluator. Directed minimizations differed:
164 numerical versus 146 Meta. Root iterations, line searches and CPU work are
not equal. Screening wall times were 164.44 / 326.98 seconds, respectively, in a
shared development environment; this is not a controlled speed benchmark.
Top three per policy received 128 starts per setting, independent vertex-energy
and finite-difference Hessian checks, and eight seeded tolerance continuations.

Meta's bias is 33.1% above this frozen numerical controller. That figure alone
overstates the evidence for AI value: an additional ordinary adaptive coordinate
search, written after preliminary Meta results were inspected, reaches 44.3071
mJ with 32 further informed queries. A subsequent seven-point geometric sweep
does not improve that accepted bias. These additional searches are explicitly
post-hoc, have extra work and restricted motifs, and do not replace the frozen
controller. The remaining bias difference is about 2.3%; the Meta candidate also
has a deeper identified sampled path than that pattern-search candidate. This
is a useful development observation, not an estimate of general AI superiority.

The accepted Meta r028 has four cells with h0=39.48 mm, theta0=29 degrees,
handedness +,-,+,-; an axial spring over rings 0–2 with k=.025 N/mm and
rest-shortening settings A=60/B=-10 mm; two zero-offset half-span torsion
springs of 20 Nmm/rad; and a fixed axial spring over rings 2–4 of .0022 N/mm,
zero rest-shortening offset. These ideal elements do not specify physical routing.
Selected nominal clamp torque is below 1.5e-10 Nmm; this is numerical zero, not
an experimentally measured zero. The largest selected axial force in its eight
tolerance samples is 1.3964 N. Its smallest selected normalized Hessian eigenvalue
is .03613. Independent normalized energy discrepancy is below 4.9e-17 and
Hessian discrepancy below 1.91e-8 (finite-difference step 1e-4).

## Claim boundaries and numerical uncertainty

- Positive Hessians establish local stability only in six constrained internal
  coordinates under an ideal coaxial guide. They exclude lateral modes.
- Constructed numerical descents are not physical time dynamics. Path heights
  are sampled values, not certified continuous upper/lower bounds, minimum-energy
  barriers, switching work or retention times. The old diagnostic file
  `research/nonlinear-robustness-initial.json` used overstrong `upper_bound`
  field names; preserve it as historical evidence, but use the corrected
  `research/nonlinear-robustness-corrected.json` and current sampled-path language.
- Eight fixed local continuation samples test persistence of four selected modes.
  They do not enumerate perturbed global minima, certify barriers or establish
  a manufacturing tolerance distribution. Proposal bounds are not physical
  validity bounds; sampled uncertainty may extend beyond proposal ranges.
- Additional starts can discover competing minima or previously missing paths.
  Some candidates are rejected and others rescued by the denser check. No
  exhaustive/global optimum, globally preferred state or infeasibility proof.
- No finite thickness, contact, spring hardware, one-way slack, dynamics,
  buckling outside the guide, material stress/failure, fatigue or printer physics.
  No physical experiments or measured avoided prototypes/human time savings.

## Actual model calls

Five new Muse Wonder requests returned HTTP 200, five distinct provider response
IDs, public outputs/tool commands and positive token usage. Receipts are in
`benchmarks/robust-discovery-v1/meta/events.jsonl`; candidate results are in
`meta/result.json`. No synthetic replay is counted as a paid call. No new vision,
image, RL or multi-agent system was used. Estimated reported-usage cost is
$1.7332312 at the frozen rates, below the $15 phase cap; actual credit deduction
is unverified. Keys/private reasoning are not stored in public evidence.

## Correct solid export, with explicit scope

The board now offers STEP, STL and OBJ ZIP bundles for the accepted numerical
and Meta winners' A/B target configurations. Five checked kits are retained,
including the earlier pilot's A target for inspection. Each kit has 48 separate
triangular prisms of assumed 1.2 mm thickness. Every triangle preserves the three
edge lengths of its selected source configuration, with source-face IDs and rigid
transforms in the manifest. Layout spacing is 5 mm; individual part files are
included because the full layout is approximately 502 by 199 mm.

These are **static geometry parts**, not a functioning folding assembly. A/B
kits are distinct snapshots; there is no claim that one rigid panel kit moves
between them. The reduced model allows deformation and does not validate the
added thickness. Hinges, rings/guide, springs, clearances and assembly remain
separate engineering work. Printer/material are explicitly **not decided**.

There is also a more direct print option: **one fused fixed-pose 3D display**
for each Meta A/B target, in the `*-display-v2` folders. Every facet is thickened
symmetrically by 1.2 mm and deliberately Boolean-unioned into exactly one valid
CAD solid; the lowest point is translated to z=0. A's bounds are approximately
61.006 by 60.999 by 103.644 mm. Its exact CAD volume is 31,784.7423 mm3;
3,264.1378 mm3 of intersecting panel material is removed by union. This changes
the crease/joint geometry into a rigid display, so the model's mechanics do not
transfer to it. No folding, actuation or strength validation is claimed. Supports,
orientation, material and slicer settings remain undecided. The board shows the
actual checked CAD tessellation, not an image or an invented render. Current
display manifests retain exporter source hashes and source snapshots. Initial
display revisions are preserved; all retained revisions are included in the
integrity audit. The separate panel-kit option remains available.

STEP comes from valid finite CAD solids, not a renamed mesh. STL/OBJ are tessellated
from those same solids. Every assembly and individual part was re-imported:

- CAD BREP validity, positive volume, solid count, explicit STEP millimetre units,
  volume and bounding-box agreement.
- Mesh closure, consistent winding, positive volume, two incident faces per edge,
  expected disconnected component count, bounds and volume agreement.
- Flat part layouts have non-overlapping positive-volume bounding boxes. Each
  triangle prism is convex; no untested union/mesh repair is silently applied.
- Independent artifact audit checks source edge lengths, triangle-area times
  thickness, transforms, 735 panel-kit format-file hashes, and all ZIP members/CRCs across
  240 panel parts. Display checks additionally verify the pre-union area/volume
  bound and retained exporter source hash. With retained display revisions, 747
  format files are hash-checked. Maximum panel-kit mesh bounds error 1.52e-5 mm, relative volume error
  1.50e-7; STEP bounds error 2.76e-11 mm and relative volume error 1.04e-12.
  Current display A's STL bounds/volume errors are 2.16e-6 mm / 1.28e-7 relative;
  its STEP has one valid solid and sub-1.3e-11 mm bounds error.

STL/OBJ have no enforced physical units: import as millimetres. Geometry validity
does not establish printer compatibility, material performance or self-assembly.
CadQuery/Open CASCADE provide real CAD import/export; Trimesh provides mesh
topology/re-import checks. See [CadQuery documentation](https://cadquery.readthedocs.io/en/latest/importexport.html)
and [Trimesh documentation](https://trimesh.org/trimesh.html). Dependencies are
pinned in an isolated CAD environment; scientific study dependencies were not
changed. Existing open OBJ surface exports remain visualization-only.

The local board's format/state/layout controls were exercised. The three panel-kit format actions
request their allowlisted ZIPs and the local server returns HTTP 200. The browser
download destination was not confirmed; direct workspace ZIP links are also
available. A top-level download bridge retains iframe origin isolation and permits
only existing checked export bundles. No viewing/export action calls an AI API.

## Reproduce and inspect

Scientific runtime used Python 3.12.5, NumPy 2.2.6, SciPy 1.16.1.
The base regression suite passed 108 executed tests (CAD tests skipped there);
all ten CAD tests passed separately. Tests include independent mechanics,
saddle descent endpoints, torque redundancy, shallow-state rejection, source
triangle/solid volume, STEP/mesh round trips, malformed indices and open-surface
rejection, one-solid fusion and rejection of disconnected display parts. The Windows sandbox stalls the older FastAPI TestClient, so the full
base suite was run outside that sandbox with model calls mocked.

```powershell
python -m unittest discover -s tests -v
research/vendor/cad-runtime/Scripts/python.exe -m unittest discover -s tests -p test_fabrication_export.py -v
python research/robust_discovery_report.py
python research/check_print_exports.py
```

To rerun a search, use a fresh output directory; existing runs refuse overwrite:

```powershell
python -m robust_discovery freeze --directory benchmarks/robust-discovery-replication
python -m robust_discovery numerical --directory benchmarks/robust-discovery-replication
# The following makes real paid Meta API requests, up to the frozen phase cap:
python -m robust_discovery meta --directory benchmarks/robust-discovery-replication
python -m robust_discovery finalize --directory benchmarks/robust-discovery-replication
```

Meta responses are stochastic; identical new model outputs are not promised.
Preserved receipts support the recorded run. Finalization is numerical only.
The two post-hoc scripts also refuse to overwrite their existing diagnostics.

For CAD on a fresh checkout, create an isolated venv and install
`requirements-cad-lock.txt` (Windows/Python 3.12), or the two top-level pins in
`requirements-cad.txt`. Do not replace the scientific runtime's packages.

```powershell
python research/prepare_print_geometry.py --study benchmarks/robust-discovery-v1 --method meta --candidate r028 --setting A --output output/custom-print-input.json
research/vendor/cad-runtime/Scripts/python.exe -m fabrication_export output/custom-print-input.json --output output/custom-print-parts --thickness-mm 1.2
research/vendor/cad-runtime/Scripts/python.exe -m fabrication_export output/custom-print-input.json --output output/custom-static-display --kind static-display --thickness-mm 1.2
python research/build_discovery_board.py --destination output/discovery-board/fragment.html
python research/render_discovery_board.py --renderer PATH_TO_RENDER_SCRIPT
python -m http.server 8767 --bind 127.0.0.1 --directory output/discovery-board
```

The prebuilt board is standalone and bundles its plot library. The build helper's
wrapper renderer is an optional external dependency; pass its render.py path explicitly. Source documents and figures:
`output/robust-discovery/evidence.json`, `comparison.png/.svg`,
`computed-states.png`, and each export's `manifest.json`, `source-geometry.json`,
`README.txt`. CadQuery/Trimesh runtimes are ignored, not redistributed.

Attribution: Zang et al., JMPS 2024, DOI
[10.1016/j.jmps.2024.105630](https://doi.org/10.1016/j.jmps.2024.105630), and
PNAS 2025, DOI [10.1073/pnas.2426790122](https://doi.org/10.1073/pnas.2426790122).
Kresling inverse design, multistability, prestress programming and programmable
origami are established. Hackathon-built contributions here are the logged
experiment, verification tooling and inspection/export workflow, with earlier
work and third-party research explicitly identified. No eligibility guarantee
or winning-product claim is inferred from a working demo.
