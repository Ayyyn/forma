# Structural discovery experiment — first cross-family development pilot

October 29, 2026. The user's objective is broader than origami or actuators: find structures meeting exact requirements, optimize them, and measure whether AI assistance improves design quality or experimental efficiency. They prefer motion/programmed response as the first application while remaining open to supports and device/instrument structures.

This first implementation tests **small-motion passive compliant structures and static frames**. It is a tractable numerical testbed, not the full problem. The architecture separates requirements, allowed structural language, physics, numerical tools, the Meta controller, and independent verification. Additional physical families need their own verified model adapters; the existing Kresling proof is preserved separately. A material, medical device, arbitrary 3D mechanism or nonlinear actuator cannot be evaluated honestly by relabeling this linear frame model.

## First experiment

Four public, synthetic development tasks on the same ground graph:

1. Positive cross-motion: an x-directed end load must cause a specified positive y response, with bounded x/y compliance. Minimize the member-volume proxy.
2. Stiff/light support: meet x/y compliance bounds with low volume.
3. Directional flexure: stiff along x and deliberately compliant within a y compliance band.
4. Reserved channel: preserve a central finite-width keepout while meeting compliance requirements.

These represent motion transfer, supports and layout-constrained device structures. They are not patient-specific, clinically validated or medical recommendations. The supplied participant guide prohibits AI-generated medical advice; this work remains generic mechanical research. Medical-device applications would require additional task-specific physics and evidence.

The current structural language has nine possible 2D nodes and 18 allowed beam edges. The model may select named conventional templates **or propose new edge subsets**, then optimize each member's in-plane width. Templates include straight beams, offset frames, dual rails, triangular bracing and ladder networks. All left nodes are clamped where used, and the right-center node is the load/output port. Crossing unjoined beams, disconnected graphs, insufficient minimum widths, excessive width/length ratios and keepout intersections are rejected. New graphs remain candidates inside this bounded language; we do not claim new-to-science structures or arbitrary topology discovery.

## Mechanical model and checks

Independently implemented linear, in-plane, rigid-jointed Euler-Bernoulli frame elements, with axial and bending contributions. Generic E=2000 N/mm², out-of-plane depth 3 mm; layout span 40 by 20 mm, widths at least 0.4 mm, at most 2 mm and at most 0.1 times member length. Layout span describes the centerline grid, not a certified external CAD envelope. Material coefficients are declared synthetic, not calibrated properties or validated yield limits.

The two compliance columns come from separate unit x/y loads. Actual diagnostic loads are 0.01 N. Reject candidates exceeding declared nodal translation, rotation or nominal member-strain guards under those loads. Compliance sizing is constrained through analytic adjoint derivatives; the other physical-domain guards are candidate rejection checks. Nominal beam-end normal stress excludes joint concentrations. No shear-flexible, nonlinear, fatigue, fracture, contact or loaded-buckling validation is claimed. The volume objective sums member volumes, including ideal-joint overlap; it is a proxy, not exact manufactured mass.

Formulation reference: [TU Delft Euler-Bernoulli elements](https://teachbooks.tudelft.nl/computational-modelling/structural_linear/euler_bernouilli.html). We implement the standard closed-form axial/bending element. A separate oracle constructs stiffness through Gauss integration of axial strain and Hermite curvature energy, then assembles/solves independently. No source code from the tutorial or external optimization packages was copied. Classical topology optimization is established prior art: [DTU TopOpt](https://www.topopt.mek.dtu.dk/apps-and-software/a-99-line-topology-optimization-code-written-in-matlab). Our control is a bounded graph portfolio, not a reproduction of the SIMP continuum algorithm or a global-optimality guarantee.

Before paid execution, the numerical gate checks analytic cantilever displacement/rotation, subdivision invariance, energy/work identity, reciprocity, equilibrium, rigid-frame covariance, independent energy assembly over all eight template topologies, and analytic width sensitivities against finite differences. It also checks graph rejection, clearance, optimizer internal accounting, corrupted-output rejection and public tool-result history. Later report generation independently checks every valid evaluated candidate, not just successes, as additional offline audit work unavailable to the search policies.

## Compared systems

- **Numerical portfolio:** screens eligible topology minimum/maximum width extremes, prioritizes constrained SLSQP sizing using analytic gradients, refines incumbents and adds/removes graph edges beyond the initial templates. Seeded exploration; same physics and optimizer as Meta. This is a meaningful automated control within this language, not the best possible structural optimizer.
- **Single-pass Meta:** one real request selects a fixed optimizer portfolio. It receives the exact task/geometry/contract. The shared optimizer executes each plan; there is no subsequent model feedback.
- **Meta tool agent:** can optimize a template/custom graph, evaluate a proposed graph, inspect computed gradients/constraint margins, obtain a rendered view of actual geometry, and continue after feedback. At most six requests. Numerical operations happen in tools, rather than mentally reconstructing stiffness from a huge table. Public tool results return in the proper conversation history.

All methods have at most **96 charged search slots**, with a separately counted common final independent oracle check. Every new parameter sample within optimization consumes a slot, including invalid candidates. An exact cache hit is free and logged for all methods. The two load cases and analytical adjoint sensitivities reuse each candidate factorization; they do not conceal extra candidate samples. Additional model tokens, API requests, images, time and money are reported separately. Search may finish with unused allowance.

An invalid/truncated model decision is recorded, can consume a search slot, and may receive explicit corrective feedback within the original request ceiling. This is a predeclared reliability behavior, not an invisible retry. HTTP/transport failures are saved without provider fallback or resampling. Final winner selection is the same deterministic feasible-first/minimum-volume rule for every method; Meta does not judge its own success or change requirements.

Model: actual Baseten `meta-models/muse-spark-open-1026`, automatic tool choice, requested medium reasoning, temperature 0.2, 8192-token output cap per request, 180-second timeout, two worker threads. Keep public tool arguments, received provider identities, input hashes and usage. Do not store private reasoning or credentials. Images generated but never transmitted in a later request must not be counted as model visual input; the ledger distinguishes queued views from transmitted images.

## Interpretation and provenance

The matrix is four development tasks × two seeds × three policies = 24 cells. All task feasibility was checked numerically during development before the manifest freeze; those diagnostic candidates are not injected into any run or counted as scored outcomes. This is an exploratory capability pilot, **not held-out confirmatory evidence**. Freeze source hashes/settings before the paid pilot, preserve every outcome, and use a separate version if integration changes are needed.

Report verified feasible completion, paired per-task volume proxy, first feasible charged/actual solve index, total search/solver work, wall time, actual API identities/usage, graph novelty relative only to the named templates, and replay/oracle discrepancies. Do not select a winner by averaging unlike tasks' raw volumes, or infer statistical superiority from eight runs on four known tasks. This pilot is not an ablation establishing that images or any particular added tool caused improvement.

Physical prototypes built: zero. Physical experiments: zero. **Physical prototypes avoided and human experiment time saved are not measured.** Fewer numerical model calls would be evidence of simulation efficiency within this testbed. It cannot be relabeled as measured manufacturing or clinical benefit. To test those later, connect a real experiment/cost ledger and evaluate on previously unseen requirements, loads and geometries with model discrepancy.

Commands: `python -m structure_lab verify`; `python -m unittest discover -s tests -p test_structure_lab.py`; `python -m structure_lab freeze`; paid execution via `python -m structure_lab run`; offline replay/report via `python -m structure_lab report`. Existing cells cannot be overwritten, and source drift is rejected. New implementation is dated October 29; previous applications and frozen scientific results remain separately attributed and intact.

## Integration correction before the retained v2 run

The first development batch (v1) completed and is retained with its raw provider records, numerical report and exact source snapshot. A post-run permutation check exposed an optimizer integration error: unsorted custom edge lists could receive analytical derivatives in sorted storage order, mismatching optimizer variables. One recorded custom optimizer call in `directional_flexure-202-tool_agent` exercised noncanonical order. Independent candidate mechanics remained valid, but that call's optimization trajectory/efficiency cannot support capability comparisons.

The correction canonicalizes optimizer edges and their associated starting widths together, and adds an explicit edge-permutation regression test. **v2 repeats the entire same matrix for every method**, with identical tasks, budgets, prompt, tools and numerical strategy. It is a new exploratory development version; do not pool versions, replace only the affected case, or attribute stochastic model-output changes solely to the bug fix. v1's `INTEGRATION_ISSUE.json` records the issue and source provenance. All original sources are saved under each version's `source/` folder. The current CLI defaults to v2; v1 can be replayed from its source snapshot with an explicit absolute `--directory` path.

## Provider encoding adaptation — retained v3 development run

v2 also completed and is preserved. Received provider outputs exposed a second integration limitation: some actual commands appear as ATEM XML or an exact single-plan JSON object in public assistant text rather than native `tool_calls`. The source now normalizes those observed encodings conservatively, retains the original received public output, records the encoding, and validates commands against the same tool names and Pydantic argument schemas. Local normalized invocation IDs are labeled as local; provider response IDs remain the actual received IDs. Arbitrary JSON is not guessed into an adaptive action, XML entities/declarations and unknown invocations are rejected, and no text is evaluated as code. This decoder is tested on native/XML/JSON semantics and malformed inputs.

The arbitrary eight-item portfolio-list cap is removed: a plan may contain up to 96 items but their allocations still must fit the same 96-slot total. Both plan and adaptive pipelines receive the shared protocol adapter. There is no increase to candidate budget, change to mechanical requirements, or hidden numerical seed. The complete matrix is rerun as **v3**, the current CLI default. v1/v2 are integration diagnostics, not pooled capability evidence. This development sequence establishes a usable system interface; a future held-out experiment is still required for a general AI-value conclusion.
