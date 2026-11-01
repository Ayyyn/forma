# Frozen benchmark protocol v5

Question: does Muse Spark Open add value when choosing design-search regions in this restricted, ideal panel model?

This tests the studio agent's **search-planning role**, with a controlled three-turn policy. It does not benchmark unrestricted geometry invention, direct model arithmetic, or the exact unbounded search allowances of the original demo. Numerical work is delegated to the same sampler and evaluator in all methods.

## Before observing model results

`scripts/run_benchmark.py --freeze` writes the task definitions, seeds, objectives, source SHA-256 hashes, model, output-token caps and pricing reference to `benchmarks/protocol-v5.json`. It refuses to overwrite the manifest. Execution checks source hashes and writes one cell per task/seed/method; resuming never replaces an existing cell. Five feasible tasks have checked witnesses constructed offline solely to verify task labels. Those witnesses and prior demo candidates are never passed to the methods. One infeasible task has an analytical certificate: deployed y cannot exceed flat y, but it requires 220 mm from a blank limited to 190 mm.

The initial v1 manifest was superseded **before any model benchmark execution**: review found that descriptive task IDs could reveal the impossible-task label. V2 sends models only an opaque case token, the actual requirements and the objective. V1 is retained for provenance and has no result cells.

Tasks: tight pocket, generous pocket where accordion is possible, shallow packet, restricted crease count, larger surface with material-first objective, impossible blank width. Three fixed seeds (101,202,303) give 18 task instances and 54 method runs. This is a small engineering benchmark, not a broad model capability evaluation. Tasks are variations in one known mechanism domain; the developer's prior knowledge is a limitation, not a claim of held-out real-world generalization.

## Equal candidate-evaluation allowance

Every method gets **64 candidate attempts**, including the same charged initial accordion evaluation. Invalid candidate dimensions and duplicates consume attempts; no rejection resampling. No planted feasible seed. The initial candidate is common information, not an extra free evaluation.

- **Deterministic adaptive search:** three batches of 21 proposals. The first uses the full domain, pruning accordion only where its retained-width constraint proves it impossible. Later batches narrow around the best evaluated design; no LLM calls.
- **Single-pass Meta planner:** one real model call chooses one region for all 63 remaining proposals. It sees the same initial evaluation but receives no feedback before choosing the full region. This is stronger than a single unsupported geometry guess: a one-shot plan plus 63 actual numerical evaluations.
- **Feedback Meta agent:** three real planning turns, 21 proposals each, with actual constraint feedback between turns. Same model, provider, geometry facts, tools, sampler, operating-angle domain, and objective as single pass.

The methods use the same inverse construction to meet deployed dimensions: sample grid, sector angle and packed angle; solve facet a/b from target deployed extents with 0.5–6% oversize. This mathematical engineering knowledge is given to both model policies. It is not extra uncounted candidate scoring. The sampler never checks packed metrics to discard proposals. Every generated candidate reaches the ledger before schema validation. A malformed model plan or provider failure leaves unused budget and is retained as a failed/incomplete run; there is no hidden deterministic fallback or retry.

The single pass has a 49,152-output-token cap; the agent has three 16,384-token caps, the same total maximum. Both request medium reasoning effort with automatic tool choice. Actual input/output tokens, latency and estimated cost are reported separately. Equal evaluations do not imply equal runtime or spending. Fixed seed/temperature do not guarantee deterministic hosted-model responses; saved traces enable replay of the observed proposals without claiming identical model regeneration.

## Scoring and anti-hallucination checks

All methods receive an evaluator-selected best-observed candidate, not credit for a model claiming success. Feasibility is primary. Four feasible tasks minimize crease segments, then material, then packed area; the larger-surface task minimizes material, then creases, then packed area. Invalid candidates never win. For failed searches, normalized constraint violation is reported rather than fabricating an objective value. The impossible task is scored separately from feasible-task attainment.

Every valid evaluation is rechecked by an independently written oracle using the original unsimplified unit-cell equations, mesh bounds and polygon material area. These post-evaluation audit computations are common to all methods, do not produce proposals, and do not grant additional optimization feedback. Any disagreement aborts the cell as a harness error. Separate audit tests compare 70-digit arithmetic, a nonlinear distance/dot/area constraint solve, projected polygon-union overlap, and injected faulty metric records.

Prespecified outputs: feasibility attainment across the 15 feasible task instances; per-task outcomes and objective values; completed runs, valid/unique/duplicate attempts; budget usage; API errors; input/output tokens; latency; approximate dollar cost. Agent-versus-baseline and agent-versus-single-pass comparisons use paired task/seed cells, showing feasibility wins/losses/ties and conditional objective comparisons only when both are feasible. No failed run is silently discarded. Uncertainty uses task-cluster resampling where feasible, and is labeled unreliable with only five feasible tasks. No result is treated as proof of physical correctness or novel invention.

The geometry model assumes ideal, zero-thickness rigid facets. Paper thickness, real crease deformation, stability, load capacity, and experimental correspondence remain unverified.

## V3 correction and retained pilot

All 54 v2 cells are retained under `benchmarks/runs-v2/`. Inspection found that accordion physical values (gamma=90, rows=1) were rejected by a generic Miura region schema, even though those fields were ignored by the accordion sampler. V3 canonicalizes ignored accordion bounds and documents the conditional field meanings. It also returns invalid-plan feedback within the original three agent turns rather than terminating immediately; the final existing turn may spend any unspent evaluation allowance. There are no extra model turns, silent retries or candidate evaluations. The full matrix is rerun, including deterministic controls; v2 and v3 are never pooled or selectively substituted. Hosted model nondeterminism means differences between versions cannot be attributed solely to this correction. V3 also records provider response IDs.

## V4 reasoning-route audit

All 72 forced-tool model responses in v3 reported zero reasoning tokens, unlike the automatic-tool route used in the working studio demo. Four unscored transport probes varied forced/automatic tool choice and provider-default/requested-medium effort. Forced calls reported zero reasoning tokens; automatic calls reported reasoning but exhausted a 4096-token allowance. A larger unscored medium-effort probe completed a tool call with 5873 reported reasoning tokens; low effort also returned a tool call with reasoning. A separate fixed-marker request verified that a 49,152 output-token cap is accepted. No candidate outcomes were scored in these configuration probes. V4 freezes automatic tool choice, requested medium effort, the same 49,152 total output-token ceiling for both model methods, and no arbitrary small character limit on optional public rationale text. Every task, seed, candidate budget, sampling rule and objective remains unchanged; all 54 cells are rerun. Earlier conditions are diagnostic results, not pooled into the final table. The request and usage logs establish observed route behavior; they do not reveal the provider internal implementation.

## V5 complete infrastructure retry

V4 was interrupted by network failures: 32 DNS errors and three request timeouts, with only one successful scored model run. These are not interpretable as a capability comparison. A fresh independent DNS/HTTPS check succeeded. V5 reruns the entire matrix at lower request concurrency (two workers) and extends the per-request read timeout from 60 to 180 seconds. Model, reasoning request, tool choice, output-token ceilings, tasks, seeds, sampler, scoring and evaluation budgets are unchanged. V4 cells remain untouched and separate. There are no per-cell automatic retries or selective replacements in v5.
