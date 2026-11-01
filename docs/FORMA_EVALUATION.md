# Frozen CAD evaluation — November 1, 2026

Open the local review at `http://127.0.0.1:8770/evaluation`. It includes task-level scores, failures, exclusions, demo history and downloadable evidence.

## Results

| Evaluation | Initial result | Detail |
|---|---:|---|
| Constructed revision tasks | 19/20 | Exact requested edits, preservation, units, enclosure propagation, clarification and STEP/STL checks |
| Public CAD-bench geometry subset | 10/11 above 0.95 | Unmodified upstream STEP scorer and reference-geometry gates |
| Public mean upstream overall score | 0.98830127 | Unweighted arithmetic mean on the selected subset |
| Public reference-oracle calibration | 11/11 effectively 1.0 | Same local evaluator and selected tasks |
| Targeted development rerun | 1/1 | Failed revision task r15, unchanged task and scoring, after the product fix |

The initial 31 tasks used 32 actual model responses. The targeted rerun added one response, for 33 total. Estimated model cost was $0.915048, including the rerun; billing has not been independently verified. The existing shared $5 **conservative reservation** guard was not increased. Its charged reservations are larger than completed-call usage estimates, so this run leaves little room under that application guard; it is not an account-credit reading.

Revision proposal/BREP latency: median 4.20 seconds, maximum 8.47 seconds. Public geometry: median 9.42 seconds, maximum 13.94 seconds. Timings exclude export, external scoring and browser rendering. These measurements establish no competitor speed comparison.

First-pass and verified success were equal in the initial run: 19/20 revisions and 10/11 public tasks. This run therefore does not establish an improvement from the existing bounded repair loop. The later targeted rerun demonstrates the product fix on one inspected failure, not a fresh 20/20 suite result.

## Public benchmark and adaptations

[CAD-bench](https://github.com/CAD-bench/cad-bench), MIT licensed, pinned to `f1084c3d345f859ba48a4bd9d5c95bccca7dcb46`. The public repository has 17 tasks. Before any new model generation, we selected all 11 static primitive/profile geometry tasks and excluded six thread/gear/Blender functional tasks, listed individually in the frozen protocol.

The geometry instructions were retained. Only the `final.py`/Build123D submission footer was replaced by the Forma JSON proposal contract. No expected answers or reference programs were supplied to the model. Generated CAD was exported as STEP and scored using upstream's unmodified `evaluate_step`, including reference geometry gates.

The local verifier used Windows Python 3.12, Build123D 0.10.0, OpenCascade 7.8.1.1, NumPy 2.4.2 and trimesh 4.11.2. The upstream Harbor runtime specifies Linux Python 3.11. Docker's engine was unavailable locally. This is an adapted local STEP evaluation of a public subset, not an official complete benchmark or leaderboard result. Forma's own CadQuery/OpenCascade runtime remained separate.

Public tasks were inspected for compatibility, so this is development evaluation, not a held-out test. No training was performed. Selection and the 0.95 success threshold were fixed before model generation. Tasks, protocol, upstream files, application sources and scorer versions are hashed. Exact source snapshots are retained for both the initial and patched runs.

## Failure 1: stock-conflict repair citations

Task r15 requested exactly 3.5 mm enclosure panels while retaining configured stock. The first response proposed the invalid thickness. On repair, the model correctly asked for clarification but quoted the validator's conflict message as evidence. The exact-source citation guard rejected it.

The product fix exposes the current engineering contract and material stock catalogue to the planner. Repair feedback now repeats the original instruction and explicitly restricts citations to it. Clarification with no edits may use an empty evidence array. No validator was weakened and the frozen task was unchanged.

The single targeted live rerun returned clarification on its first response, preserved the document and passed the frozen scorer. The initial failure and both original responses remain in the evidence archive.

## Failure 2: unspecified slot-end shape

The `plate_80x40x8_slot_4_hole` instruction names a centered 40 × 10 mm through slot without specifying the end profile. The model built an overall-length rounded slot. The reference uses a rectangular 40 × 10 mm box cut. The unchanged reference geometry gate returned 0.87131397; this remains an initial failure under the fixed 0.95 threshold.

Independent volume arithmetic confirms the difference: the rounded slot has area `(40−10)×10 + π×5²`, while the rectangular cut has area `40×10`. The resulting solid-volume difference exactly explains the measured reference difference fraction, approximately 0.00798696. We infer a prompt/reference ambiguity from the source instruction and reference implementation; we do not replace the upstream verdict.

A separate, explicitly square-ended **human edit** produced score 1.0. It made no model request and is excluded from every frozen aggregate. This documents an intent-resolution path rather than hiding the original result.

## Reproduce and inspect

Frozen files: `evaluation/forma-v1/`. Initial run: `output/forma/evaluation/v1/`. Targeted rerun: `output/forma/evaluation/v2-repair/`. Native oracle checks: `output/forma/evaluation/oracles/`. Supplemental human edit: `output/forma/evaluation/slot-clarification/`.

```powershell
research/vendor/cad-runtime/Scripts/python.exe -m unittest tests.test_forma_eval -v
research/vendor/cadbench-runtime/Scripts/python.exe -m research.verify_cadbench_oracles
research/vendor/cad-runtime/Scripts/python.exe -m research.run_forma_eval --output output/forma/evaluation/NEW_RUN --live
research/vendor/cad-runtime/Scripts/python.exe -m research.forma_eval_report
```

A fresh Git checkout also needs the pinned upstream files: clone `https://github.com/CAD-bench/cad-bench.git` into `research/vendor/cad-bench` and check out the commit above. The curated source ZIP already includes the selected verifier/reference files. File hashes are byte-exact to the tested Windows checkout; line-ending conversions should be checked if reproducing on another platform. The current runner uses Windows `Scripts/python.exe` paths.

Live commands make paid requests. The output directory identifies a run; completed task results are reused, and interrupted requests require inspection rather than automatic repetition. Changed application sources require a new run name. Install `requirements-cadbench-lock.txt` in a separate Python environment from Forma's `requirements-forma.txt`.

The evidence ZIP contains hashed artifacts with credential scanning, receipts, failures, source snapshots and candidate geometry. Generated evidence is intentionally ignored by Git and needs a separate backup. Source code, frozen tasks, protocol, tests and the portable example are versioned. Physical validation, held-out generalization and broader CAD capability remain unestablished.
