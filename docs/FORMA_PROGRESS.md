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

## Remaining scope

Shared enclosure editing inside Studio, integrated finite-thickness folding, the stage canvas, external evaluation and physical printing are still pending. Follow [the build plan](FORMA_BUILD_PLAN.md). This increment does not complete the full product.
