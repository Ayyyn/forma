# Nonlinear structure discovery: first experiment and inspection board

October 29, 2026. **Continue this nonlinear discovery investigation. A useful candidate emerged, but this is a single exploratory task with important baseline/state-search limitations—not proof of scientific novelty or general AI superiority.** Earlier negative beam/revision results remain unchanged.

## Why this is a different experiment

The user correctly distinguished the previous bounded linear beam/sizing task from discovering nonlinear mechanical behavior. The [Princeton article](https://materials.princeton.edu/news/2025/looking-perfect-fold-it%E2%80%99s-frustrating) links to Zang et al., [PNAS 2025](https://doi.org/10.1073/pnas.2426790122). That research already demonstrates elastic frustration, tunable energy landscapes and programmable origami assemblies. We do not claim those inventions. The public paper discusses axial, torsional and local crease prestress; an ideal bilateral spring is not a reproduction of the paper's one-way/slack hardware.

Implemented a separate `nonlinear_discovery/` experiment using the already checked [JMPS 2024](https://doi.org/10.1016/j.jmps.2024.105630) Kresling cell energy. Four six-sided cells have variable height/twist geometry and handedness; spring topology connects pairs of five interface rings. One spring has two controlled preload/rest settings; up to three others are fixed. Both axial and torsional couplings are allowed. Total shortening is 55 mm and additional end twist is zero, leaving **six free internal coordinates** under ideal coaxial guides.

At each setting we solve the constrained stationary equations and classify the full six-dimensional Hessian. An attractive geometric configuration does not count as a minimum. This model excludes lateral/guide modes, routing/contact, real shell/material failure, fabricated joints, friction and switching dynamics. Control settings require external preload adjustment/work; there is no free-energy or autonomous actuation claim.

## Functional target

A memory-like element: retain locally stable internal shapes concentrated toward either end, while changing one preload makes the desired end's shape lower in energy. Polarization is `(u0+u1-u2-u3)/55`. Target sign is positive at A and negative at B, with magnitude at least .35. Both the target and opposite localized minima must coexist at each setting.

Require at least 0.5 mJ bias to the lowest **found** non-target minimum, selected normalized constrained Hessian eigenvalue at least 2e-4 and selected absolute axial holding force at most 1.5 N. Maximize the smaller A/B bias. Torque is reported, **not bounded in this task**. Energy bias is not a transition barrier or switching threshold; preference remains conditional on found states. These are synthetic research requirements, not a customer/device specification.

## Actual experiment and independent checks

Source/protocol frozen in `benchmarks/nonlinear-discovery-v1/`; 103 tests passed before scored calls. Numerical and Muse policies each received **24 candidate queries**, including the same conventional prestress reference. Each valid query ran 16 stationary starts at each of two settings: **768 root-start attempts per policy**. All 48 proposals were valid. Identical cached queries and inspections do not repeat roots. Root iterations/function evaluations vary, so this is equal candidate/start allowance—not equal CPU time or a claim of identical primitive evaluation counts.

The numerical policy follows fixed-seed stiffness continuation and incumbent-guided Sobol variations of geometry, preload and spring placement. Muse Wonder high-reasoning can batch arbitrary proposals in the same declared grammar and inspect cached coordinates, eigenvalues, forces and energies. The model received numerical structural context; no images were sent to its API in this phase. The local geometry viewer is separate.

Common final refinement reran each policy's top three candidates with 64 starts per setting. All six passed the task and independent cell ring-vertex/face-normal energy plus finite-difference Hessian checks. This is 384 additional stationary starts per policy, separate from online search. Maximum Hessian discrepancy in these audits was **2.31e-8**, below the declared 2e-5 limit. Geometry/derivative consistency is not experimental validation.

| Selected design | Bias after 64 starts/setting | Bias after separate 256-start audit |
|---|---:|---:|
| Frozen numerical winner | 30.684 mJ | **2.542 mJ** |
| Post-hoc numerical spring-grid winner | 34.064 mJ | **34.064 mJ** |
| Muse winner | 47.156 mJ | **47.156 mJ** |

The larger audit found additional competing minima for the original numerical winner. Its previous 30.684 mJ estimate was overoptimistic because of state-search coverage. The Muse candidate retained two found minima at each setting and the same 47.156 mJ bias. All three selected designs pass the denser task/independent checks. **256 starts is still not an exhaustive state enumeration or global-preference certificate.** Original screened/64-start records are preserved, not overwritten. The separate dense audit is `research/nonlinear-dense-check.json`.

The frozen policy's control also sampled programmable preload A in [32,55] mm and B in [0,23] mm during its Sobol phase, while the shared admissible grammar permitted [-10,60] mm. Muse used the wider allowed extremes. That is a real **control-coverage limitation**; the initial 53.7% improvement against its 64-start score is not a defensible general efficacy claim. We checked a separate 24-query post-hoc grid that used A=60/B=-10, conventional paired torsional springs and six axial stiffnesses. It reached 34.064 mJ, verified again with 256 starts, but did not match Muse. This diagnostic was informed by the observed motif and is not a fresh prospective comparator.

Muse screening took 226.8 s versus numerical 49.6 s. More candidates indicated feasible behavior during initial screening for Muse, but those counts depend on the limited initial state search. Neither runtime nor fewer prototypes improved demonstrably. There is one task and one model trajectory, not a repeated held-out study.

## What Muse proposed—and what it did not invent

The selected assembly keeps the four cells at h0=39.48 mm and initial twist 30 degrees, handedness `[+,-,+,-]`. It proposes:

- Programmable axial spring between rings 0–2: k=.027 N/mm, offsets A=60 mm/B=-10 mm.
- Torsional springs on rings 0–2 and 2–4: each k=30 Nmm/rad, rest offset 1 rad.
- Fixed axial spring on rings 2–4: k=.002 N/mm, offset zero.

Selected-state minimum normalized Hessian eigenvalue is about .00953, and maximum selected axial holding force is about 1.343 N. The clamped end supplies approximately **30 Nmm torque**, which was not a task limit. That clamp/payload demand must be included in a real application specification.

An algebraic diagnostic exposes redundant parameters: with zero total additional end twist, the two equal torsion offsets add a constant 30 mJ to constrained energy and change clamp torque, but do **not** change its internal gradient or Hessian. Their effective torsional stiffening is useful; the common offset is not extra internal programming freedom. `research/nonlinear-catalogue-challenge.json` records zero gradient/Hessian difference after removing those common offsets. The four-spring representation should not be advertised as four independent useful controls.

There is also a nearby index-one stationary saddle only **0.0208 mJ** above the opposite local minimum at setting B (and .1010 mJ at A). A connecting escape path has not been established, so these differences are **not certified barriers**. They are evidence that local-minimum existence alone does not establish robust memory, tolerance to disturbances or practical retention. The next task must explicitly address robustness and torque rather than maximize bias alone.

This is a useful simulated proposal and coupling motif, new to this run. We have not established a new fold pattern, new physical principle, unprecedented topology or a new-to-science device. Prior art includes mixed prestress and programmable assemblies.

## Real API usage and spending

**Six actual `muse-wonder-1.0` requests**, all HTTP 200 and six distinct provider IDs. Public received commands, tool outputs and usage remain saved. High reasoning and a maximum 12,288 output tokens/request were configured; no private reasoning text or credentials were saved.

Reported usage: 194,433 input tokens, including 137,156 cached, and 14,073 output tokens. Estimated usage cost **$0.5380**, within the initial **$15 cap**; actual promotional-credit deductions remain unverified. The cap reserves estimated worst-case request cost before each request. No images were submitted and no image-generation, RL training or additional model agents were used. We did not spend the full $100 simply because credits were available. Other numerical/post-hoc audits and board export made zero API calls.

## How the numerical controls work

No language model is involved. The earlier linear studies assemble beam stiffness matrices, solve `K u = f`, compute radius sensitivities and run constrained sizing with catalogue screening/member mutations. Here, designs are proposed by programmed continuation/Sobol rules; the solver finds stationary points of the nonlinear constrained energy and uses Hessian eigenvalues to separate minima from unstable stationary points.

Sampling/shuffling uses a fixed random seed. The algorithms are repeatable in the same software environment given the same seed and inputs. They are neither exhaustive nor globally optimal, and exact floating-point equality across machines/library versions is not guaranteed. More conventional optimization or a stronger design generator may improve the comparator. See `spatial_revision/laboratory.py:numerical_control` and `nonlinear_discovery/experiment.py:numerical`.

## Viewing the actual generated designs

The local inspection board is at **http://127.0.0.1:8767/** while its server runs; standalone HTML is `output/discovery-board/index.html`. It bundles its plotting library and data and needs no API key or network/model call to view. Source is in `discovery_board/`; the plotting dependency's license is retained in `discovery_board/vendor/D3-LICENSE`.

It currently contains the audited top three nonlinear candidates/policy and all 16 selected results from the previous linear revision study. All 48 raw nonlinear proposals remain in `benchmarks/nonlinear-discovery-v1/{numerical,meta}/result.json`; the board does not pretend every exploratory proposal has a final audit. Winning nonlinear entries use the latest 256-start evidence; the remaining audited entries use 64 starts, explicitly labeled.

Choose experiment, candidate and computed configuration. Drag to orbit, shift-drag to pan, use the wheel or +/- to zoom. Compare A/B minima and unstable stationary configurations; inspect cell heights/twists, spring connections, force/torque, eigenvalues, residuals, parameters and independent checks. Earlier linear failures remain visibly failed and their 60× deformation magnification is labeled. Geometry is generated from numerical coordinates, not an image model. The energy curve is a straight interpolation, not a physical motion, MEP or certified barrier.

Export selected JSON from the board. Open OBJ surface meshes and companion JSON for the winning A/B configurations are in `output/discovery-board/models/`, for use in Blender or another mesh viewer. Coordinates are mm; these are open visualization meshes, not watertight CAD/manufacturing solids. Editing them in another tool does not automatically validate new mechanics. This board is for inspecting evidence, not a general CAD replacement. Actual family/state/camera controls and failure labels were checked in the browser; a screenshot is saved as `output/discovery-board/board-preview.jpg`.

## Recommendation and next gate

Continue nonlinear architecture discovery as a research direction. This first candidate is more interesting than beam resizing, and it illustrates meaningful model-led proposal plus numerical falsification. Do not claim a winning project, general optimization superiority, physical savings or scientific novelty yet.

The next prospective study should use a full-range stronger numerical architecture optimizer, multiple tasks/trajectories, a better minimum-finding method (including perturbations from saddles), and explicit retention/tolerance/torque requirements. Root coverage is now an observed failure mode, not a hypothetical warning. Only after that should selected geometry be promoted to higher-fidelity simulation or hardware, with actual guide/spring routing/contact and calibrated material behavior.

Physical prototypes/experiments: **zero**. Prototype savings and human time saved: **unmeasured**. No clinical/device certification or real-world performance claim.

## Reproduce

```powershell
python -m unittest discover -s tests -p test_nonlinear_discovery.py
python -m nonlinear_discovery finalize
python research/nonlinear_discovery_figures.py
python -m http.server 8767 --bind 127.0.0.1 --directory output/discovery-board
```

These commands use saved data/numerical tools, not model calls. `finalize` regenerates the common 64-start result; the denser audit stays separately preserved. Raw query files and source snapshot are unchanged. Creating a fresh paid search requires another directory and explicit source freeze; the current `meta`/`numerical` commands refuse existing run directories. Board generation/re-export commands and source paths are in `research/build_discovery_board.py` and the visualization helper used for the standalone wrapper.
