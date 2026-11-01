# Frontier scout: measured-data tests and optical feasibility

2026-10-30. Research milestone, not a new-material or new-to-science claim. All data, failures and numerical baselines remain available. New physical experiments: **zero**. No measured prototype/time savings.

## Measured-data experiment selection

Pinned [PV-Lab benchmark](https://github.com/PV-Lab/Benchmarking) commit `7585c517ad88e676c42c6bf24a8ad278e01ddb21`. Selected tables: printed crossed barrels (1,800 measurements / 600 identical-geometry groups), AutoAM print-shape calibration (100/100), perovskite instability (139/94). Counts reflect this exact revision. Group mean is the objective; variance and replicate count are revealed together. Unequal groups do not represent equal physical replicate counts.

Every episode reveals eight initial groups, then chooses 24 more; all methods see the same public input pool and per-seed initial groups. Hidden outcomes are used only by the oracle and offline scoring. Tests change hidden values and verify controller choices stay unchanged. The normalized simple regret is `(pool_best - best_observed)/(pool_max - pool_min)`, with objective sign handled for minimization. Primary score is its mean at reveals 9–32; lower is better. Random search, raw Matern-ARD GP/EI, random-forest EI and hand-derived domain-feature GP/EI are numerical controls. No global-optimality claim.

The Meta role is to propose at most six finite expression features through a bounded schema, using all revealed observations and past prediction errors. A shared GP/EI engine then chooses experiments. This is meaningful hypothesis representation, but restricts the model's agency; a failure here is not evidence that all AI experiment planning fails. Raw features always remain.

### Study A: one feature expert, v2

Five policies × three tables × four seeds = 60 episodes. Seeds 31,47,71,97. Results:

| Policy | Mean normalized regret | Final top-5%-of-pool hit episodes / 12 |
|---|---:|---:|
| Random | .105516 | 11 |
| Raw GP/EI | .072672 | 12 |
| RF/EI | .070903 | 11 |
| Domain GP/EI | .081307 | 11 |
| Meta feature GP | .089794 | 12 |

Wonder: 36 genuine HTTP200 responses with unique provider IDs/usage; 35 accepted complete feature plans, one truncated/incomplete command. Estimated usage cost **$2.8797648**, billing unverified. The preregistered exploratory gate fails. Meta beats raw GP in 7/12, RF in 4/12 and domain GP in 9/12 paired episodes; pooled mean regret is worse than all three.

Initial v1 integration failed: 36 HTTP400 errors from unsupported named-function `tool_choice`. These are not inference or Meta performance evidence. Their explicit raw-GP fallbacks cannot be counted as AI results. v2 corrects to supported `auto` and halts on transport failures. Valid v1 numerical controls were reused only after exact source/input/runtime/episode-function checks; 48 copied control episodes are not newly computed runs. Raw rejection records, snapshots and reuse hashes remain. No rejected-request billing claim.

### Study B: evidence-gated portfolio, fresh seeds

Seven policies × three tables × four seeds = 84 episodes, seeds 106,137,193,239. Raw GP, RF and domain GP keep forecasts; before each new observation their forecasts are recorded, then weights change using clipped Gaussian log loss. A Meta-feature expert starts with 10% weight and can be disabled by abstention. Model sees expert errors/weights and can revise at reveals 8,16,24. This is a heuristic forecasting portfolio, not a calibrated posterior guarantee.

| Policy | Mean normalized regret | Final top-5% hit / 12 | Surrogate fits |
|---|---:|---:|---:|
| Random | .082517 | 12 | 0 |
| Raw GP/EI | .072201 | 11 | 288 |
| RF/EI | .092317 | 10 | 288 |
| Domain GP/EI | **.061280** | 12 | 288 |
| Numerical portfolio | .070262 | 12 | 864 |
| Portfolio + Wonder | .072888 | 12 | 1152 |
| Portfolio + Spark | .071783 | 12 | 1032 |

Both Meta continuation gates fail. Their pooled regret is slightly worse than the plain portfolio; the domain GP is stronger here. Equal group-query allowance does not mean equal CPU/model computation; fit counts are shown. Seeds differ from Study A, so differences between A/B are not a causal engineering ablation.

Wonder: 36/36 HTTP200, unique IDs, complete accepted plans; estimated **$2.2297584**. Spark: 36/36 HTTP200 and unique IDs, **21 complete accepted plans; 15 hit output length** under default reasoning and an 8192 output budget. Cost estimate **$1.22160665**. Explicit numerical fallbacks are part of the scored end-to-end system. This condition is not a clean comparison of intrinsic Spark/Wonder scientific ability. A separate unscored repair probe repeated three truncated requests with explicit medium reasoning AND 16384 output budget; all three yielded complete plans. No rollout was replaced/re-scored. Both settings changed, so the cause cannot be assigned solely to reasoning effort. Wonder failed the value gate despite complete outputs; no further feature-planner rollout was justified simply by fixing Spark transport.

Scored research inference total: **108 HTTP200 responses**, estimated **$6.33112985**, excluding compatibility/repair probes. Two simple compatibility calls and three output-budget diagnostics were also real HTTP200 inference. All requests, public outputs, IDs and usage remain; private reasoning and credentials are not stored. Costs are estimates at stated standard API rates, not checked credit deductions. Initial 36 HTTP400 attempts are separate.

## Independent verification

`research/frontier_scout/audit_replays.py` independently parses CSVs using standard-library grouping/statistics, checks source/snapshot hashes, matches every revealed mean/variance/count, verifies unique budgeted selections/common initial groups and recomputes regret. It checks each model request contains only the correct revealed prefix and diagnostics. **144 episodes, 4,608 group reveals and 108 scored request contexts pass.** Raw outcomes are historical measurements, not new lab data.

Figures in `output/frontier-scout/` are generated from recorded observations; lines average four seeds, shading is the observed Meta seed range, not a confidence interval. No significance or population-superiority conclusion from three public tables. Public/pretraining contamination cannot be excluded. Grouped means reduce noise and the fixed candidate pool differs from open-ended synthesis. Repository LICENSE says MIT while README says BSD-2-Clause; both retained with source papers. Larger NC-SA shell archive is excluded.

## Optical forward-model feasibility

Implemented coherent isotropic planar-film optics with dispersive measured n/k inputs and air / semi-infinite silica boundary conditions. Independent recursive Fresnel and characteristic-matrix formulations plus pinned external `tmm 0.2.0` reference. SiO2 uses the Malitson dispersion formula, k=0 approximation; TiO2 data are associated with a **350 nm ALD film**, not a universal process-independent material. Transfer to arbitrary layer thickness is an assumption. Data database commit `c5c2f188e848453def5970e347399d653df2ffc2`, CC0 retained; external solver MIT retained.

Across 64 random stacks × 5 wavelengths × 3 angles × 2 polarizations = **1,920 external comparisons**, maximum R/T disagreement is **6.22e-15**; between our two formulations **5.11e-15**. Analytical checks include Fresnel/Brewster/TIR, quarter-wave layers, energy/passivity and reciprocity. This validates implementation under these equations, not a fabricated film.

Conventional grid plus ordinary non-AI L-BFGS-B refinement (actual **1,695** objective evaluations, not an equal-budget AI comparison) finds a sampled feasible witness. Dense 801-point band quadrature: worst sampled visible T **.8748099**, NIR R **.9655982**; 401→801 maximum band-metric change **1.0741e-6**. Goal T>=.85 over450–650nm and R>=.8 over900–1100nm, minima over angles0/30, both polarizations, five fixed thickness perturbations <=3nm. Values are band integrals, not minima over all wavelengths. Separate witness remains explicitly **non-AI** and is withheld from the program-authoring prompt.

No finite-substrate rear face, roughness, scatter, thermal/cooling calculation, fabrication process uncertainty or continuous worst-case tolerance certificate. Layer count/order of the small program probe is fixed. It is not a new material discovery. Optical LLM algorithm discovery is established [prior art](https://arxiv.org/abs/2503.19742); implementation and measured results must earn the contribution claim.

## Reproduction

Use Python with the pinned versions in `requirements-frontier.txt` (no install performed by these commands). From workspace root:

```powershell
python research/frontier_scout/audit_replays.py
python research/frontier_scout/figures.py
python -m unittest discover -s tests -p test_frontier_materials.py -v
python -m unittest discover -s tests -p test_frontier_portfolio.py -v
python -m unittest discover -s tests -p test_coating_proof.py -v
python -m unittest discover -s tests -p test_coating_program.py -v
python -m coating_proof
```

`python -m coating_proof` regenerates a forward-only report and the conventional grid; it makes zero API calls and does not run the separate refinement script or program study. Preserve original input reports when regenerating hashes. Frozen scientific/model sources and input SHA256 manifests remain in each benchmark directory. Replaying numerical searches from scratch is supported by the experiment modules with a NEW output directory; do not overwrite paid/raw studies. `meta` commands perform paid live calls and require local `.env` keys, which must not be committed.

## Meta-authored optical search programs: completed probe

Three actual Wonder high-reasoning HTTP200 responses, three unique provider IDs, estimated usage cost **$0.334676**. Code0 ran 15 new queries then failed the interpreter's exact-integer conversion at `int(j/2)`; ordinary Python truncates here, so this is a language-interface limitation. Code1 exceeded the declared1200-AST-node bound before any new query. Code2 ran unchanged, completed its255 program queries plus one host initial evaluation, and found a sampled feasible eight-layer coating. No human repair is counted as model-authored code. All original programs and failure statuses remain.

Each method had a maximum256 queries/round, three rounds; each later round started from that method's previous best. Unused/failed-round allowances were not transferred. All outer development queries count. This is one known development problem with adaptive code revision, not three independent trials or an unseen-task test.

| Method | Actual total objective calls | Best search loss (lower better) | Dense801 visible T | Dense801 NIR R | Sampled goals met |
|---|---:|---:|---:|---:|---|
| L-BFGS-B | 693 | .00256396409 | .876815 | .866757 | yes |
| Differential evolution | 768 | .01253618426 | .840585 | .838366 | no |
| Meta-authored programs | 273 | .00256461387 | .876379 | .867127 | yes |

**No superiority claim:** Meta does not beat L-BFGS-B; the tiny final loss difference is not meaningful independent evidence. Its smaller actual count includes aborted rounds and does not establish query efficiency or saved prototypes. Differential evolution is a conventional control under the same cap, not a proof of the best global optimizer's performance. Fixed eight-layer order/target and a good conventional start make this a deliberately tractable feasibility check.

An offline audit independently reassembles the characteristic-matrix objective for **all1,734 queries**, checks budgets/chained initial points/best selection and replays all three unchanged received programs. Pass: maximum loss disagreement **6.80e-16**; all program traces exactly match. The separate forward proof supplies external `tmm` comparisons. Audit evaluations are additional offline work, not free online oracle queries and never sent to controllers.

The capability is real: Meta wrote an executable search strategy that generated independently checked, feasible model designs. The demonstrated output is an optimized instance of established thin-film physics. It is not a new material, an invented inverse-design method, fabrication evidence or a validated efficiency advantage.

Current targeted tests: 10 measured-data +4 portfolio +9 optical physics +6 numerical-language = **29 passing**. Existing unrelated/other-thread suites were not rerun or represented as new validation. Both materials studies' live inputs/sources match their frozen manifests.

Read `COATING_PROGRAM_PROBE.md`, `benchmarks/coating-program-probe-v1/summary.json` and `independent-audit.json` for receipts. `research/frontier_scout/api_ledger.py` aggregates this turn's actual provider evidence, including compatibility and failed integration. Broader recommendations are in `FRONTIER_OPPORTUNITIES_2026_10_30.md`.

## Continuation decision

Stop expanding feature-GP planning as the centerpiece. Continue the **optical search-program direction only provisionally**, with a separate prospectively frozen study for discrete material/sequence/layer-count choices and held-out band/angle/tolerance requirements. Use a fixed high-quality solver tool as a shared inner optimizer; the AI must earn value in formulation, architecture choice or transferable algorithm selection. Include multistart local search, DE, a domain-aware discrete search and the unchanged best received search program as controls. Charge all training/program-selection calls; report API cost and wall time separately. More credits support this breadth and replication, not a success guarantee.

Before claiming an AI advantage require a meaningful effect against the strongest complete baseline across multiple unseen tasks/seeds, plus independent dense spectral checks and source/receipt audits. Freeze the task suite, effect threshold and stop rule before new results. Allocate up to **$50 estimated API cost** to that distinct follow-on within the user's expanded authorization, but do not claim the allocation is actual spending, a new account balance or a completed experiment. No claim that this is hackathon-winning yet; final scope should follow that gate. Retain the verified work even if the next gate fails.
