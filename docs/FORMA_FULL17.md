# Full public CAD-bench evaluation

All 17 public tasks were attempted and graded, including the six previously excluded thread/gear/functional tasks. No missing task is removed from the aggregate. Only Meta Muse Wonder (`muse-wonder-1.0`) was used. Baseten and Modal were not needed for this run.

| Workflow | Tier-weighted score | Tasks ≥0.95 | Estimated inference |
|---|---:|---:|---:|
| Forma, initial frozen run | 0.689413135 | 10/17 | $0.752477 |
| Direct Build123D, same Meta model | 0.663536803 | 9/17 | $1.963509 |
| Forma, generic thread-engine repair replay | 0.709375192 | 10/17 | Original responses retained; no new inference |

These are single development runs, not confidence intervals or leaderboard rankings. The repair replay is explicitly post-failure: exactly the same 17 model plans, two thread tasks regraded, 15 identical original STEP inputs and scoring records retained. It is not a fresh end-to-end model run. Original failures remain available.

The initial paired comparison gives Forma a 2.59 percentage-point lead. Estimated inference cost is 61.68% lower. Observed median workflow generation latency is 16.171 s versus 61.547 s (3.81× difference); this includes different CAD runtimes and baseline container startup, so it does not isolate model speed or equalize generation hardware. Provider billing is unverified. There were 17 Forma responses and 25 baseline responses. The incremental estimated inference total is $2.715986. The conservative application ledger is $17.653816 of the approved $25 cap, including previous experiments and retained reservations.

## Protocol and runtime

Upstream: https://github.com/CAD-bench/cad-bench, revision `f1084c3d345f859ba48a4bd9d5c95bccca7dcb46`. The frozen protocol and all 17 geometry prompts are in `evaluation/forma-full17-v1/`, committed before inference at `c4b1193`. Public tasks were inspected while developing generic mechanical features; this is development evaluation. No training or private tasks were used.

Both arms use medium reasoning, temperature 0.15, at most 8,192 output tokens per response and two calls per task. One repair can use actual build errors. No grader output is returned to either model. New generations bypass application caches. Geometry instructions are identical; only the submission contract differs: bounded editable JSON for Forma, Python for Build123D. No reference code, scoring contracts, fixtures or expected geometry are sent to the models.

Generated Python executes only in a separate agent container with no network, credentials, verifier or reference assets. Containers run unprivileged with capabilities dropped, a read-only root filesystem, a private temporary filesystem and only task-specific input/output mounts. The verifier is separate and has networking disabled. Both arms export native BREP STEP and use the same **unmodified upstream `TaskModuleSpec.evaluate_step`**, including reference gates and Blender physics. This is an adapted STEP evaluation, not the original Harbor `final.py` submission protocol.

The original Dockerfiles build Linux Python 3.11.15, Build123D 0.10.0 / OCP 7.8.1.1.post1 and Blender 4.3.2. Today's unpinned `ocp_gordon` 0.3.1 failed to import against the required OCP. The compatibility overlay pins 0.1.17 in both images. The scorer source is unchanged. An initial UID 65534 provenance copy failed to preserve timestamps on the Windows/WSL mount; UID 1000 fixed that without running as root. Both failed calibration passes are retained separately. Subsequent functional oracle scores were 0.962077, 0.954641 and 0.977126. Image IDs, package freezes and versions are retained under `output/forma/evaluation/full17-environment-compatible/`.

The grader uses 4 CPUs and 4 GB, below upstream's declared 8 GB, with the upstream 7,200-second task limit. Both arms share these scoring resources. Forma generation remains Windows CadQuery 2.8 / OCP 7.9.3.1.1; baseline generation uses the isolated Linux Build123D runtime. Historical GPT/Gemini/Qwen research records have a different revision, harness and budget and cannot substantiate a direct ranking against this run.

## Baseline harness audit

The independent release check caught three null public responses: the provider returned usage receipts but no Python code after consuming the output budget on reasoning. The original client raised a `NoneType.strip` error, skipped the remaining repair and omitted those receipts from its generation summary. Raw receipts and the conservative ledger remained intact. Those first failures, summaries and receipts are preserved in `output/forma/evaluation/full17-baseline-client-failure/`.

Null output now undergoes actual empty-program build validation. Each affected case received exactly its remaining second attempt, with the unchanged original prompt, system message, model settings and two-call limit. The final scores remain zero for all three. The corrected baseline still scores 0.663536803, but its complete cost is $1.963509 across 25 responses. Earlier 19-response/$0.993917 baseline figures omitted the client-failed cases and are superseded. No extra task attempts or best-of selection were allowed. Three mocked controls verify null handling, all-receipt accounting and refusal of a third call.

## Product work and failures

New editable native features: involute spur gears, bevel gears, independent tooth/bore phase, round and D-shaped bores, placed principal-axis geometry, real single/multi-start right/left threads, internal threads with radial clearance, and socket-head screws. The inspector exposes dimensions, orientation, suppression and feature history. Gear profiles use [cq_gears](https://github.com/meadiode/cq_gears), pinned at `e73874cf17a25447a99b1e7c22a4d5af38560e9c` (Apache-2.0). The initial thread implementation used [cq_warehouse](https://github.com/gumyr/cq_warehouse), pinned at `a57bb7a24762d367d66369f280a24c38a64e73dd` (Apache-2.0). Its source and attribution are retained for reproducing the original run. Current threads use native CadQuery helical sweeps.

The initial thread Boolean could return a valid solid while dropping the crests, or retaining crests without the core. The fix embeds a swept axial profile into an extended cylindrical core, joins it before clipping, then verifies core retention and added ridge volume. Small and fractional-pitch regressions now check the actual major diameter and material. The identical screw plan improves from 0.403167 to 0.804140. The custom threaded pair remains low at 0.100790; its native major/root diameters are present, but profile/pitch matching still fails the upstream task-specific checks. No reference profile was copied to improve the score.

The remaining failures are explicit:

- A rounded slot scores 0.871314 against the rectangular reference. The instruction does not specify end shape; the upstream verdict is retained.
- The native involute spur gear has correct pose and dimensions but scores 0.485510 on the task's radial-profile criteria.
- Screw contact/thread proxy checks remain incomplete after the real geometry repair.
- The custom thread profile remains a failure.
- Two-shaft physical transfer scores 0.926208; three-shaft transfer scores 0.486272.
- The four-bevel assembly scores zero (`missing_axis_components`). Its native exported bodies also overlap at rest; it is not a verified functional gearbox.

Valid native solids and round-trip exports are geometry checks, not proof of all design constraints, dynamic transmission, manufacturing suitability or strength. All 17 initial Forma proposals built and exported, but only 10 meet the separate ≥0.95 benchmark threshold. This distinction is retained in the report.

STEP NURBS conversion can change numerical volume integration without changing geometry. Export validation retains its strict volume tolerance; where integration differs, it additionally proves symmetric Boolean difference within that same tolerance and bounds within 0.00001 mm. STL must remain watertight, consistently wound, and within the existing tessellation tolerances. The scorer was not modified.

Final verification: **98 checks passed** (95 CAD regressions and three baseline accounting/repair controls). A separate browser QA document verified 4→5 mm thickness editing, default preservation, saved history, drawing dimension updates, actual UI STL download, native STEP read-back, portable JSON, bundle integrity, undo and redo. The user's original Batman project pointer is restored after QA.

## Reproduction and artifacts

Open http://127.0.0.1:8770/full17 for the complete report and evidence download. Frozen inputs: `evaluation/forma-full17-v1/`. Initial results: `output/forma/evaluation/full17-v1/`. Repair freeze: `evaluation/forma-full17-thread-repair/`. Repair outputs: `output/forma/evaluation/full17-thread-repair/`. Exact generation source snapshots, original responses, receipts, all candidate files and scoring provenance remain available.

Build the upstream images from their pinned checkout, then apply `research/cadbench_compat.Dockerfile` with the original agent/verifier images as `BASE`. The full runner uses the existing Ubuntu WSL Docker engine. Do not install Build123D into Forma's CadQuery environment because their OCP versions differ.

```powershell
research/vendor/cad-runtime/Scripts/python.exe -m research.run_forma_full17 --arm forma --output output/forma/evaluation/NEW_RUN --live
research/vendor/cad-runtime/Scripts/python.exe -m research.run_forma_full17 --arm build123d --output output/forma/evaluation/NEW_RUN --live
research/vendor/cad-runtime/Scripts/python.exe -m research.forma_full17_report
```

Live commands make paid requests. New generation requires the frozen source bytes; use the retained snapshot to reproduce the original version. Completed tasks resume; a started task without a result requires receipt inspection to avoid duplicate billing. Frozen hashes refer to exact tested file bytes, including line endings. Regrading retained candidates verifies the generation snapshot rather than requiring a rollback of current product fixes.

The aggregate uses upstream `dataset/metric.py` unchanged: tier means weighted 1/2/3/4 for easy/medium/hard/insane. All 17 entries, including zeros, are present. Physical printing, broader task generalization, native SolidWorks/AutoCAD feature compatibility, FEA, and a winning hackathon result are not established by this evaluation.
