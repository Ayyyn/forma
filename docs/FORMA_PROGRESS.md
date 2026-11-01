# Forma progress — November 1, 2026

## First implementation increment

Baseline commit: `ce79818`. Source is versioned locally. No remote has been configured. Generated evidence and local projects are retained under ignored directories and need a separate backup.

Implemented selectable enclosure design comparisons, source-bound requirement status in Studio, cached drawing projections, correct informational check markers, current project documentation and a reproducible backend profiling command.

## Verification

- Studio suite: 29 tests passed after the implementation. Added one further end-to-end snapshot binding regression; all six tests in that module passed. Current Studio test count: 30.
- Enclosure suite: 35 tests passed.
- Studio HTTP harness: 37/37 checks passed against the running application. Receipt: `output/forma/studio/http-2026-11-01-v2/results.json`. The first attempt was blocked by sandbox loopback restrictions; the second ran with local network access.
- Browser: opened design alternatives for the saved Transit enclosure; inspected 12 mm and 15 mm designs; selected 15 mm; verified unsaved preview, changed mass (9.28 kg), preserved 80 L capacity and updated floor screening (0.522 mm). Reload restored the saved 12 mm design. Final comparison modal visually inspected.
- JavaScript syntax checks passed for both application scripts. Python files formatted with Black; changed UI assets formatted with Prettier 3.6.2.
- Staged baseline scanned against actual local credential values and common private-key/token patterns: no matches.

## Performance

Five default-plate backend snapshots per condition, in one process:

| Condition | Median | Maximum |
|---|---:|---:|
| Uncached snapshot | 384.586 ms | 442.228 ms |
| Cached snapshot | 4.524 ms | 5.787 ms |

Receipt: `output/forma/performance-2026-11-01.json`. Run `python -m research.profile_forma --output output/forma/performance.json` with CAD dependencies installed.

These timings exclude interpreter startup, HTTP, browser rendering and model inference. They measure one simple fixture, not a broad performance benchmark or competitor comparison.

## Integrated workflow increment

Shared Project editing now regenerates enclosure panels, requirements and drawings into one Studio revision. Briefs and motion settings persist in portable projects. The AI planner has a bounded global enclosure patch action that preserves requirements and rejects failing revisions. Arbitrary edits remain explicitly stale rather than inheriting source checks.

Finite-thickness wall motion includes adjustable angle/sample count, local playback and scrubbing, envelope plots, sampled overlap markers, revision invalidation and saved configuration. Independent transformed OpenCascade solids agree with computed bounds and overlap checks at five poses. A deliberately incorrect hinge location is detected. The large stage canvas includes pan/zoom, scrollbars, fit-all, minimap, model overview and stage navigation; narrow-screen placement was corrected during browser QA.

The export bundle includes `workflow-report.json`, current/stale requirements and motion state, hashes, and separate flattened enclosure panel STEP/STL files with mesh verification. The physical mockup guide is [FORMA_WORKFLOW.md](FORMA_WORKFLOW.md).

Verification: 76 unit tests (41 Studio, 35 enclosure); 37 Studio HTTP checks; 19 shared-workflow HTTP checks including panel files, export hashes and portable context. Final receipts are under `output/forma/workflow/`. No model calls were made by these checks. After explicit approval for the synthetic payload, the live global-thickness task passed all seven checks: ready proposal, thickness update, dimensions/requirements/brief preserved, current qualification and applied revision. One real muse-wonder-1.0 response, estimated $0.028588. Receipt: `output/forma/workflow/live-v1/results.json`. This is one constructed integration task, not an external benchmark.

Latest five-sample default-plate backend profile: uncached median 183.760 ms, cached median 2.254 ms. This remains one local fixture, excluding HTTP, startup, browser rendering and model inference. It establishes no competitor comparison.

Browser checks: manual thickness change, visible engineering failure, feasible alternative regeneration, folding at 90°, saved configuration, 19-pose/60° configuration, play/pause and fit, revision canvas, fit-all and responsive layout. The physical test remains pending.

## Remaining product scope

Physical measurements, engineered hinges, general origami/mechanism solving, general FEA, photo interpretation, external benchmark evaluation and production deployment are still pending. The stage canvas currently has fixed stage positions and session-local navigation. Follow [the build plan](FORMA_BUILD_PLAN.md).
