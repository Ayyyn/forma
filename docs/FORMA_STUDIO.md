# Forma CAD Studio

Open `http://127.0.0.1:8770/studio`. The enclosure workspace's **CAD Studio** button converts its saved panels into individually editable solid bodies. The original enclosure revision remains available.

Studio is a bounded CAD editor built on OpenCascade. It implements the operations below; it is not feature parity with AutoCAD or SolidWorks.

| Area | Implemented | Boundary |
|---|---|---|
| Parametric editing | Ordered feature tree, driving parameter forms, suppression, deletion, reorder and regeneration | Face/edge references are ordinal; topology changes can require reselection |
| Sketches | Rectangle, circle and imported closed polygon profiles; grid snap, pan/zoom, dimensional editing and extrusion | XY profiles, not a general sketch-constraint solver |
| Solid features | Boxes, cylinders, holes, pockets, booleans, fillets, chamfers, mirror, linear pattern | Invalid operations stop downstream regeneration |
| Direct editing | Planar face push/pull on native or imported STEP geometry; selected-edge fillet/chamfer | No curved-face offsets or arbitrary surface deformation |
| Manipulation | Genuine 3D translation handles, numeric translation/rotation | Rotations use the global origin, followed by translation |
| Assembly | Separate bodies, placement, sequential planar-face alignment, offsets and interference checks | No simultaneous multi-mate solver or kinematic mechanism simulation |
| Inspection | Face area, edge length, point distances, exact BREP distances and planar normal angles | Picked-point distances follow tessellated hit positions; exact results are labeled separately |
| Drawings | BREP projections, hidden lines, measured overall dimensions and editable/movable text notes | Reference annotations cannot override measured geometry; no GD&T or production release |
| Projects | Revisions, undo/redo, named configurations, visibility, colors and portable source | Local single-user workflow, not PLM |
| Import | STEP/STP, single closed DXF profile with declared units, portable Studio JSON | No native SLDPRT/SLDASM/DWG history or arbitrary mesh editing |
| Export | STEP, STL, SVG, PDF, 1:1 mm DXF, body-list CSV and portable package | STEP retains neutral solids; feature history lives in Studio JSON |
| Meta | Proposed feature edits, BREP verification, preview and explicit Apply | Quotes establish provenance, not correct interpretation or physical suitability |

## Human editing

Select a feature in Explorer, change parameters and choose **Update feature**. The complete history regenerates. Failed operations retain the last saved geometry and identify the failed feature. Suppression and ordering are versioned edits.

In Sketch, drag a rectangle or circle. Adjust the resulting feature's extrusion, position and Add/Cut/New body operation in Properties. Alt-drag or middle-drag pans the sketch.

In Model, choose Faces or Edges. Ctrl-click selects a pair. Faces expose area, push/pull and body movement; edges expose length and targeted fillet/chamfer. Planar alignment requires two planar faces on different bodies. Positive face offset adds material along the outward normal; negative removes it. Missed cuts, zero-volume and invalid solids are rejected.

In Drawing, add a note, drag to move, or double-click to edit/delete. Notes persist in project and drawing exports. Model dimensions come from analytic BREP bounds, independently of display triangulation. Drawing curves use 0.02 mm chord deflection. PDF text uses Helvetica/Latin-1; SVG and JSON preserve full Unicode.

## Versions and AI

Ctrl+Z restores the parent; Ctrl+Shift+Z restores the latest child. History can branch. Named configurations store feature setups; restoring one creates a revision. Display visibility does not exclude a body from export. CSV contains one row per solid and geometric quantities, without material/cost qualification.

Select a feature or face/edge when asking Meta about "this" geometry. It receives the feature definition and bounded selection metadata, proposes declarative operations, and waits for Apply. It never executes generated Python. Manual edits invalidate an older proposal's apply action. Invalid proposals may receive one BREP-feedback repair attempt.

General Studio edits do not automatically requalify the enclosure workspace's capacity/load requirements. Conversion retains the source context and shows this boundary. Use the enclosure workspace for its supported inverse sizing.

## Verification

```powershell
./research/vendor/cad-runtime/Scripts/python.exe -m unittest discover -s tests -p 'test_workspace_*.py' -v
./research/vendor/cad-runtime/Scripts/python.exe -m research.verify_studio_http --directory output/forma/studio/YOUR_NEW_RUN
```

The HTTP harness uses constructed fixtures and real CAD operations, with no model calls. Live feature-edit and unsupported-analysis cases are in `output/forma/studio/live-v1`; they are not external benchmark or physical validation results.

Regressions cover imported filleted plates with holes surviving face offsets, cleanup preserving valid volume, and triangulation not inflating drawing dimensions. Earlier failing attempts remain in `http-v1` and `http-v2`; the second failure was the harness's HTTP method, not a CAD/model failure.

Previous-work attribution remains in `crate_studio/README.md`. TransformControls matches bundled Three.js 0.170.0 and retains its MIT license and download receipt.
