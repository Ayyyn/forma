# Forma implementation plan

Updated November 2, 2026. Product direction is fixed: an editable CAD workflow with requirements, design alternatives, bounded folding and fabrication outputs.

## Delivered first increment

- Local Git baseline; ignored credentials, generated state, external snapshots and CAD runtimes. Existing files remain on disk.
- Enclosure stock comparison: inspect all feasible alternatives and explicitly preview a choice. Changed input invalidates an in-flight comparison.
- Imported enclosure requirements: recompute checks while the source panel geometry matches; mark stale after resizing, suppression, deletion, added features or movement. Presentation edits preserve qualification. Returning to the original definition restores current checks.
- Cache drawing projections for repeated snapshots, invalidating with document changes. Informational checks no longer display success ticks.

## Integrated workflow increment

Delivered: shared Project editing and regeneration, bounded AI enclosure patches, finite-thickness wall motion with adjustable sampling and local playback, revision-bound study settings and export reports, separate flat panel components, and the large stage canvas with minimap and model overview. Engineering scope is documented in [FORMA_WORKFLOW.md](FORMA_WORKFLOW.md). General origami, engineered hinge hardware and physical validation remain separate work.

## Product hardening and acceptance criteria

1. **Shared project workflow — delivered for enclosures.** Brief, requirements, alternatives, panel CAD, motion settings and drawings share a revision. Further work: additional design families and richer constraint editing without losing custom features.
2. **Interactive performance — initial improvements delivered.** Geometry and drawing caches have separate inputs; brief/display changes reuse both; hidden model rendering pauses. Next: browser-level latency profiles, superseded manual-preview cancellation and incremental regeneration for larger models. Targets remain under 100 ms for local interaction and under 1 s for representative simple geometry updates; no broad speed claim yet.
3. **Folding — wall study delivered.** Thickness-aware rectangular panel motion, editable angle/sample count, overlap checks, playback and export report. Remaining: engineered hinges, contact/load behavior and physical calibration. Ideal Miura/accordion remains separate and labeled with zero-thickness assumptions.
4. **Project canvas — delivered.** Warm neutral left-to-right stages, minimap, model overview, stage navigation and focused editors. Remaining: arbitrary stage placement, saved navigation and canvas annotations.
5. **Evaluation — complete public coverage, further validation open.** The frozen 20-task revision suite and earlier 11-task subset are retained. All 17 public CAD-bench tasks now have results with a controlled Meta-only baseline, fixed call/token limits, unmodified Linux STEP grading and original failures. The same-plan engine repair is labelled separately. See [FORMA_FULL17.md](FORMA_FULL17.md). Next: held-out tasks, repeat trials and controlled generation hardware. No official leaderboard claim for adapted tasks.
6. **Physical demo — pending.** Separate flat panel STEP/STL files and the mockup protocol are delivered. For November 2, print a thickness/hinge coupon before the complete assembly, then retain measurements, print settings and failures.

## Release gates

Feature and HTTP regression checks; browser verification of critical workflows; representative latency receipts; STEP/STL round-trip checks; clear engineering scope; no secrets in source; reproducible setup and a concise recorded demonstration. Portfolio/product polish includes sample projects, onboarding and dependable recovery from invalid edits.

## Boundaries

Current qualification binds only to the exact supported enclosure panel feature definition. Arbitrary geometry edits require engineering requalification. Matching geometry does not establish strength, manufacturing readiness or physical safety. Neutral STEP exports do not preserve Studio feature history; portable JSON does. DWG, general FEA and a general mechanism solver are not implemented.
