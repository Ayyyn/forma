# End-to-end demonstration — foldable instrument case

Open `http://127.0.0.1:8770/evaluation`, then **Open project canvas**. The review links to each immutable revision so the demonstration can be repeated without new model calls. A portable copy is in `examples/forma-instrument-case.json`.

## Suggested three-minute walkthrough

1. **Intent and requirements.** Open the first timeline revision. Show the synthetic 90 × 60 × 45 mm clear enclosure, polypropylene reference profile and 3 mm panels. The contract retains at least 0.2 L capacity and a 160 × 120 × 80 mm closed envelope. Show Project and compare stock options; nine are feasible in this bounded catalogue, with 3/4/5 mm as the first three.
2. **Real Meta revision.** Open revision 02. It applies the retained verified response from frozen evaluation task r11: all panels change from 3 mm to 4 mm, while clear dimensions, requirements and brief remain unchanged. Show the feature dimensions, regenerated drawing and current requirement results. Explain that this is a retained real response, not a fresh live inference or an independently sampled replay.
3. **Human control.** Open revision 03. A human edit changes clear height to 50 mm and refines the brief. Show the updated solid bodies and drawing. The brief and geometry are ordinary editable project state.
4. **Motion and package.** Open revision 04, then Motion. Run its saved 37-pose study, choose **Focus view** for a larger viewport, then play or scrub from 0 to 90°, and inspect the envelope graph. Closed envelope is 98 × 68 × 54 mm; outward-flat virtual motion envelope is 198 × 168 × 8 mm. Show the assumptions: rigid finite-thickness panels, virtual hinges, prescribed motion and sampled overlap checks.
5. **Evidence and fabrication.** Return to the evaluation review. Show the initial 19/20 and 10/11 results, the targeted repair and retained slot ambiguity. Download the fabrication package: separate flat panel STEP/STL files, drawings, portable project, checks and hashes. The largest flat component is 98 × 68 × 4 mm; printer fit and the actual material still require checking.

The camera and canvas can be moved freely. Canvas buttons open the stage editors; project-specific history keeps this four-revision story visible, and **Show all local designs** retains access to earlier work and QA fixtures.

## Physical follow-up

Use the separate components rather than printing the assembled union mesh as a moving mechanism. Start with a thickness/hinge coupon, then arrange individual panels in the slicer. No designed hinge hardware is included; a temporary external/tape hinge can approximate the virtual axis for a low-load mockup. Record real dimensions, material, print settings and interference. Do not present the reference polypropylene calculations as qualification of another printed material.

The demo manifest and package live under `output/forma/demo-v1/`. Actual printing and measurements are pending.
