# Forma frozen development evaluation v1

Frozen before new model generations on November 1, 2026. Public development data; no held-out or physical-performance claim.

- 20 synthetic revision tasks: requested edits, state preservation, units, enclosure material/thickness propagation, invalid/ambiguous requests and preservation of custom geometry.
- All 11 compatible static primitive/profile geometry tasks from [CAD-bench](https://github.com/CAD-bench/cad-bench), pinned to commit `f1084c3d345f859ba48a4bd9d5c95bccca7dcb46`.
- Six gear/thread/Blender functional tasks excluded before generation. Every exclusion is listed in `protocol.json`; they remain part of the upstream public benchmark's 17-task scope.
- Upstream geometry instructions retained. Only its Build123D Python submission footer is replaced by Forma's declarative JSON output contract. No reference solutions or expected answers enter model prompts.
- Generated CAD is exported as STEP, then scored using the **unmodified upstream STEP evaluator**, including its reference-geometry gate where configured.
- The local evaluator uses Windows Python 3.12 and Build123D 0.10.0, rather than upstream Linux Python 3.11/Harbor. This is a local STEP evaluation of a public subset, not an official full-benchmark run.
- One Muse Wonder 1.0 generation per task, with one BREP/schema repair if needed. First-pass scores use that same initial response; they are not an independently sampled baseline.
- Upstream success threshold fixed at overall score ≥0.95 and build success 1. Continuous scores and all failures are retained. Revision scoring requires disposition, preservation, geometry and export checks.
- Existing conservative $5 app cap is retained. No automatic budget increase or retry after interruption. Fixed tasks, source versions, receipts and hashes make reruns reviewable.

Task and protocol hashes are in `manifest.json`. Generated evidence belongs under ignored `output/forma/evaluation/`; back it up separately. The upstream MIT license is retained in `CAD-BENCH-LICENSE.txt`.

```powershell
research/vendor/cad-runtime/Scripts/python.exe -m unittest tests.test_forma_eval -v
research/vendor/cadbench-runtime/Scripts/python.exe -m research.verify_cadbench_oracles
research/vendor/cad-runtime/Scripts/python.exe -m research.run_forma_eval --output output/forma/evaluation/v1 --live
```

The last command makes real Meta requests using only these public/synthetic tasks. The separate evaluator environment must contain Build123D 0.10.0 and upstream mesh dependencies. Forma's CadQuery runtime stays separate because the two packages require different OpenCascade versions.
