# First broader structural-design experiments

October 29, 2026. **A working numerical/tool-using prototype is implemented. It generates and checks useful candidates in a bounded structural language. General AI optimization superiority, faster experiments and physical-prototype savings remain unproved.**

## What we built

The objective is requirements-driven structural discovery across mechanism families. Origami, Kresling and actuators are possible physics adapters, not the project boundary. The user prefers motion/programmed response first, while supports and instrument/device structures also matter.

The first new adapter handles non-folding, small-motion compliant beam/frame networks. Meta can edit connectivity/widths, invoke a real constrained numerical optimizer, inspect gradients and constraint failures, request actual geometry images, and revise after tool feedback. Independent numerical verification decides feasibility. The older Kresling proof remains separate; we do not compare nonlinear origami equilibria and linear frames as interchangeable models.

This is generic mechanical research. Medical-device mechanical R&D could be a later application with the right model and evidence. There is no patient data, medical advice, tissue/implant model, clinical-performance claim or medical-device validation here.

## Frozen exploratory v3 pilot

Four public development tasks: positive cross-motion coupling, stiff/light support, directional flexure and a reserved central channel. Two seeds per task; three policies; 24 cells. Every policy receives the same exact constraints, graph, coefficients, clearance/feature/linearity checks, sizing optimizer, cache and independent final oracle. Each has at most 96 charged search slots. Optimizer internal samples consume those slots. A common final oracle solve is separately counted.

| Method | Verified feasible | Median actual frame solves to first feasible result | Median search time |
|---|---:|---:|---:|
| Automated numerical portfolio | 8/8 | 5 | 0.144 s |
| Single-pass Meta portfolio | 6/8 | 13 among successful runs | 6.676 s |
| Adaptive Meta tool agent | 8/8 | 43 | 32.977 s |

The numerical control screens template width extremes, prioritizes constrained SLSQP sizing with analytical derivatives, and adds/removes graph members. It is a bounded portfolio, not the best possible structural optimizer or a global optimum guarantee. Single-pass Meta gets one model request; adaptive Meta gets at most six. Numerical allowances are equal; API/compute allowances and costs are separately reported.

### Paired quality, rather than a misleading overall average

| Task | Seed 101: agent versus numerical volume proxy | Seed 202: agent versus numerical volume proxy |
|---|---|---|
| Motion coupling | 30.15% larger / worse | 19.30% larger / worse |
| Stiff support | Effectively tied | 35.70% smaller |
| Directional flexure | Effectively tied | Effectively tied |
| Reserved channel | Effectively tied | 26.53% smaller |

“Tied” ignores numerical differences below 0.001%. Two selected agent graphs are outside every starting template; the numerical control also selects a non-template graph in one run. These are candidates within this structural language, not established new-to-science structures. Raw per-case feasibility, objective values, failures and optimizer samples are retained.

The two favorable agent results are genuine within the declared model. They do not establish broad advantage: the preferred motion task worsened, the other seeds did not repeat the gains, and all tasks were known development requirements. Averaging unlike volumes or dropping failed single-pass runs would distort the evidence.

The adaptive policy used 701 charged slots and 683 production assemblies across eight runs, versus numerical 768/748. Unused allowance plus mixed final quality does not establish sample efficiency. In particular, the agent required far more solves to obtain its first feasible candidate and was much slower on these cheap models.

## Post-hoc catalogue-coverage check

Inspection suggested that the numerical control might simply lack useful starting families. A separate **post-hoc** diagnostic enumerates conventional dense grids with different diagonal orientations, and one/two two-edge load paths. It screens candidates and sizes promising ones using the same solver/optimizer with a 96-slot cap. It uses no new Meta calls and does not inject the agent's selected widths.

| Lead example | Frozen numerical, seed 202 | Frozen Meta, seed 202 | Post-hoc wider catalogue |
|---|---:|---:|---:|
| Stiff support volume proxy | 472.4 mm³ | 303.8 mm³ | **299.3 mm³** |
| Reserved channel volume proxy | 357.8 mm³ | 262.9 mm³ | **214.9 mm³** |

Both diagnostic candidates satisfy the same modeled constraints and independent compliance checks. The channel example removes unnecessary dangling members from the more direct load-path family. Catalogue coverage is therefore a plausible explanation for the apparent wins. This check was designed after seeing the pilot: it is not a replacement prospective comparator or proof of general numerical superiority. It identifies a stronger control to freeze before unseen tasks.

The useful systems lesson is that Meta can suggest a structural family overlooked by a particular portfolio, while ordinary numerical tools can size and improve it. That may help an engineering workflow, but this experiment has not measured an advantage over a sufficiently broad automatic design-space generator.

`research/structure_catalogue_challenge.py` reproduces the diagnostic. Its results are in `research/structure-catalogue-challenge.json`. `benchmarks/structure-pilot-v3/structures.png` shows the two examples, explicitly labels the post-hoc column, and notes that the other outcomes remain in the full report.

## Real API/tool operation and cost

The retained v3 run made **46 actual API requests**, all HTTP 200 with 46 distinct provider response IDs, returning Baseten `meta-models/muse-spark-open-1026`. Encoding counts: 42 native tool responses, one XML invocation, one single-plan JSON object, and two responses without an executable command. The latter two single-pass outcomes remain failures.

The agent actually used numerical optimization, custom evaluation, sensitivity inspection and geometry rendering. Thirty image inputs were transmitted across requests, including repeated history; this does not mean 30 distinct images. Eight geometry-inspection views were generated. We have not isolated a causal benefit from images or any specific tool. Internal optimizer work is counted per candidate, not per high-level invocation.

v3 reported 512,326 input tokens (345,344 cached), 44,302 output tokens, including 33,649 reasoning tokens. Estimated cost: **$0.45**. All three development versions together made **143 actual requests**, estimated reported-usage cost **$1.38**, using [Baseten's generic rates](https://www.baseten.co/library/muse-spark-open/) checked October 29. Actual promotional-credit deductions/account balance are unverified. Provider identities, received public output, normalized-action provenance, arguments and usage are retained; private reasoning text and credentials are excluded.

## Integration history is preserved

- **v1:** completed and archived with exact source. A post-run permutation regression exposed optimizer variable/sensitivity mismatch for unsorted custom edge lists. One actual optimizer call exercised this path. Candidate mechanics remained independently checkable, but trajectory/efficiency was affected.
- **v2:** corrected ordering and reran the full matrix. It exposed some usable commands in XML/JSON public text outside native `tool_calls`, plus an unnecessarily restrictive eight-item plan schema.
- **v3:** a tested strict normalizer accepts those observed encodings, retains received output/encoding, and validates the same allowed tools and argument schemas. Local normalized invocation IDs are explicitly local, not fabricated provider response IDs. Portfolio length is bounded by the same 96-slot total. The whole matrix was rerun.

Earlier versions remain diagnostic archives. We do not pool them, replace only failures or attribute stochastic output changes solely to the fixes. Supplying a seed does not guarantee identical remote model output. Each version preserves exact source under `source/`, raw cells under `runs/`, and the associated report/issue notes.

## Verification and scientific limits

All **77 current workspace tests** pass. The frame implementation matches analytic cantilever displacement/rotation, subdivision invariance, energy/work balance, coordinate covariance and reciprocity. Independent Hermite strain-energy assembly agrees across all starting topologies. Analytic sizing gradients agree with finite differences. Targeted tests cover edge-order invariance, graph/clearance rejection, budget/cache accounting, corrupted-output detection, tool-result history and strict output decoding.

All v3 **24 cells and 1,940 charged records** replay. All **1,852 valid candidates** get independent offline compliance checks, separately recorded and unavailable to the search controllers. Selected-candidate oracle discrepancy is at most 1.15e-11 mm/N. Maximum absolute discrepancy over all candidates, including very compliant failed designs, is 2.89e-8 mm/N, within the declared scaled tolerance. Actual assembly counts can include failed solves and therefore differ from valid-candidate counts. All source hashes/snapshots match, and prior Miura/Kresling frozen sources remain unchanged.

The model is small-displacement, slender, rigid-jointed, in-plane Euler-Bernoulli mechanics on a fixed nine-node/18-edge graph. It excludes shear flexibility, joint compliance/concentrations, true fabrication geometry, nonlinear actuation, contact, large motion, plasticity, fatigue, self-weight and loaded buckling certification. The volume proxy sums ideal member volumes including joint overlaps. All coefficients, loads and requirements are synthetic. Numerical consistency is not hardware validation.

**Physical experiments: zero. Physical prototypes: zero. Avoided prototypes and human experiment/design time saved: not measured.** Numerical solve counts or runtime cannot be relabeled as observed hardware savings.

## Decision and next useful experiment

Continue investigating the broader requirements → structural concepts → optimization → verification loop as an experimental workbench. Do not claim Meta is already the better structural optimizer or that it reduces prototype counts. Current evidence supports functional tool orchestration and useful candidate generation, with a catalogue-coverage confound and no efficiency benefit.

The next prospective study should freeze unseen requirements, geometries/load cases and revisions, with the wider catalogue/structural generators in the numerical control from the start. Separate one-pass formulation, iterative numerical feedback and geometric context through ablations. Judge verified completion, robustness and paired quality/cost, rather than attractive geometry or one favorable seed. Validate additional physics adapters before adding nonlinear motion, shells, origami or application-specific device claims.

The possible AI contribution is formulating a useful design space/model, suggesting structural concepts, designing tests and repairing failures with tools. Numerical optimizers remain core tools and controls. A general CAD canvas, branding or a clinical claim is not the next scientific gate.

## Reproduce

```powershell
python -m structure_lab verify
python -m unittest discover -s tests -p test_structure_lab.py
python -m structure_lab report
python research/structure_catalogue_challenge.py
python research/structure_pilot_figures.py
```

These commands are offline. Paid `python -m structure_lab run` skips saved cells; fresh research changes require another versioned source freeze. The CLI defaults to v3. Older versions can be replayed from their own `source/` directory with the absolute original `--directory` path. See `docs/STRUCTURE_LAB_PROTOCOL.md` and `benchmarks/structure-pilot-v3/` for the protocol, source manifest, raw records, CSVs and plots.
