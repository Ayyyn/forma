# Concrete frontier opportunities, researched 2026-10-30

Decision: provisionally test **Meta-authored executable optimization strategies for robust optical multilayers**. A physically measured materials experiment-selection benchmark was also implemented and tested, but the attempted feature-expert agents failed their continuation gates. Keep that negative evidence. The optical direction is a research bet, not a proven winning project or scientific discovery.

## 1. Reduce expensive compression experiments for energy-absorbing structures

Beneficiary: a mechanical/materials lab screening printed impact absorbers. Task: choose the next geometry to test to reach high measured toughness using few historical design-group reveals. Gongora et al.'s crossed-barrel study physically printed and compressed 600 designs with three replicates each. The benchmark supplies 1,800 rows; identical geometry is grouped before reveal to prevent replicate leakage. Our goal is the group mean, not the highest individual replicate. [Primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7148087/), [benchmark repository](https://github.com/PV-Lab/Benchmarking).

This is directly relevant to structures and measurable without inventing a mechanical constitutive model. We implemented two studies with raw/domain GPs, random forests, random search and an adaptive numerical portfolio. Meta proposed bounded feature hypotheses from revealed observations and received prediction-error feedback. Neither the simple feature expert nor the evidence-gated Wonder/Spark variants met the gate. No fresh geometry, new lab experiment or saved prototype is established. **Do not pitch this implementation as an AI efficiency win.** Results and source-linked plots are in `FRONTIER_SCOUT_RESULTS.md`.

The larger generalized cylindrical-shell study reports 25,387 autonomous experiments and a broader design parameterization. Its archive is CC BY-NC-SA 4.0; it is not downloaded or redistributed here. Its public GCS generator is a separate code asset. More design breadth alone is not evidence that an LLM will help. [Primary study](https://www.nature.com/articles/s41467-024-48534-4), [OpenBU archive/license](https://open.bu.edu/items/871d47cb-a12c-4ebb-8623-92df97353ea9), [generator](https://github.com/samsilverman/gcs).

## 2. Optical multilayer inverse design under fabrication variation — selected probe

Beneficiary: a photonics engineer designing a wavelength-selective filter/coating. Concrete conflict: transmit visible wavelengths while reflecting a chosen near-infrared band across incidence angle, polarization and thickness perturbations. This is a useful spectral-filter subproblem; it does **not** establish solar heat rejection, cooling power or finished-window performance.

Why feasible: exact coherent 1D thin-film equations are fast enough for thousands of queries on this laptop. Independently implemented recursive Fresnel and characteristic-matrix forms agree with external `tmm` on 1,920 randomized wavelength/angle/polarization checks. Measured dispersive material inputs are pinned from the CC0 refractive-index database. No need to fit an invented material dataset. A conventional numerical refinement already establishes a sampled feasible witness, separately labeled non-AI. [Material database and source citations](https://github.com/polyanskiy/refractiveindex.info-database), [external solver](https://pypi.org/project/tmm/).

What Meta does: write a complete bounded numerical search program, run it against an uneditable scalar oracle, inspect actual failures/query outcomes, and revise the program. This changes the search strategy rather than asking a model to guess floating-point thicknesses. The interpreter has no imports/attributes/file/network operations and keeps independent scores. Count outer program-development searches as well as inner design queries. Compare against gradient-based local search and differential evolution with the same design-query allowance.

Critical novelty boundary: LLM-generated photonic optimization algorithms are already published. Yin et al. use LLaMEA for photonic optimization, including comparison with established optimizers. We are not inventing this concept. A defensible hackathon contribution would be an attributable, working Meta implementation with a clearly measured robustness/query-efficiency result on prospectively specified tasks. Even a positive one-case probe would not establish that result. [Primary prior art](https://arxiv.org/abs/2503.19742).

Current deliberately small probe: fixed eight-layer alternating architecture, thickness search only. If executable programs work, a stronger next study can expose discrete material/sequence/layer-count choices plus fixed numerical sizing tools, with new target bands/angles held out and all development queries charged. That expansion must earn its way through benchmark results. It is not already implemented or validated.

Limitations: SiO2 dispersion is taken as lossless, TiO2 n/k is associated with a 350 nm ALD film and is transferred to other thicknesses, substrate is semi-infinite, no roughness/scatter/deposition/thermal physics. Five tolerance samples are not a certified worst case. A manufactured material or device claim requires new evidence.

## 3. Formulation substitution and structural-characterization experiment planning

Beneficiary: a formulation lab replacing an unavailable ingredient while preserving useful microstructure. NIST's Autonomous Formulation Lab combines formulation, structural measurements and agent software; this is a concrete scientific workflow, not a generic chatbot. [NIST AFL](https://www.nist.gov/programs-projects/autonomous-formulation-lab), [NIST agent project](https://www.nist.gov/publications/autonomous-agent-soft-material-structural-optimization-and-discovery), [software documentation](https://pages.nist.gov/AFL-agent/en/latest/index.html).

The selected public benchmark also supplies a perovskite instability table (139 rows, 94 grouped compositions in the pinned revision). It supports honest retrospective experiment selection, which we tested without advantage. It cannot establish performance of new unsynthesized formulations. Original work: [Sun et al., Matter](https://www.sciencedirect.com/science/article/pii/S2590238521000084), [MIT record](https://dspace.mit.edu/entities/publication/39bc0cda-20d8-4630-a04c-9a9faffd3071).

**Defer as main demo:** we have no connected lab or independently verified measurement pipeline for new recipes. Budget for model calls cannot substitute for assays or scattering measurements.

## 4. Wave/energy routing in nonlinear mechanical metamaterials

Beneficiary: engineers shaping transient energy transmission or concentration. DifFlexMM supplies differentiable rigid-unit/elastic-ligament models and established inverse-design examples. This is closer to the user's structure interest and potentially visually strong. [Primary paper](https://doi.org/10.1038/s41563-024-02008-6), [MIT-licensed implementation](https://github.com/bertoldi-collab/DifFlexMM).

**Defer pending one independent reproduction:** this turn did not install/run DifFlexMM or validate its dynamic/contact assumptions. An LLM wrapper on an unverified simulation would repeat the earlier problem. Differentiable optimization is a serious baseline; tool availability alone does not imply an AI advantage.

## 5. General truss discovery or drug discovery

Text-to-truss and LLM inverse truss design are already research areas; TrussGPT provides published prior art and a large dataset. We should not claim merely generating a truss graph is novel. [Primary paper](https://doi.org/10.1038/s41524-026-02175-x), [implementation](https://github.com/917959491/TrussGPT). We did not execute or independently validate it this turn.

Drug discovery is not selected: no assay partner, target-specific validated workflow or new experimental endpoint was established in this research. A generated molecule or docking score would not support efficacy, safety or a discovered-drug claim. No drug search/docking experiment was run.

## Budget and submission decision

Use the expanded credits for distinct algorithms, task variation and replication, not repeated unbounded attempts until a favorable plot appears. The immediate optical program probe has three requests / $10 estimated ceiling; follow-on experiments can use a separate prospectively recorded allocation within the user's larger authorization. Actual account balances/billing are unverified. Avoid complexity for its own sake: no new RL, agent team, vision pipeline or decorative UI is justified by current evidence.

The guide weights impact 30%, Meta use 25%, technical implementation 20%, demo 25%. Our selection is an engineering judgment based on verifiability and meaningful Meta control, not a prediction of judging outcome. Final submission is due Nov 4, 2026 21:00 EST (Nov 5 07:30 IST). The participant guide was supplied locally; retain it as the source of competition rules. Public-repository release still needs a dependency/data attribution review. Earlier origami/studio/CAD work remains prior work; this turn's new benchmark adapters, numerical audits and optical prototype are recorded separately. No public release or submission is performed here.
