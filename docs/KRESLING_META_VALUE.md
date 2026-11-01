# Does Meta add value to Kresling experiment selection?

**Recommendation: do not continue Meta-led experiment selection as the main hackathon project.** The mechanical implementation remains a useful, numerically checked research asset. This experiment does not establish a sufficiently strong reason to put an AI selector at its center, or a compelling hackathon application. Do not expand the canvas, branding or generic CAD features on the strength of these results.

## What was tested

An actual Meta model selected four virtual paired force/torque tests to identify an unknown Kresling mechanical hypothesis, with unknown fixed calibration offset and noisy observations. This provides a sequential decision task in which planning could help beyond direct low-dimensional parameter optimization.

We froze the source, catalogue, priors, noise, model settings, 48 matched cases, primary metric and decision rule before running either the scored controls or Meta. The main comparator enumerates all 12 tests and maximizes Bayesian expected information gain about the mechanical model, marginalizing calibration. This is a strong greedy numerical baseline, rather than a globally optimal four-step policy. A fixed four-corner test sequence provides a secondary control.

Each policy has four charged slots. Repeats and invalid proposals consume slots. They share the same full mechanical prediction catalogue and Bayesian estimator. Identical test/replicate choices receive identical potential observations. Meta gets neither the baseline's information scores nor hidden truth, future noise, held-out scores or previous cases. Compute and money are recorded separately from the equal measurement allowance.

## Full result

| Method | Mean true-model NLL over steps 1–4, lower better | Final correct | Correct with at least 90% posterior by final step | Confidently wrong | Median seconds/case |
|---|---:|---:|---:|---:|---:|
| Bayesian information gain | 0.292730 | 44/48 | 35/48 | 1/48 | 2.879 |
| Fixed four-corner tests | 0.602248 | 46/48 | 32/48 | 1/48 | 0.00116 |
| Meta | 0.288408 | 46/48 | 35/48 | 1/48 | 73.776 |

Meta's primary loss is **1.48% lower**, a difference of **0.004322 nats**. The paired mechanical-cluster bootstrap 95% interval for baseline-minus-Meta loss is **[-0.084874, +0.089728] nats**. It spans zero widely. With 16 fixed mechanical clusters and three noise seeds per cluster, this does not demonstrate consistent improvement. It also falls short of the frozen 10% relative-improvement requirement.

Meta's final identity count is two higher than EIG's, but the fixed four-corner control also identifies 46/48. That positive secondary result does not establish AI value. Both Meta and EIG attain correct 90% confidence in 35 cases; both have one confidently wrong case. Meta's held-out response RMSE is 0.068637 in declared-noise units, versus EIG's 0.076545 and fixed testing's 0.065477. These are descriptive secondary outcomes, not substituted success criteria.

All 48 Meta cases completed transport. **Eight of 192 decisions (4.17%) reached the 8192-token output limit without a usable experiment choice.** Those rounds remained charged and retained their previous beliefs; there was no retry, fallback, replacement or exclusion. Meta produced 184 actual virtual observations versus 192 for each control, within the same four-slot allowance. Reliability passes the declared 5% ceiling but is still a demo concern.

The deterministic median excludes a separately reported **17.276-second shared initial-prior calculation**, cached across the 48 identical initial public states. EIG's summed case times plus this setup average 3.239 seconds/case; Meta averages 73.582 seconds/case. Timings are local run measurements, with two workers and ordinary machine variability, not a controlled hardware benchmark. The extra latency is material even after accounting for the setup.

## Actual calls and cost

Model: Baseten `meta-models/muse-spark-open-1026`, automatic tool choice, requested medium reasoning, temperature 0.2, maximum 8192 output tokens/decision, 180-second timeout, one request/decision, two workers. No prompt or model-setting changes were made after seeing scored outcomes.

There were **192 actual API calls**, 192 distinct provider response IDs, and usage records for all 192 responses. Every response reported reasoning tokens. Reported totals: 1,528,475 input tokens, including 1,083,008 cached input tokens; 874,079 output tokens, including 849,292 reasoning tokens. Public tool arguments and transport metadata are retained; private reasoning text and credentials are excluded.

Estimated reported-usage cost: **$4.43**, using [Baseten's generic published rates](https://www.baseten.co/library/muse-spark-open/) checked October 28. Actual promotional-credit deductions and account balance are unverified.

## Verification and scientific limits

- All **144 saved cells**, **576 charged actions** and **568 valid observations** replay, including public API request hashes, selected actions, potential observations, posteriors and scores. No overspend or selectively missing cases.
- A separate multivariate-Gaussian density calculation independently recomputes all 144 cells. Maximum posterior discrepancy is 4.44e-16; maximum step/mean NLL discrepancy is 1.34e-15; maximum standardized prediction-RMSE discrepancy is 1.90e-12.
- All **192 baseline decisions** were checked with higher-order 35-by-35 quadrature. Maximum order-25/order-35 score discrepancy is 0.0002175 nats. The largest selected-test information regret at order 35 is below 3e-15 nats: no materially different baseline choice.
- Candidate and held-out reactions at all **320 mechanical poses** agree with independent vertex-energy finite differences: maximum force discrepancy 5.53e-10 N, maximum torque discrepancy 4.41e-9 N mm.
- All **56 software/reference tests** pass. The first sandboxed full regression invocation stalled at local API tests and was interrupted; the complete suite passed outside that restriction. No live Meta outcomes were retried because of this test-environment issue.
- All five frozen earlier benchmark source hashes and all ten mechanical-proof source hashes remain unchanged.

These checks establish implementation and scoring consistency for the declared reduced model. **They do not establish physical validity.** Every observation is synthetic, generated by the same constitutive model assumed by inference. Calibration profiles and noise levels are declared assumptions, not sensor measurements. Each mechanical identity is tested with only three of nine calibration profiles, not a full calibration factorial. The interval is conditional on this fixed catalogue, not a broad population of mechanisms.

The tests hold compression and twist simultaneously and read their generalized reactions. They are not equilibrium measurements, free-rotation deployment tests, or proofs that these poses are mechanically stable. The earlier energy/Hessian proof makes that distinction separately. Contact, panel buckling, plasticity, fabrication variation, model discrepancy and unknown material laws remain unsupported. Real actuator/sensor feasibility and costs have not been demonstrated.

## Decision

The predeclared decision gate fails on primary-effect size and uncertainty; it passes final accuracy, invalid-action rate and transport completion. The result is **no demonstrated Meta selection advantage**, not proof that every Meta model, prompt, inverse-design method or experiment-selection problem will fail.

Keep the reduced-order solver, published numerical reproduction and benchmark as reusable evidence. **Shelf this AI-selector demo as the hackathon centerpiece.** There is currently no demonstrated sample-efficiency or workflow gain that justifies its added latency and cost. More UI work would not resolve that evidence gap. Continuing this particular concept would need new external evidence of a useful problem where numerical design methods lack essential information, plus a fresh benchmark frozen before testing—not merely more settings tried until one looks favorable.

Established Kresling mechanics, inverse design, multistability and Bayesian experimental design are prior art. Our contribution is the October 28 implementation, numerical reproduction, explicit measurement protocol, fair comparator and transparent negative/uncertain AI-value result. This is useful research hygiene, but is not itself a new mechanical principle or evidence of a winning hackathon product.

## Reproduce and inspect

```powershell
python -m unittest discover -s tests
python -m kresling_bench summarize
python scripts/audit_kresling_selection.py --baseline-only
python scripts/audit_kresling_posteriors.py
```

These commands reproduce the offline report/audits; they do not make new Meta calls. The higher-order numerical audit takes several minutes. Paid provider generation is stochastic even with a supplied seed; the saved outcomes are exactly replayable, while fresh API generations need not be identical.

Protocol: `docs/KRESLING_BENCHMARK_PROTOCOL.md`. Frozen manifest, catalogue, every raw cell, usage, CSV tables, PNG/SVG plots and numerical-audit hashes: `benchmarks/kresling-selection-v1/`. The manifest was frozen at **2026-10-28 09:02:22 UTC**, before scored execution. Post-run audits are explicitly additional verification and do not alter the frozen score or success rule.
