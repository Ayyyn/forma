# Shared Studio workflow

Run `python -m crate_studio --port 8770` with the CAD dependencies installed, then open `http://127.0.0.1:8770/studio`.

## Project → CAD → motion → drawing → package

**Project** stores the brief, enclosure specification and requirements in the same immutable document revision as the feature tree, notes and motion configuration. Edit panel thickness, material or clear dimensions, then choose **Rebuild & save revision**. Every panel regenerates; engineering checks and drawings update. Failing requirements remain visible even when the geometry is valid. Custom feature edits require the explicit **Replace custom geometry** checkbox before panel regeneration. The previous revision stays in history.

**Compare alternatives** searches the configured stock catalogue using the retained requirements. A selection regenerates and saves a new revision. Locked clear dimensions remain fixed; otherwise the existing bounded sizing family may resize within the envelope. Results describe this search family and do not establish a global optimum. Inputs are locked while a request is running; superseded comparisons cannot apply to a different base revision.

The Meta planner also supports a bounded global enclosure specification patch. For example: “Change every enclosure panel from 3 mm to 4 mm, preserving the internal dimensions and every requirement.” It regenerates all panels, preserves the requirement contract, checks the result and waits for explicit Apply. Custom geometry cannot be discarded through this action. The operation is covered by offline checks and one user-approved live synthetic integration task: all seven checks passed, with an estimated API cost of $0.028588. This is one constructed task, not an external benchmark.

**Motion** runs a finite-thickness, rigid-panel enclosure study. The top panel must be removed in Project first. Set a maximum angle (1–90°), choose 19/37/73 poses, then run. Scrub or play the result locally without further API calls. The graph shows X/Y/Z envelope dimensions across sampled poses. Red panels identify detected overlap in the nearest sampled pose. **Fit** frames the current pose; orbit and zoom work directly in the viewport. Save study settings to attach the configuration to a revision. Geometry changes invalidate session results; export recomputes the saved configuration for the exported revision.

**Canvas** presents six stages from left to right: brief, requirements, alternatives, editable CAD, wall motion, and drawings/export. Drag empty space to pan; use the wheel to zoom, Shift-wheel to scroll, or the zoom/fit controls. The bottom and right scrollbars and clickable minimap navigate the large canvas. A model overview remains visible on wider screens. Stage buttons and double-clicks open the corresponding editor. Canvas stage positions are currently fixed; engineering content remains editable in its stage editor. The view is session-local.

**Drawing** contains geometry-derived views and editable notes. **Export → Design package** includes neutral solids, drawings, portable source, per-file hashes and `workflow-report.json`. For a matching enclosure, it also includes individually flattened panel STEP/STL files and `panel-pack.json`. Motion settings and the brief survive portable JSON import. STEP retains geometry; Studio JSON retains feature history and project context.

## Motion definition and verification

The base stays fixed. Four walls rotate outward about virtual axes along the base's outer top edges, with angle zero representing the assembled enclosure and 90° representing outward-flat panels. Placing each axis on the outer edge accommodates panel thickness; putting it through the wall's bottom center causes base penetration and is covered by a regression test.

At each sampled pose, the checker applies the separating-axis theorem to all pairs of oriented rectangular panel boxes: six face-normal directions and nine edge cross products. Positive-volume overlap is rejected; touching is allowed within numerical tolerance. The UI uses the same hinge definitions, while independent test solids are transformed using OpenCascade and checked for both bounds and Boolean intersection volume at five poses.

For a 90 × 60 × 45 mm clear enclosure with 3 mm panels, the closed envelope is 96 × 66 × 48 mm and the outward-flat envelope is 186 × 156 × 6 mm. Dimensions refer to this specified virtual motion, not a tested physical mechanism.

This is a prescribed kinematic study with sampled overlap checks. It does not prove continuous swept clearance or model hinges, fasteners, flexibility, stresses, contact forces, fatigue or printed-material behavior. The original separate Miura/accordion prototype still uses ideal zero-thickness kinematics; it has not become a general finite-thickness origami solver.

## Small physical mockup for November 2

Use the 90 × 60 × 45 mm clear dimensions, 3 mm thickness, open top, a 0.2 L minimum capacity and a suitable envelope limit. The polypropylene profile is a computational assumption; select and document the actual fabrication material separately. Save a motion configuration and export the Design package.

1. Open the separate `panel-*.stl` files in a slicer. Check units, printer bed fit and thickness. These panels include no designed mechanical hinges or joining holes.
2. Print a small thickness/hinge coupon first. Measure the actual thickness and check that the intended tape/external hinge axis can be positioned near the virtual axis without forcing the panels.
3. Arrange and print the five flat components. Assemble a low-load demonstration with temporary external hinges; do not infer a load rating from the screening model.
4. Record printer, filament, slicer settings, print time, actual clear dimensions, closed/flat envelopes and any interference. Photograph and retain failed trials.

Physical validation remains pending until those measurements exist.

## Verification commands

```powershell
python -m unittest discover -s tests -p 'test_workspace_*.py' -v
python -m unittest discover -s tests -p 'test_crate_*.py' -v
python -m research.verify_studio_http --directory output/forma/workflow/NEW_STUDIO_RUN
python -m research.verify_forma_workflow --output output/forma/workflow/NEW_WORKFLOW_RUN
python -m research.profile_forma --output output/forma/workflow/performance.json
python -m research.package_forma
```

HTTP checks need the server running. Verification directories must be new. Local checks make no model calls. The separate `verify_forma_workflow_live` command sends one constructed task to Meta, within the existing application budget cap; the user-approved synthetic task passed once. Each run makes a real API request. Keep generated evidence backed up separately from Git because `output/` is ignored.
