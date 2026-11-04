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
| Assembly | Separate bodies, sequential planar alignment, offsets, interference checks; five native rigid-panel folding families with hinges and pins | No general simultaneous mate/origami solver; motion qualification is bounded and sampled |
| Inspection | Face area, edge length, point distances, exact BREP distances and planar normal angles | Picked-point distances follow tessellated hit positions; exact results are labeled separately |
| Drawings | BREP projections, hidden lines, measured overall dimensions and editable/movable text notes | Reference annotations cannot override measured geometry; no GD&T or production release |
| Projects | Revisions, undo/redo, named configurations, visibility, colors and portable source | Local single-user workflow, not PLM |
| Import | STEP/STP, closed STL/OBJ with explicit units, single closed DXF profile, portable Studio JSON | Mesh limit 2,500 triangles/50 components; faceted solids, not recovered smooth surfaces/history; no native SLDPRT/SLDASM/DWG history |
| Export | STEP/STL, SVG, Unicode PDF with parameter appendix, 1:1 mm DXF, CSV, portable package and separate folding print pack | STEP retains neutral solids; feature history lives in Studio JSON; print packs require a supported unmodified folding feature |
| Meta | Proposed feature edits, BREP verification, preview and explicit Apply | Quotes establish provenance, not correct interpretation or physical suitability |

## Human editing

Select a feature in Explorer, change parameters and choose **Update feature**. The complete history regenerates. Failed operations retain the last saved geometry and identify the failed feature. Suppression and ordering are versioned edits.

In Sketch, drag a rectangle or circle. Adjust the resulting feature's extrusion, position and Add/Cut/New body operation in Properties. Alt-drag or middle-drag pans the sketch.

In Model, choose Faces or Edges. Ctrl-click selects a pair. Faces expose area, push/pull and body movement; edges expose length and targeted fillet/chamfer. Planar alignment requires two planar faces on different bodies. Positive face offset adds material along the outward normal; negative removes it. Missed cuts, zero-volume and invalid solids are rejected.

In Drawing, add a note, drag to move, or double-click to edit/delete. Notes persist in project and drawing exports. Model dimensions come from analytic BREP bounds, independently of display triangulation. Drawing curves use 0.02 mm chord deflection. PDF text uses Helvetica/Latin-1; SVG and JSON preserve full Unicode.

## Versions and AI

Ctrl+Z restores the parent; Ctrl+Shift+Z restores the latest child. History can branch. Named configurations store feature setups; restoring one creates a revision. Display visibility does not exclude a body from export. CSV contains one row per solid and geometric quantities, without material/cost qualification.

Select a feature or face/edge when asking Meta about "this" geometry. It receives the feature definition and bounded selection metadata, proposes declarative operations, and waits for Apply. It never executes generated Python. Manual edits invalidate an older proposal's apply action. Invalid proposals may receive one BREP-feedback repair attempt.

Enclosure conversion retains the source specification and requirements. Studio recomputes enclosure checks while the panel feature definition matches that source. Geometry edits mark the requirements **stale** and remove current numerical requirement results; restoring the source definition restores current checks. Names, colors and notes do not invalidate the definition. General geometry changes still require requalification in the enclosure workspace. Informational checks use an information marker rather than a passing tick.

The enclosure workspace's **Compare stock designs** opens ranked feasible alternatives with mass, capacity, outside dimensions and mass margin. Selecting an alternative creates an unsaved preview; saving creates a revision. Input changes during search invalidate the comparison. Repeated Studio snapshots cache drawing projections; changing the document invalidates that projection.

## Verification

```powershell
./research/vendor/cad-runtime/Scripts/python.exe -m unittest discover -s tests -p 'test_workspace_*.py' -v
./research/vendor/cad-runtime/Scripts/python.exe -m research.verify_studio_http --directory output/forma/studio/YOUR_NEW_RUN
```

The HTTP harness uses constructed fixtures and real CAD operations, with no model calls. Live feature-edit and unsupported-analysis cases are in `output/forma/studio/live-v1`; they are not external benchmark or physical validation results.

Regressions cover imported filleted plates with holes surviving face offsets, cleanup preserving valid volume, and triangulation not inflating drawing dimensions. Earlier failing attempts remain in `http-v1` and `http-v2`; the second failure was the harness's HTTP method, not a CAD/model failure.

Previous-work attribution remains in `crate_studio/README.md`. TransformControls matches bundled Three.js 0.170.0 and retains its MIT license and download receipt.

## Shared workflow and folding

Project, Canvas and Motion share the Studio revision. See [the workflow guide](FORMA_WORKFLOW.md) for enclosure thickness propagation and [articulated folding and 3D import](FORMA_FOLDING.md) for the five native hinge/pin mechanisms, sampled BREP checks and prepared print packs. The separate enclosure-wall study uses virtual hinges and OBB overlap checks; it does not model physical hardware or loads. Brief/display changes reuse cached geometry and drawings; annotation changes invalidate drawings while reusing geometry.

## Components and working drafts

**Components** inserts geometry into the current saved design. The initial curated library includes socket, hex and button head screws, hex nuts, two USB packages and one DIP package. Hardware uses the pinned Apache-2.0 [cq_warehouse](https://github.com/gumyr/cq_warehouse) dependency; electronics use pinned public KiCad STEP references with [KiCad library licensing](https://www.kicad.org/libraries/license/). Source revision, asset hash, parameters and attribution travel with portable projects and export packages. Hardware has simplified threads and is a fit reference, not a printable thread certification.

Select a library feature and choose **Edit library component** to change its supported size/length. Position and rotation remain editable in the normal inspector. **Insert your STEP / mesh** appends an external STEP/STP/STL/OBJ component, with explicit mesh-unit confirmation. Imported geometry supports placement and downstream CAD operations; its original feature tree is not reconstructed. Native geometry is rechecked before saving a new revision; adding a component does not automatically qualify mates, motion, electrical behaviour or physical fit. The bounded document limit is 120 features and 50 bodies. Motion retains its separate limits.

In **Design with tools** mode, **Live view** follows successful native candidate builds in a read-only 3D/drawing window. This displays tool-produced drafts between model decisions, rather than token-level animation. The saved design stays unchanged until a ready proposal is applied. Existing human edits invalidate stale proposals; drafts are never physical approval.

Run the optional source acceptance audit with `python -m research.verify_component_catalog --output output/forma/YOUR_RUN --electronics`. It downloads only the three pinned KiCad assets, validates their Git blob hashes and checks native solids, STEP read-back and placement. It makes no model calls and does not test electrical behaviour, friction, loads or actual manufacturing fit.

## Drawings and mechanical print handoff

New drawings use aligned third-angle top/front/right views with shared calibrated scale, native overall W/D/H dimensions, a native isometric view, source revision and feature hash, a part list and a paper calibration ruler. **Drawing layout** can retain a legacy sheet or switch to aligned views; existing REF notes keep their sheet coordinates. **Section…** adds editable native X/Y/Z cuts for all or selected bodies. Cut material is hatched and holes remain open. Sections appear in the PDF, separate SVG sheets and 1:1 model-space DXF layers. Full editable parameters remain in source JSON and CSV. Material and fit tolerances are unspecified until explicitly supplied; this is a geometry drawing, not manufacturing certification.

**Export → Print & assembly pack** prepares ordinary native solids as separate oriented STLs, provisional non-overlapping bed plates, an assembly STEP, a portable project and a deterministic handbook with part/state/section sheets and retained installation stages. Plate and part meshes are reopened and checked against native solids. Orientation maximizes actual planar bed contact among six axial poses; support, adhesion, printer profile and physical fit still require slicer/operator review. Retained installation, capture and lock/end-stop acceptance targets must pass before release. Folding assemblies use their dedicated hinge/coupon exporter. No machine-specific G-code or reliable print-time estimate is generated.

Saved-revision payloads use bounded exact process-local reuse, including actual imported asset byte identities. Warm history reads bypass the native worker lock. Cold geometry edits and new native studies still require the CAD worker; a request timeout does not guarantee that server-side work stopped.

Geometry-only snapshots for a new label or section revision can also reuse an already owned, checked native build while an unrelated study is running. New or changed solids and imported asset bytes still require native work; vector projections remain serialized.

Drawing and live-preview requests keep one projection in flight and collapse rapid revision changes to the latest source. Obsolete vectors cannot replace the current revision, and leaving the drawing view prevents queued projections from starting.

Studio loads checked 3D geometry before computing vector drawings. Drawing, Canvas and the live draft's Drawing view request exact native projections when needed; stale source, package or imported-asset responses cannot replace the current view. Export and engineering verification still generate full native drawings. Revision labels and notes reuse owned projection curves without reusing stale sheet text. A normal save validates and persists in one request.

Ordinary geometry exports verify STEP/STL readback and native drawings without starting a new general mechanism analysis. Their workflow report retains source-bound review status and explicitly labels motion as not rechecked during export. Use Motion or Recheck native study for current collision evidence. Print & assembly pack retains its mandatory assembly, capture and lock/end-stop release checks. Wheel scrolling over numeric inspector fields does not change dimensions.
