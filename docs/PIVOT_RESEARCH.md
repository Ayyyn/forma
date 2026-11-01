# Direction decision: material revisions for static display fixtures

October 27, 2026. Research and feasibility decision; proposed product features below are not implemented yet. The existing origami studio remains available. Physical origami verification is deferred at the user's request.

## Decision

Build **Design Continuum / Revision Desk**: a workspace that turns customer material-change requests into explicit, reviewable design revisions, checks their geometric consequences, and regenerates a consistent presentation and vendor package for one supported static panel assembly.

First demo: a small retail display casing, representing a bounded part of stall/display work. It has several flat panels around a fixed support/frame, editable dimensions, thickness and material appearance. Scope the panel geometry and interfaces explicitly. Avoid presenting it as a load-bearing crate or an engineered steel-to-plastic replacement.

The workflow comes from the user's report of a three-hour conversation with a product designer: static stalls/crates, mostly SolidWorks, customer-driven revisions, and a steel-to-plastic change propagating through thickness, dimensions, render, CAD and vendor drawing. The friend did not identify an obvious AI/software opportunity. This is evidence of a reported annoyance, not measured time savings, willingness to adopt, or completed customer validation.

## Directions compared

These are engineering judgments, not predicted judging scores.

| Direction | Useful result | AI role | Prior-art/scope problem | Decision |
|---|---|---|---|---|
| General brief/image-to-CAD canvas | Broad design creation | Interpret references and generate CAD | Directly overlaps mature CAD/AI products; arbitrary geometry, native edits and drawings too broad | Reject for this hackathon |
| Origami/mechanism discovery | Compact moving geometries | Search planning | Weak fit to the reported workflow and limited evidence of practical AI advantage | Preserve research, stop expanding |
| Standalone drawing auditor | Highlight vendor-drawing mistakes | Read and reconcile documents | Drawing QA and revision comparison already exist; risk of ending at annotations | Useful component, not central demo |
| Thickness-aware crate/box generator | Fast cut files | Translate parameters | Boxes.py, LaserSVG and CAD configurators already address parameter propagation | Use known techniques; no novelty claim |
| Material-revision desk for static displays | Resolve a real change request and produce a coherent next revision | Ground informal intent, identify missing decisions, propose edits and explain computed conflicts | Adoption unproven; must outperform a properly parameterized CAD workflow on a specific task | **Selected** |

## What already exists

- SolidWorks global variables propagate dimensional changes, and model dimensions are associated with drawings. Automatic updates are not our invention. [Global variables](https://help.solidworks.com/2024/English/SWConnected/swdotworks/c_global_variables.htm), [drawing dimensions](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_Dimensions_in_Drawings.htm).
- DriveWorks automates SolidWorks parts, assemblies, drawings and related documentation from captured parameters and rules. A thickness slider driving documents is insufficient differentiation. [Design automation](https://www.driveworks.co.uk/solutions/design-automation/).
- SolidWorks advertises AI companions and drawing/model assistance; capability availability varies across releases. We reviewed documentation/marketing, not a hands-on competitive test. [Official AI overview](https://www.solidworks.com/product/solidworks-design/ai-overview).
- Zoo documents conversational generation/editing of parametric CAD from prompts and images. General text-to-CAD is crowded. [Official FAQ](https://zoo.dev/docs/faq).
- DraftGuard advertises drawing/document checks, revision comparison, evidence and proposed fixes. Document consistency alone cannot establish uniqueness. [Product page](https://www.genaisys.ai/draftguard.html).
- LaserSVG already addresses semantically responsive fabrication templates, and Boxes.py supports material thickness and machine-dependent kerf. [LaserSVG](https://arxiv.org/abs/2209.00116), [Boxes.py manual](https://florianfesti.github.io/boxes/html/usermanual.html).
- Engineering evaluation of controlled CAD edits and intent preservation is also established research. [CADEngBench](https://arxiv.org/abs/2608.09296). Our test set would be a scoped project contribution, not the first such benchmark.

## Defensible contribution

Proposed wording, valid only after implementation and evaluation:

> We built and evaluated a Meta-powered material-revision workflow for static display-panel assemblies. Informal changes become evidence-linked edits with explicit preserved requirements; a deterministic checker detects conflicts and uncertainty, and approved revisions regenerate geometry, visualizations and vendor documents from one versioned model.

The contribution is this implemented workflow and its measured behavior. Do not claim the first AI CAD system, a new material-selection algorithm, novel parametric propagation, universal drawing QA, a novel geometric mechanism, or certified manufacturability. The research does not establish a world-first combination either. Differentiation must be demonstrated through a specific useful interaction and evaluation, rather than asserted from a feature list.

## Three-minute demonstration

1. **Existing design and request.** A dimensioned static display casing, colored geometry and vendor drawing appear on linked canvas cards. Customer asks for plastic instead of steel to reduce cost. The system extracts that request and shows missing grade, stock thickness, process, price and suitability decisions. Budget motivation is not evidence that plastic is cheaper.
2. **Designer supplies decisions.** For a clearly labeled synthetic example, approved sheet thickness changes from 1.2 to 6 mm. Outer width is locked to 600 mm; required clear opening is at least 594 mm. The inset-side-panel model predicts an opening of 588 mm. The conflict is shown on the model and drawing, with the requirement and request that caused it.
3. **Review a quantified compromise.** Keeping 6 mm panels requires at least 606 mm outside width at nominal dimensions. The customer/designer explicitly authorizes a dimensional compromise, rather than the AI quietly weakening the opening requirement. With supplied width tolerance ±0.5 mm and thickness tolerance ±0.2 mm, nominal 606 mm yields a worst-case opening of 593.1 mm; 607 mm yields 594.1 mm. These tolerance values are synthetic fixture inputs, not vendor guidance.
4. **Apply one coherent revision.** The application regenerates its supported editable model, colored render, orthographic views, panel cut drawings and BOM. Show actual changed dimensions and material/thickness notes, not just an animation. A deliberately stale old drawing is blocked from the proposed handoff package by revision and content checks. Retain the before/after diff and unresolved review items.
5. **Export.** Download a proposed-revision bundle: PDF drawings, SVG/DXF panel files, BOM CSV, editable project JSON and a change/evidence manifest. Unresolved material, attachment or strength checks remain labeled; geometry passing is not manufacturing approval.

The 600/594/6 mm example is deliberately simple enough for a judge to verify mentally. The product must also handle fresh dimensions and differently worded requests. It is not a one-example hardcoded demonstration.

## AI and deterministic responsibilities

Meta Spark Open on the already-working Baseten route interprets freeform requests and, within tested capability, reference drawing annotations. It proposes typed edits with source spans, identifies ambiguity, and explains tool-computed options. It must distinguish current achieved dimensions from minimum requirements, explicit units from guesses, designer authority from a supplier suggestion, and facts from assumptions.

The engine owns unit conversion/rechecking, geometry, dimensional dependencies, interval bounds, nominal part fit, supported interface checks, versioning, export generation and read-back consistency. The model cannot replace the rules, silently relax a lock, invent material properties or declare its own proposal verified. A syntactically valid edit still requires semantic review against the brief.

Use bounded inference per revision; a second request is justified only by a meaningful clarification or actual validation feedback. Avoid adding agents or models merely to increase the tool count. Existing text/vision APIs are sufficient; image generation is not required.

## Scope of the first implementation

- One family of flat-panel static display casings; a bounded set of panel, aperture and mounting features. Geometry and dimensions are editable through direct controls and typed AI patches.
- Real modeled thickness and supplied dimensional tolerances. Simple assembly/exploded views; no dynamics or FEA in the acceptance path.
- One versioned design graph drives deterministic 3D meshes, orthographic drawings, BOM and fabrication outlines. A model-based colored render remains geometrically tied to the model; generated concept art is unnecessary.
- Reference PDF/image ingestion extracts candidate facts, not arbitrary hidden 3D geometry. Users confirm scale, dimension anchors and mappings when evidence is insufficient. Uploaded vendor text is data, not authority to override requirements.
- A warm neutral canvas with left-to-right cards: request/reference -> approved intent -> before/after geometry -> checks -> drawings/handoff. Pan, zoom, minimap and a pinned 3D preview support navigation. Stable feature identifiers connect selections across cards. The canvas layout is UX, not the novelty claim.
- PDF/SVG/DXF/CSV/project JSON are the initial formats. DXF is not DWG. Arbitrary native SLDPRT/SLDASM history import and round-trip editing are outside the first demo. A SolidWorks parameter/change manifest is useful, but not native integration.

The last limitation matters: the friend works in SolidWorks. A standalone demo establishes capability, not that their actual file workflow has been improved. Test whether a verified change package is useful alongside their CAD process. If copying work into our representation costs more than the revision saves, the integration or product scope must change.

## Feasibility evidence collected now

`research/revision-direction-probe.json` preserves one actual Muse Spark Open request containing five synthetic text cases, the public typed output and deterministic arithmetic checks. HTTP 200, roughly 7.6 seconds, 3,719 reported tokens. Cases cover unspecified plastic replacement, explicit conflicting stock thickness, an authorized width change, inch-to-mm conversion and a cost request without cost inputs. All six narrow structural/arithmetic checks passed.

Manual review exposed a semantic risk in case A: the current opening is 597.6 mm, but the model's clarification restated only the old 594 mm minimum despite a request to keep the current opening. It correctly requested more input; that does not make the restatement fully faithful. Cases C/D also have zero nominal fit margin without supplied tolerances. The output is promising evidence that the typed proposal role is feasible, not proof of reliable design intent, vision capability on engineering drawings, CAD generation, usability or manufacturing validity.

Local Python already has Shapely, SciPy, NumPy and the existing API stack. CadQuery/OCP and ezdxf are absent in the ordinary runtime. Restricted planar panel geometry can start with polygon operations and deterministic extrusions; a full B-rep kernel is not a prerequisite for the scoped mesh/SVG demonstration. DXF export and arbitrary panel holes/mesh triangulation need separate validation. STEP requires a real solid kernel and is deferred unless the core flow is complete. We have not installed new CAD tooling or replaced the studio in this research task.

## Evaluation and build order

First, freeze a small set of realistic revision tasks: explicit changes, ambiguous requests, conflicting locks, mixed units, missing material/price inputs, tolerance failures and stale artifacts. Ask the friend to review the wording and expected outcomes through the user. Keep at least several tasks unseen during prompting. Do not count correlated rephrasings as independent customer problems.

Compare (a) a typed parametric form using the same engine, (b) a simple deterministic request parser with the same engine, and (c) Meta grounded proposals with the same engine. Measure total user time, clarification burden, intent correctness, unauthorized changes, uncertainty handling and final artifact consistency. Include a properly parameterized SolidWorks workflow if the friend can demonstrate it. The AI must earn its role through semantic task performance; it need not beat CAD at computing geometry.

Build in this order:

1. Versioned panel assembly, invariants, source references and deterministic export/read-back checks. The locked-width conflict and tolerance examples must work without AI.
2. Typed Meta revision proposals, explicit clarification and a reviewable transaction/rollback. Test retained intent, not just JSON validity.
3. Linked canvas, colored model, before/after comparison and vendor bundle. Exactness takes priority over canvas polish.
4. One anonymized real revision replay or designer review, followed by held-out evaluation and fixes. Native SolidWorks integration remains a separate feasibility milestone.
5. Freeze scope, host the working app, publish eligible source and produce the three-minute demo before the November 4, 21:00 EST deadline (November 5, 07:30 IST).

Go/no-go: if no specific revision shows value relative to the friend's existing CAD method, stop expanding the standalone editor and reassess. If extraction needs manual correction, retain the correction workflow and report its cost. If material/structural approval remains unknown, export a proposed revision with open issues rather than a manufacturing-approved claim.
