# What has actually been checked

The numerical implementation, a model's explanation, and a physical object's behavior are different evidence layers. No model explanation is used as a feasibility verdict.

## Software and mathematical evidence

`benchmarks/audit-geometry.json` records a reproducible independent audit (seed 20261027):

- 40 randomly selected Miura designs/poses, beyond the original demo candidate.
- Comparison against the original Schenk–Guest unit-cell equations in their unsimplified form using 70-decimal-digit arithmetic. Maximum relative discrepancy from the production floating-point implementation: about 3.62e-15.
- A separate nonlinear solve of rigid edge-length, fixed dot-product and projected-area constraints. It does not call the production unit-cell function to construct the solution. Maximum normalized constraint residual: about 1.83e-13.
- Shapely polygon unions compare the sum of projected facet areas with their union. Maximum absolute difference is about 2.91e-11 mm², numerical noise below the 1e-7 mm² audit threshold. This checks sampled states; the continuous nonintersection argument is in `GEOMETRY.md`.
- Six deliberately corrupted metric records (omitted boundary overhang, unit scaling, fabricated material area, wrong feasibility, wrong crease count, wrong constraint flag) are all detected.
- The original recorded demo selection independently agrees to about 2.84e-14 mm in extent and 1.46e-11 mm² in material area.

The unit/API suite additionally checks known flat/accordion configurations, all facet pairwise distances including diagonals, coplanarity, projected area by polygon integration, disk topology, Maekawa crease counts, an independently known mountain/valley ridge orientation, invalid/singular input rejection, impossible requirements, reproducibility, print units, and exported geometry consistency. Benchmark tests cover charging invalid/duplicate proposals, blocking overspend, absence of a planted feasible seed, scoring without trusting model claims, and the corrected accordion region schema.

Every valid benchmark proposal is compared with an independent scoring oracle. The report generator also replays every recorded attempt from its stored parameters and checks the saved best candidate against recomputation. A disagreement is a harness failure, never an AI success. Raw provider model IDs, response IDs when available, token usage, public tool arguments, computed feedback and source/manifest hashes are retained. Private reasoning text and API keys are not retained.

Source: [Schenk & Guest, Geometry of Miura-folded metamaterials, PNAS (2013)](https://doi.org/10.1073/pnas.1217998110). The mechanism and equations are established research, not a new invention claimed by this project.

## Problems the audit found

The prototype's default search includes a known reference design, and its agent originally had tool-call rather than shared candidate-evaluation limits. Those demonstration runs are therefore not comparative evidence. The controlled benchmark uses an independent evaluation ledger and no known feasible seed.

Benchmark v2 rejected accordion-specific angle/row fields that its sampler ignored. V3 corrected the schema and retained the full earlier pilot. V3 also reported zero reasoning tokens on forced-function calls. Unscored transport probes found reasoning on the automatic-tool route and verified a sufficient output allowance; v4 froze that route. V4 then suffered a transient DNS/timeout interruption. V5 retains the same reasoning configuration and full task matrix, extends the per-request timeout, and keeps all previous runs separate. Results from interrupted or superseded conditions must not be pooled into a favorable headline.

These are meaningful integration problems, not excuses to discard inconvenient design outcomes. Frozen protocols, raw cells and version-specific summaries retain the evidence.

## What remains unverified

- Real paper folding, material thickness and self-contact clearance.
- Crease torque, fatigue, bending, springback, self-locking, strength or load capacity.
- Manufactured tolerances and agreement with physical measurements.
- General origami solving, arbitrary mechanisms, container closure or usable capacity.
- Whether deployed bounding extent constitutes a useful real product surface for a particular use case.
- Whether a model's public rationale is wholly correct. Only its numerical proposals and the independently recomputed constraints are automatically checked.
- API billing balances and exact dollar charges. Published-rate estimates are labeled estimates.
- Broad model superiority. The benchmark has a small number of related tasks in one engineered domain, not a representative invention benchmark.

Passing these checks supports correctness of this **ideal mathematical mechanism model**. It does not justify saying that a physical product has been validated or that AI adds value unless the relevant comparative results support that claim.
