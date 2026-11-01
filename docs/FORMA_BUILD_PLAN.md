# Forma implementation plan

Updated November 1, 2026. Product direction is fixed: an editable CAD workflow with requirements, design alternatives, bounded folding and fabrication outputs.

## Delivered first increment

- Local Git baseline; ignored credentials, generated state, external snapshots and CAD runtimes. Existing files remain on disk.
- Enclosure stock comparison: inspect all feasible alternatives and explicitly preview a choice. Changed input invalidates an in-flight comparison.
- Imported enclosure requirements: recompute checks while the source panel geometry matches; mark stale after resizing, suppression, deletion, added features or movement. Presentation edits preserve qualification. Returning to the original definition restores current checks.
- Cache drawing projections for repeated snapshots, invalidating with document changes. Informational checks no longer display success ticks.

## Next increments and acceptance criteria

1. **Shared project workflow.** Link brief, requirements, alternatives, CAD, simulation and drawings by revision. No stale result can appear current. Add supported enclosure parameter editing directly inside Studio, with deterministic panel regeneration.
2. **Interactive performance.** Measure browser interaction, API, CAD regeneration, drawings and model inference separately. Cancel superseded previews, debounce parameter edits, move projections out of the critical editing path. Target under 100 ms for local interaction and under 1 s for representative simple geometry updates; measure before making speed claims.
3. **Folding.** Integrate one supported panel/hinge family, with motion limits, thickness-aware clearance screening and printable components. Verify against an independent kinematic reference. Ideal Miura/accordion remains labeled with its zero-thickness assumptions.
4. **Project canvas.** Warm neutral stage canvas, left-to-right workflow, minimap, model/drawing focus modes and persistent assistant context. Keyboard and narrow-screen workflows remain usable.
5. **Evaluation.** Freeze a small external CAD task subset after checking compatibility and licenses. Publish task selection, failures, adaptations and fixed model budgets. Add a separate 20-task revision suite and model/call-cost comparison. No official benchmark claim for adapted tasks.
6. **Physical demo.** For November 2: a small printer calibration and hinge/clearance specimen before a full assembly; record actual dimensions, print settings and failures. Physical results stay pending until measured.

## Release gates

Feature and HTTP regression checks; browser verification of critical workflows; representative latency receipts; STEP/STL round-trip checks; clear engineering scope; no secrets in source; reproducible setup and a concise recorded demonstration. Portfolio/product polish includes sample projects, onboarding and dependable recovery from invalid edits.

## Boundaries

Current qualification binds only to the exact supported enclosure panel feature definition. Arbitrary geometry edits require engineering requalification. Matching geometry does not establish strength, manufacturing readiness or physical safety. Neutral STEP exports do not preserve Studio feature history; portable JSON does. DWG, general FEA and a general mechanism solver are not implemented.
