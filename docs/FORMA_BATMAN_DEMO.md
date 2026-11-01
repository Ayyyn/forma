# Batman emblem: brief to editable CAD and print export

The local Forma project is a symmetric bat silhouette, **76.2 × 31 × 3 mm**.
Three inches converts exactly to 76.2 mm. The design uses a closed 126-point
polyline and a positive Z extrusion, with its flat underside at Z=0. The curved
regions are sampled cubic Beziers; the saved CAD contains editable straight
sketch segments. This was explicitly authored from the brief, with zero Meta
API calls; it is not a model-generation benchmark result.

Import `examples/forma-batman-logo.json` in Studio to retain the outline,
extrusion, brief, color and drawing note. Select the extrusion in Explorer,
open Properties, and edit its height or polyline points. Drawings regenerate
from the BREP. Overall dimensions are measured; manual notes are editable
reference text. STL is an export, not the editable master.

The local demo history starts with a saved brief and then adds the sketch and
extrusion. A real browser edit changed thickness from 3 to 4 mm and restored
3 mm in a new revision. The final drawing shows 76.2 mm width, 31 mm height
and 3 mm thickness. The Studio STL download was exercised through its UI.

`research/build_batman_demo.py` creates the project through the running local
app, downloads its actual export bundle, checks file hashes, reimports STEP
and STL, audits DXF, compares all three measured drawing views, checks mirror
symmetry, and independently computes polygon area and extrusion volume.
Rerun verification without creating another project:

```powershell
.\research\vendor\cad-runtime\Scripts\python.exe -m research.build_batman_demo --verify DOCUMENT_ID
```

The generated `output/forma/batman-logo/results.json` binds the checks to a
saved revision. `batman-logo-package.zip` includes STL, STEP, SVG/PDF/DXF
drawings, editable portable project, body list and checksums. Convenient STL,
STEP and PDF copies are alongside it. Screenshots and the browser edit receipt
are retained there too.

Import the STL into a slicer **in millimetres at 100% scale**, with its broad
flat face on the bed. It is a single connected, watertight solid. Printer,
material, extrusion settings and toolpath have not been selected, and no
physical print has been performed.

## Meta-selected keyring attachment

The follow-up explicitly delegated dimension and placement choices to Meta.
No attachment dimensions were supplied in that generation prompt. Muse Wonder
returned a ready proposal in one response, choosing a 14 mm diameter circular
lug, 6 mm through-hole, and 6 × 17 mm connecting neck, all 3 mm thick. Its lug
centre is (0, 22) mm. The overall envelope becomes 76.2 × 46 × 3 mm.

The original bat feature, notes and other document fields remain unchanged.
Three appended features describe the neck, round lug and cylindrical cut.
`examples/forma-batman-keyring-meta.json` is the exact portable model result;
Codex did not correct its geometry. The preceding underspecified prompt had
returned clarification questions; it is retained separately. The successful
delegated generation cost an estimated $0.120576, with billing unverified.

`research/verify_batman_attachment.py` checks the retained result before applying
it, then verifies actual app exports. All 25 checks passed: the original solid
is a subset of the result, the neck has positive-volume overlap with the bat,
the cylindrical hole is entirely outside the original bat, the bore is open
through the thickness, the mesh is one connected watertight component with one
hole, STEP retains analytic circle radii, and measured drawings and editable
sources agree. Hole clearance and surrounding material are also sampled; they
are geometric checks, not physical ring-fit or strength tests.

Artifacts are in `output/forma/batman-logo/keyring/`, including the unedited
model provenance, verification report, updated CAD/print package and screenshots.
This is one interactive demonstration, excluded from the frozen benchmark.
