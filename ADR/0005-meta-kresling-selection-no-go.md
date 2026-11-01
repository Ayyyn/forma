# 0005 — Do not center the hackathon demo on Meta Kresling test selection

Date: October 28, 2026. Status: accepted on the frozen experiment's declared rule.

The user asked for a fair empirical test of whether Meta adds value before further building. We implemented closed-world sequential virtual experiment selection, with a common Bayesian estimator and four charged measurement slots. Its main comparator exhaustively maximizes greedy Bayesian information gain across all available tests; fixed four-corner testing is a secondary control. Protocol and source were frozen before scored execution.

Across 48 matched cases/16 mechanical clusters, real Muse Spark Open decisions reduce mean step-1..4 true-model NLL by 1.48% (0.292730 to 0.288408). The paired cluster interval for EIG-minus-Meta loss is [-0.084874,+0.089728] nats, failing both the frozen 10% effect-size and positive-interval requirements. Final identification is 46/48 for Meta, 44/48 for EIG, and 46/48 for fixed testing. All transports complete, but eight Meta rounds hit the output-token limit without selecting a test. Median case time is 73.776 seconds for Meta versus 2.879 seconds for EIG, plus EIG's one-time 17.276-second cached prior calculation. There were 192 actual API calls, with estimated reported-usage cost $4.43.

Decision: retain the verified mechanical solver and evidence archive; do not expand a Meta-led test-selector product, canvas, branding or generic CAD interface as the main hackathon concept. A working model and correct numerical mechanics have not demonstrated a compelling incremental AI benefit. A positive secondary count is insufficient when a fixed control matches it and the primary gate fails.

All raw runs are retained. Replays cover all 144 cells/576 attempts/568 observations. Independent inference, higher-order checks of all 192 EIG choices, independent 320-pose reaction checks, and 56 tests pass. These are numerical checks of a synthetic likelihood and published reduced model, not hardware/material validation. No broader claim that all AI experiment selection is useless is justified.

See `docs/KRESLING_META_VALUE.md` for the decision, limits, costs and exact reproducibility commands; `docs/KRESLING_BENCHMARK_PROTOCOL.md` for prior design; `benchmarks/kresling-selection-v1/` for immutable scored evidence. Any new task or settings must have separately preserved prospective evaluation; this result must not be overwritten or pooled away.
