# Kresling mechanical proof — October 28, 2026

**Recommendation: continue with a single-cell reduced-order research prototype.** The numerical reproduction gate passed. This is not a validated physical device, a demonstrated AI advantage, or a claim of a new mechanism. Keep the scope to static energy landscapes and controlled pre-stress; do not expand the old studio or build a product UI yet.

## Run and inspect

From the workspace root, using Python 3.12:

```powershell
python -m pip install -r requirements-science.txt
python -m kresling_proof all --output artifacts/kresling-proof
python -m unittest discover -s tests -v
```

The proof runs offline, without API credentials or new Meta requests, in about 90 seconds on this machine. It generates `report.json`, `RESULTS.md`, three CSV tables, and four PNG/SVG plots. The report records exact inputs, source/fixture hashes, dependency versions, classifications, failed search attempts, errors, tolerances and unresolved outcomes. It exits with code 2 if the scientific gate does not pass.

The new `kresling_proof` package is isolated from the earlier Miura implementation. Its public Python entry points are `Cell`, `AxialSpring`, `features`, `energy_components`, `energy`, `jet`, `scaled_jet`, `equilibria`, `relax_phi` and `branch_barrier`. Angles accepted by the numerical functions are radians; degrees appear only in explicitly named input/output fields. `jet` returns energy, the physical gradient and Hessian; `scaled_jet` uses q=(u/r,phi) and U*=U/(ks*r).

## Model and attribution

Base source: Zang, Misseroni, Zhao and Paulino, [Kresling origami mechanics explained: Experiments and theory](https://doi.org/10.1016/j.jmps.2024.105630), JMPS 188 (2024) 105630. An accessible [author PDF](https://paulino.scholar.princeton.edu/sites/g/files/toruqf6546/files/documents/JMPS_24_KreslingMechanics.pdf) includes the appendices.

We independently implemented Eqs. 1–9 and 14–15: two effective stretching energies and three effective rotational energies. The independent coordinates are axial compression u and additional twist phi; h=h0-u and theta=theta0+phi. End polygons remain regular and undeformed. The model is symmetric and has two generalized coordinates, not a general deformable shell mesh.

Stiffness mapping is important: k_s,b=ks/b0, k_s,c=ks/c0, and k_r,i=kr*l_i0. Both end polygons contribute their edges, so n_a=2n while n_b=n_c=n. Parameters ks and kr retain the paper's conventions. They are effective model coefficients, not newly measured material constants. Energy in N mm is numerically equal to mJ.

Pre-stress source: Zang et al., [Origami frustration and its influence on energy landscapes of origami assemblies](https://doi.org/10.1073/pnas.2426790122), PNAS 122 (2025), Eq. 5. We add U_spr=0.5*k_e*(Delta_l-u)^2 for an **enabled, bilateral ideal axial spring**. Disabling the spring removes this term. Zero reference offset with the spring still enabled adds stiffness and generally does not recover the bare cell. Some physical apparatuses in the paper disengage when unloaded; our bilateral numerical experiment does not reproduce that apparatus.

Prior art: Kang et al., [Physics-informed neural networks for programmable origami metamaterials with controlled deployment](https://doi.org/10.1039/D5MH01607J), Materials Horizons (2025), with an accessible [preprint and appended supplementary material](https://arxiv.org/abs/2508.13559). That work already addresses energy-landscape inverse design and deployment programming. Its truss/PINN formulation is a different approximation; we do not merge its normalization into the five-term model or train/reproduce its neural network.

These mechanisms, equations, frustration concepts and inverse-design objectives are established research. Our new contribution here is a source-attributed implementation, reference extraction, independent checks and reproducible numerical study built during this hackathon.

## Published results reproduced

Frozen inputs: n=6, r=30 mm, h0=39.48 mm, theta0=30 degrees, ks=50 and kr=0.005. These are the Appendix A.3 inputs, not fitted parameters.

| Quantity | Published reference | Computed |
|---|---:|---:|
| Free rotation at u=10 mm | 28.65 degrees | 28.633416 degrees |
| Free translation at phi=20 degrees | 6.33 mm | 6.321479 mm |
| Intermediate stationary compression | 12.1 mm | 12.118101 mm |
| Intermediate stationary twist | 33 degrees | 33.191799 degrees |
| Second unloaded minimum compression | 27.7 mm | 27.703482 mm |
| Second unloaded minimum twist | 55 degrees | 55.126902 degrees |
| Second minimum U/(ks*r), Table 1 | 0.0041 | 0.00405114349 |

The intermediate stationary point is a **saddle**, with dimensionless Hessian eigenvalues approximately -0.03510 and 4.78979. Its individual diagonal curvatures are both positive; a test of diagonals alone would miss the coupled instability. The implemented classification uses the full Hessian. At an imposed displacement, transverse angular stability is a separate constrained question.

Thirty comparison points were extracted from the published Figure 5A-left dashed theoretical curve before our first model evaluation. The extraction script imports no model code. Its PDF hash, color/path selection, axis calibration and uncertainty are recorded in the frozen reference JSON. This is sampled published theory, not experimental raw data.

The energy-curve RMSE is 2.917e-5 in normalized energy, or **0.20836% of the full plotted vertical range**, below the predeclared 2% limit. The source-reading uncertainty estimate is 1.2e-4 normalized energy. No curve shift, energy rescaling or parameter fitting was applied. Appendix tolerances account for the paper's rounded numbers and are separate from the much smaller solver errors.

The bare-model branch barriers are approximately **9.491911 mJ forward** and **3.415196 mJ reverse**. These refer to the declared monotonic axial-displacement/free-rotation branch, not a globally optimized transition path or a dynamic switching threshold.

## Independent checks and numerical errors

- Eighty frozen-seed random states compare production trigonometric geometry with independently constructed ring vertices and triangle normals. Maximum scaled feature discrepancy: about 1.33e-15; maximum normalized energy discrepancy: about 9.09e-16.
- Four states compare automatically differentiated gradients/Hessians with a separate 70-digit mpmath implementation. Maximum gradient discrepancy is about 5.77e-16 and Hessian discrepancy about 1.33e-15 in the chosen dimensionless coordinates. This checks the same constitutive assumptions; it is not independent material validation.
- Five-point finite-difference checks over four step sizes confirm the derivatives. Stationary searches using 5x5, 7x7 and 9x9 initial grids find the same two minima and saddle; maximum scaled coordinate difference is about 4.75e-14. This is convergence evidence, not exhaustive root isolation.
- Angular scans at 65, 129, 257 and 513 points are followed by stationary-root refinement. An early sampled-energy scan missed shallow wells inside the first angular interval. We added explicit edge-interval torque-root checks and regression tests. The free-rotation energy derivative is also checked against its predicted axial reaction.
- Boundary configurations, degenerate Hessians, nonstationary geometric states, failed solves and unresolved barriers have separate statuses. A zero-energy folded geometric boundary is not automatically called an interior mechanically stable state.

## Pre-stress findings

The original planned spring k_e=0.1*ks/r=0.166667 N/mm was retained. With this spring engaged, only one minimum is located in the declared searched domain. Changing its reference offset from 0 to 3.948 mm moves that equilibrium from approximately u=0 to **u=0.669198 mm**, with twist **2.307509 degrees**. A separate high-precision derivative check confirms the final stationary residual. Estimated numerical position uncertainty is 3e-7 mm, not a physical fabrication uncertainty.

Because that spring removes the second well in the searched domain, we additionally declared and retained a weaker-stiffness study. At k_e=0.002*ks/r=0.00333333 N/mm, two minima and an intermediate saddle remain across all 21 tested offsets:

| Weak spring reference offset | First minimum u | Second minimum u | Forward branch barrier | Reverse branch barrier |
|---|---:|---:|---:|---:|
| 0 mm | approximately 0 mm | 25.834898 mm | 9.743531 mJ | 2.475178 mJ |
| 3.948 mm | 0.013636 mm | 26.092876 mm | 9.580374 mJ | 2.653614 mJ |

The forward barrier decreases by about 1.67% over this chosen range while both reduced-model minima remain. This is a computed sensitivity result, not a novel physical discovery or measured tunability. All offsets and the broader seven-stiffness/two-offset state searches are retained, including cases without a resolved second minimum. Missing barriers are not replaced by zero.

An axial-only spring cannot change the relaxed twist at a fixed imposed u: its energy is independent of phi. It changes the energy/force along that path and therefore shifts unloaded equilibria. Tests verify this identity and the exact added axial reaction k_e*(u-Delta_l). This guards against mistakenly attributing a geometric path change to this spring.

## Data and code availability investigated

- JMPS 2024 gives explicit numerical checkpoints, reference figures and material characterization in its appendices; its raw-data statement is availability on request. We did not obtain raw experiments.
- PNAS 2025 states that study data are in the article/supporting information. We inspected the main theory; direct supplementary-file retrieval returned an access error during research. We do not claim to have reproduced its exact parameterized experimental plots.
- The Kang preprint includes supplementary equations and algorithms; its data statement says data are available on request. We did not obtain its training code or experimental data.
- [MERLIN/MERLIN2](https://paulino.scholar.princeton.edu/software/origami-mechanics) are existing nonlinear origami mechanics implementations. They are not dependencies here.
- The [Mora et al. 2025 Zenodo dataset](https://zenodo.org/records/15118000), metadata license CC BY 4.0, includes experimental data, FE inputs and a MATLAB five-parameter sizing example. We inspected, but did not execute or copy, that example. It follows a prescribed crease-length path and uses different normalization/hinge-count conventions, so its full output is not a drop-in free-equilibrium oracle. Its data describe a different material/fabrication study.

## Meaningful AI task and deterministic baseline

Propose a subsequent bounded inverse-design study: from a target stable height, branch-barrier interval and permitted spring settings, choose k_e in [0,0.035] N/mm and Delta_l in [0,3.948] mm while retaining two verified reduced-model minima. The forward kernel, not Meta, decides whether the target is met. Targets must explicitly specify their loading protocol and distinguish unknown/unsupported requests from demonstrated infeasibility.

Use a deterministic baseline with 36 grid evaluations and 28 bounded local-search evaluations, charging every complete landscape solve, including failed/invalid proposals. Meta receives the same bounds, equations, feedback and 64-evaluation allowance. Freeze held-out targets before prompting, and compare success, target residual, preserved constraints, elapsed time and actual token usage. Hidden feasible-target witnesses stay outside model context. No Meta calls have been made for this study.

This two-parameter numerical problem may favor conventional optimization strongly. An LLM merely selecting two numbers would not establish a compelling contribution. A more substantial later task is selecting discriminating force/torque tests among competing reduced-model hypotheses from sparse observations, with a greedy information-gain baseline. Initially those observations would be labeled simulations; calling them physical experiments would be false. Neither task has yet been implemented or benchmarked.

## Limits and decision

Minima are stable only with respect to the modeled symmetric coordinates and boundary assumptions. Panel buckling, non-axisymmetric deformations, self-contact, finite-thickness clearance, plasticity, viscoelasticity, dissipation, friction, fatigue, damage and dynamic snap-through are unsupported. The ideal pre-stress spring is not a calibrated fabricated assembly. The results do not establish force accuracy for arbitrary paper/plastic samples, controllable physical deployment sequences or manufacturability. The numerical geometry functions also do not certify a flat-foldable or manufacturable crease pattern for arbitrary input parameters; the published reference case is the validated reproduction target.

**Go:** the reduced-order numerical model is sufficiently supported to continue a small mechanical-behavior research prototype. **Simplify:** stay with one cell and ideal axial pre-stress; omit multicell sequence claims, neural-network training and a general product studio. **Unproven:** practical physical validity, useful AI assistance and hackathon competitiveness. Test the AI task against a strong numerical baseline before building a presentation layer. A failed future gate must be reported rather than rescued by a decorative animation.

The final submission deadline remains November 4, 2026, 21:00 EST / November 5, 07:30 IST. All new implementation and numerical results here were created during the hackathon, with established science attributed. The earlier origami/CAD directions are retained as earlier work, not relabeled as this contribution.
