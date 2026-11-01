# Spatial actuation mechanism: first numerical proof

Follow-up, October 29: external OpenSees agreement has since passed, and a prospective eight-revision study has completed. Its AI-value gate failed. See [the follow-up results](SPATIAL_REVISION_RESULTS.md); the step-one development record below remains historical.

October 29, 2026. **Continue with a loaded compliant transmission as the next functional demonstration.** A mount remains a useful simpler control. This first step establishes a runnable spatial mechanics/tool integration, not general AI superiority, a new mechanical principle or a manufactured actuator.

## Why this choice

A moving mechanism offers an explicit input/output requirement and lets us test the consequences of material and loading revisions. The first model is a passive structure driven by a prescribed external force. Its output moves against a resisting spring, so free motion cannot be mistaken for useful force delivery. It does not yet include a motor, pressure source, active material, dynamic cycle or large-stroke mechanism.

## Implemented and checked

New isolated `spatial_actuator/` adapter: true spatial circular Euler–Bernoulli beams with axial deformation, bending in both planes, torsion, six DOFs/node and moment-rigid ideal joints. The development graph has 10 nodes and 35 allowed edges; both input and output connect to anchored structure. Initial finite-radius unjoined-member collisions and minimum/slenderness bounds are rejected. Output stroke, spring force and energy, input travel, output parasitic motion, nominal member strains and conservative deformation/compression guards are reported.

The mechanics matches closed-form six-DOF cantilever responses and a cantilever against a grounded output spring, subdivision, rigid coordinate transformations, reciprocity, reaction balance and energy conservation. A separately coded Gauss/Hermite strain-energy assembly provides a second global solve. The reference gate's maximum scaled displacement discrepancy is 2.04e-14; radius sensitivities match finite differences within 2.23e-9 scaled error. These are checks of the same ideal model, not experimental material/joint validation.

All **91 workspace tests pass**, including 14 spatial tests. A published spatial Frame3DD example has **not** been reproduced: that external-solver reference under matching shear/geometric-stiffness/load assumptions remains a gate before a broader efficacy study. We did not silently compare our linear model with published examples that enable additional physics.

## One known development case

Synthetic isotropic E=2000 N/mm², nu=0.3; externally supplied input force 2 mN in +x; resisting output spring 0.02 N/mm along z. Require at least 20 µm positive output stroke, at most 40 µm input travel, and bounded parasitic motion/other guards. Objective: summed beam-volume proxy. Relative feasibility tolerance is 1e-6. Requirements were inspected during development and are not untouched evaluation cases.

| Controller | New candidate solves | Additional online inspection solves | Volume proxy | Loaded output stroke | Input travel |
|---|---:|---:|---:|---:|---:|
| Conventional catalogue + numerical sizing | 192 | 0 | 55.09334 mm³ | 26.08105 µm | 39.99928 µm |
| Muse Wonder + the same sizing tools | 62 | 1, original rendering implementation | 55.09278 mm³ | 26.08095 µm | 40.00004 µm |

Both satisfy the declared tolerance and select the same conventional six-member spatial fork. The tiny volume difference is effectively a tie, not a design improvement. Muse's first sized candidate was feasible; the numerical portfolio's first feasible was its 45th charged candidate. Both had a 192-slot cap, but different allocation/stopping policies. A known synthetic case, favorable initial family choice, early stopping and a baseline with a specific screening order cannot establish general sample efficiency, human time savings or reduced physical prototypes.

The output delivers about **0.522 mN** against the modeled spring. It stores about **0.00680 µJ** of spring energy during the input ramp; beam strain energy plus spring energy equals input ramp work. The spring's 17% share of that work is an energy allocation, **not cycle efficiency**. These tiny synthetic forces/strokes are a testbed, not an asserted real application specification.

Changing only E to 1200 N/mm² increases input travel to **61.913 µm**, so the material revision correctly fails the 40 µm requirement. The saved load sweep shows that output motion decreases and delivered force changes as load stiffness increases; failing sweep points remain labeled as such. No revision was silently repaired.

## Actual Muse calls and correction provenance

Four real `muse-wonder-1.0` Meta API requests returned HTTP 200 and four distinct provider IDs. Received commands: optimize the upper fork, inspect its computed geometry/sensitivities, optimize a lower fork, finish. The generated multi-view numerical geometry image was supplied in the following requests; two image inputs in total include the repeated history. No causal benefit from images is established.

Reported usage: 25,723 input tokens, including 11,240 cached, and 8,065 output tokens. At the [official listed Wonder rates](https://dev.meta.ai/products/meta-model-api) checked October 29 ($4/M input, $0.20/M cached, $20/M output), the usage estimate is **$0.22148**. Actual promotional-credit deduction is unverified. Public output, normalized commands, tool returns and usage are saved; private reasoning text and credentials are excluded.

The original source/report is preserved in `artifacts/spatial-actuator-step1/`. Inspection was described as using no new solve, but its drawing function recomputed one identical candidate. The table explicitly adds that one assembly: original online total 63, plus a separately recorded final production/oracle check. No new design or search guidance was hidden in that repeat.

Current code passes the cached result into drawing. `artifacts/spatial-actuator-step1-v2/` freezes this correction and an offline numerical rerun. All four previously received commands were replayed using current tools: every one of the 62 candidate records and the selected result was identical; drawing performed no reassembly. **This replay made zero API calls and generated no new model responses.** The original paid probe and the offline replay are not pooled or mislabeled as fresh model runs.

All 254 valid original candidates were independently checked offline (192 numerical + 62 Muse). Largest absolute displacement/rotation discrepancy was 3.83e-14 across mixed mm/radian DOFs. The additional replay/verification assemblies are explicitly recorded, were unavailable to controllers and are not part of their online search counts. Both versions preserve exact source hashes/snapshots. The previous planar/Kresling results are unchanged.

## Limits and next step

Small displacement/strain, rigid ideal joints and circular slender members; no shear flexibility, nonlinear/loaded-system buckling certification, contact, joint concentrations, fatigue or calibrated manufacturing model. Shared-node overlap is idealized, volume double-counts overlaps, collision checks apply to the initial geometry, and section rotations are sampled at 17 points/member. Strain and pinned-member compression guards do not establish structural safety. No physical experiment, new-to-science geometry, clinical capability or prototype savings has been demonstrated.

Next: cross-check a spatial case with an external solver under identical assumptions; then freeze a richer set of previously unseen load/geometry/material revisions and the stronger numerical generator. Score requirement preservation, verified completion, quality and resources separately. Muse can request numerical optimization, custom topology evaluation, multi-view deformation inspection and exact sensitivities. Additional model/context/reviewer roles should be added to address observed failures and tested with matched total budgets, rather than assumed to produce a drastic improvement.

## Run and inspect

```powershell
python -m spatial_actuator verify
python -m unittest discover -s tests -p test_spatial_actuator.py
python -m spatial_actuator report
# Optional: reproduce the saved Muse decisions without a new model call.
# Use a fresh --current directory for another tool replay; existing replay files are preserved.
python research/replay_spatial_tools.py --help
```

The default directory is the corrected v2 offline proof. `step1` creates a new proof in a fresh directory; `probe` performs paid requests and refuses an existing paid journal. To reproduce the original report, run its archived module from `artifacts/spatial-actuator-step1/source/` with `--directory` pointing to the absolute original artifact folder. Common Python/scientific dependencies remain required; no credentials are needed for verification/report/replay.

See `artifacts/spatial-actuator-step1-v2/numerical-design.png`, `load-sweep.png`, `material-change.json`, and `received-tool-replay.json`; actual provider receipts remain in `artifacts/spatial-actuator-step1/meta-probe.json`.

Classical mechanics/mechanism prior art: [Frame3DD](https://frame3dd.sourceforge.net/), [pyMOTO loaded compliant mechanism example](https://pymoto.readthedocs.io/en/latest/auto_examples/topology_optimization/ex_compliant_mechanism_springs.html). No source from these projects was incorporated. The new contribution here is our hackathon-built integration, verification and experiments; it is not the invention of compliant actuation or inverse design.
