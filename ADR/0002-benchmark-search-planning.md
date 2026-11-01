# 0002 — Evidence favors one-pass planning for the tested parameter-search role

Date: October 27, 2026 (India). Status: implemented as the prototype's default at the user's request after the benchmark.

Evidence: final protocol v5 runs six tasks × three seeds × three methods, with exactly 64 candidate attempts for every run and the same numerical sampler. Across 15 feasible task instances, both Meta policies attain feasibility in all 15, versus 12 for constructive adaptive numerical search. The single-pass planner beats the feedback policy in 12/15 declared lexicographic objective comparisons. On the primary metric alone the comparison is single pass 8 wins, agent 1 win, 6 ties. Median run latency is about 23.9 seconds for single pass and 26.4 seconds for the agent, versus 0.18 seconds for the numerical baseline. Published-rate API estimates for all 18 runs are approximately $0.59 and $0.85 respectively; actual charges are unverified.

Decision: use one-pass Meta search-region planning plus deterministic evaluation as the default for this bounded parameter-search stage. The API and studio use one actual request followed by 64 charged attempts, numerical selection, independent scoring and rigid-geometry verification. The older loop remains an explicit API option for recovery experiments. There is no automatic fallback. Contract tests and actual run `ebd847afdf79` verified the default integration; the wider benchmark remains unchanged.

Limits: five related feasible tasks with three repeated seeds provide narrow evidence, not a general superiority result. The numerical baseline is adaptive and informed by exact geometry, but other optimizers may be stronger. This benchmark includes no physical measurements, topology invention, or novel mechanism discovery. Additional independent task families and numerical baselines remain necessary.

Provenance: preserve the schema pilot, forced-call/no-reported-reasoning condition, transport probes and interrupted network batch separately. The final result is a whole-matrix retry with observed reasoning telemetry, not a selection of the best cells from different versions. All final numeric ledgers replay and agree with the independent oracle.

Completed geometry, constraint checks, fabrication exports, API adapters, evidence traces and the exploration UI remain useful. The project vision is unchanged; the responsibilities and evaluation of its model component are becoming more precise.
