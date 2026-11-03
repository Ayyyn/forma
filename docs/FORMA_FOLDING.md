# Articulated folding and model import

Studio supports five finite-thickness rigid-panel mechanisms: Miura grids with
compatible crease cycles, concertina chains, open annular half-fans, alternating
triangle strips, and six-face cube nets with staged wall/lid closure. These use
native solid panels, bored three-knuckle hinges and separate headed pins.

## Human and Meta workflow

Create a **Folding assembly** or describe one to Meta. Review the proposal before
applying it. The feature inspector exposes the family, relevant panel counts and
pitches, thickness, hinge dimensions, clearances, setback and preview driver.
Dimensions are millimetres; the driver angle is not every joint's dihedral.

The Sketch tab shows nominal hinge axes. Model and Drawing show the actual
finite-thickness geometry, including panel setbacks and hardware. A change
regenerates geometry, drawings and exports from the same feature parameters.
Saved revisions preserve undo/redo and source intent.

Run **Motion** to check actual native-solid interference and hinge-axis closure
at the selected poses. Playback displays those checked poses. Results become
stale after a geometry change. Dense sampling is available for folding features;
the default is 73 poses. The larger Miura grids can take substantially longer
for a first dense study; exact repeated trajectories reuse the in-memory result.

Qualification requires one active folding feature. Additional arbitrary CAD
edits can be retained as static geometry, but do not inherit that feature's
motion qualification. General origami graphs, Kresling/Yoshimura mechanisms,
compliant materials and force/friction/fatigue simulation are outside this tool.

## Printing

Choose **Export → Folding print pack**, confirm your bed, nozzle, layer height
and material, and save the settings. The pack contains:

- Separate oriented component STLs and verified build-plate STL/STEP files.
- A fit coupon with the same hinge dimensions.
- Plate identification maps, panel/hinge assembly instructions, and target
  mountain/valley dihedrals. Use Motion to see the intended folding direction.
- A FOLD crease-axis representation, editable source JSON, verification manifest
  and file hashes.

Print the coupon first. Check bore bridging, pin insertion and free rotation in
your actual material. Thin upright pins may need a removable brim. Confirm
machine and filament settings in your slicer. Axial pin retention and physical
strength have not been qualified. The exporter does not generate machine G-code.

The ordinary workspace STL represents the assembled source pose. Use the
prepared print pack for separated build-plate parts. STL has no embedded length
unit; these files use millimetres. STEP declares millimetres.

## Import instead of generate

Use **Import** for STEP/STP, STL or OBJ. Mesh imports require an explicit source
unit and a closed, consistently oriented solid, up to 2,500 triangles and 50
independent components. Conversion preserves supplied facets, checks native
validity, bounds and volume, and rejects overlapping components. It does not
guess units, fill holes or reconstruct the original smooth CAD feature history.
Use STEP for smooth surfaces or larger CAD models.

The imported solid can receive normal supported CAD edits and exports. Importing
an arbitrary assembled model does not infer joints or qualify its motion.

## Export representations

Meta proposes declarative operations; CadQuery/OpenCascade constructs the native
geometry. CAD and drawing export use deterministic tools without a model call.
PDF/SVG/DXF use common-scale native projections. The PDF contains an embedded
Unicode font and a parameter appendix; JSON retains the full editable source,
and CSV provides source values with units/meaning. Inactive parameters are
labelled. Drawings measure overall envelopes and are review documents, not
complete tolerance/GD&T manufacturing drawings. STEP/DXF metadata can vary
between otherwise equivalent geometric exports.

Local development verification can be reproduced with:

```powershell
research/vendor/cad-runtime/Scripts/python.exe -m unittest tests.test_folding tests.test_folding_print tests.test_mesh_import tests.test_workspace_drawing
research/vendor/cad-runtime/Scripts/python.exe -m research.verify_folding_demo --output output/forma/folding-new-check --samples 361
```

These are synthetic development checks, not held-out CAD benchmark results.
The separate planner helper requires `--run-paid`; it makes Meta requests and
must remain within the user's approved application cap.
