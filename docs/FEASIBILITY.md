# First prototype decision — October 27, 2026

The supplied participant guide is the current competition reference: Impact 30%, Meta tooling 25%, technical execution 20%, demo 25%. It supersedes the handoff's equal weights. Public repository, new work, working product, and a three-minute video are required. Submission is November 5, 2026, 07:30 India time (November 4, 21:00 EST). No repository is published yet.

## Comparison

Scores are engineering judgments, not measured outcomes. All columns use 1–5 (higher is better); equal-weight total makes trade-offs explicit rather than pretending to predict judges.

| Initial demonstration | Impact | Distinctive exploration | Meaningful Meta decisions | Mathematical validity in time | Demo appeal | Implementation feasibility | Paper prototype | Total /35 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Two-capacity reconfigurable container | 4 | 5 | 4 | 2 | 5 | 2 | 3 | 25 |
| Multifunction tabletop stand / scissor linkage | 3 | 3 | 4 | 4 | 4 | 4 | 4 | 26 |
| Deployable panel: accordion versus Miura | 4 | 3 | 4 | 5 | 5 | 5 | 5 | 31 |

Choose the deployable panel. A bounded design domain has enough discrete and continuous freedom (fold family, panel grid, facet lengths, sector angle, operating angles) to explore useful trade-offs. It also supports fabrication without a printer or workshop beyond ordinary paper printing. This is a geometrical precursor to portable field panels, markers, and folding surface substrates, not a certified shelter, solar array, or structural product.

The first brief asks for at least 240 × 150 mm deployed extent, a packed envelope no larger than 120 × 45 × 24 mm, and a blank fitting A4 landscape with 10 mm margins. Minimize material area and crease segments. Miura contracts in two directions; an accordion preserves one width. An early 155 mm pocket experiment found feasible examples in both families after rotating the package; the chosen 120 mm pocket needs biaxial contraction because the deployed width is at least 150 mm. The UI keeps pocket dimensions editable, so the model must compare real trade-offs rather than always recommending Miura. Accordion facets span the full width (`rows=1`) to avoid counting artificial coplanar subdivisions as fabrication creases. Both are established mechanisms, not our inventions. A deterministic search remains the baseline; no claim of AI superiority is justified yet.

## Sources and established tools

- Schenk & Guest (2013), [Geometry of Miura-folded metamaterials](https://doi.org/10.1073/pnas.1217998110): closed-form unit-cell dimensions and ideal folding kinematics. We use the established geometry and derive our own vertex construction; we make no material-mechanics claim from it.
- [Origami Simulator](https://github.com/amandaghassaei/OrigamiSimulator), [MIT license](https://github.com/amandaghassaei/OrigamiSimulator/blob/main/LICENSE): interactive GPU force-based folding, strain display, SVG/FOLD import. Valuable for general patterns, but an approximate relaxation solver is unnecessary for this analytically parameterized first family. No code copied.
- Suto et al., [Crane](https://narumi.me/crane/): already integrates design, folding simulation, inverse constraints, thickening and fabrication in Grasshopper. Therefore an AI chat veneer on those features would not constitute novelty. We do not install or redistribute it.
- Tachi, [Freeform Origami and related tools](https://origami.c.u-tokyo.ac.jp/~tachi/software/): proprietary terms require advance contact and distinguish commercial use. Not a dependency.
- [FOLD specification and tools](https://github.com/edemaine/fold): mesh/crease interchange, MIT-licensed tooling. Export the documented JSON representation; no library code copied.
- Chen et al., [Symmetric waterbomb origami](https://pmc.ncbi.nlm.nih.gov/articles/PMC4950188/), and [Folding of Tubular Waterbomb](https://pmc.ncbi.nlm.nih.gov/articles/PMC7171592/): multiple folding modes and possible rigid/nonrigid transitions are reasons to postpone a general tubular container.
- Langbecker, [Kinematic Analysis of Deployable Scissor Structures](https://doi.org/10.1260/0266351991494650): supports the feasibility of exact linkage kinematics, while a useful stand would still need locking, connections and load evidence.

## Architecture and limits

- Python/FastAPI, Pydantic input contracts, NumPy geometry. No elastic simulator or CAD solid kernel is necessary for a grid of planar quadrilaterals. This is a mechanism model, not FEA.
- `Design` stores family, rows/columns, facet side lengths, sector angle, and deployed/packed states, in mm and degrees. `Requirements` separates target dimensions and fabrication limits.
- Geometry returns vertices, quads, edges, measured extents, projected coverage, material area, and explicit constraint violations. UI receives computed meshes and a sampled animation; it does not invent results.
- Independent checks use facet distances and diagonals, cross-product area, planarity, topology, an alternate trigonometric derivation, known configurations, invalid input, fixed-seed search, and export consistency.
- Continuous zero-thickness nonintersection follows from the strictly positive planar cell map in the nonsingular angle domain. This says nothing about finite-thickness interference or hinge clearances. Sheet thickness, strength, crease springback and self-locking are unmodeled.
- A seeded bounded search produces candidates and a nondominated material/crease/packed-area comparison. Meta proposes tool calls and reads actual evaluations; logs store public outputs, validated tool arguments, tool results and token usage, never raw private reasoning.
- Local static UI served by the API: warm drafting-paper palette, orbitable 3D panel, deploy slider, dimensions, candidate comparisons, constraint evidence and SVG/FOLD export.
- Prototype protocol: print at 100%, check the scale bar, precrease, measure both extents and corrugation height, record actual values. No physical measurements have been made.

## Demo sequence

1. Ask for a pocketable field panel with explicit deployed and packed envelopes.
2. Show a computed naive accordion candidate failing its packed envelope, including corrugation height.
3. Let a real Meta agent inspect the failure, propose Miura, and call bounded design evaluation/search tools.
4. Compare feasible and rejected designs; show what fewer creases costs in material or compactness.
5. Scrub the real rigid-folding geometry, inspect invariant errors, and export a printable pattern.
6. Later add a real paper sample and measurements. Until then label experimental validation pending.

The first delivery should establish a complete, inspectable prototype, not the entire invention studio. Remaining competition work includes a controlled agent-versus-baseline evaluation, experimental measurements, hosting, public repository, and demo video.
