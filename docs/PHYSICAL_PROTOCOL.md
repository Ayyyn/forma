# Paper prototype measurement protocol

Status: not yet fabricated or measured. The PDF illustrations and reference dimensions are computed geometry.

Use `output/pdf/paper-model-print-pack.pdf`: page 1 is the actual-size pattern, page 2 explains folding, and page 3 is a blank measurement worksheet. The pack belongs to design `bbbf31e211`, selected by actual single-pass Meta run `ebd847afdf79`. Earlier exports in `examples/` belong to a different design; do not combine their measurements.

1. Print **page 1 only**, A4 landscape, Actual size / 100%. Disable fit, shrink and borderless enlargement. The connected blank is 246.02 × 151.67 mm. Check both the 100 mm horizontal and 50 mm vertical bars before cutting. Suggested practical gates are within 1 mm and 0.5 mm respectively; otherwise fix scaling and reprint. These are procedural choices, not claims about ruler accuracy. Record both readings.
2. Use ordinary thin printer paper first. Record its actual brand, weight and thickness if known. Cut only the black outside outline; keep the sheet connected. Interior red dash-dot / M lines are mountains, and blue dashed / V lines are valleys, viewed from the printed side. Line styles and letters also work in grayscale.
3. Place the printed face upwards. A mountain is a raised ridge; a valley is a depressed trough. Use a ruler and fingers to precrease each straight marked segment gently, then reopen it. Stop at junctions; a kinked zigzag is not one straight fold. Work one band at a time.
4. Gradually bring the left and right edges together, nudging ridges up and troughs down. Allow the top and bottom edges to move too. Several folds must move together. If a corner jams, reopen slightly and check its M/V signs. Begin with a comfortable partial fold, using the 45° illustration as a visual reference. This exact paper sequence has not been physically tested here; record difficulty rather than forcing a packed pose.
5. Set the lowest troughs on a level table, keeping the pose stable. X runs along the numbered columns; Y runs from row A to D. Measure the **entire outside extent**, including chevron overhangs, along X and Y. Measure H from the table to the highest crest. H includes real paper thickness, which the ideal model omits. Take three readings without intentionally changing the pose, then gently try a more packed pose and repeat. Keep failed trials and springback notes.
6. If you can independently measure facet inclination, record it in `theta_measured_deg` and compare all dimensions at that angle. Resemblance to the 45° drawing is not an angle measurement. Otherwise leave the angle blank: the tool infers an ideal angle from H and compares X/Y only. H is then an input, not independent validation. Out-of-range heights are flagged rather than clamped into agreement.
7. Fill `output/paper/measurements.csv`, leaving unmeasured values blank. Record ruler resolution, procedure uncertainty, material and date. Photograph the sample from above and from the side with a ruler if practical. Repeat readings do not measure refolding reproducibility; that needs separate reopen/refold trials.
8. Run `python scripts/compare_paper_measurements.py`. It preserves blank and rejected trials and reports signed and relative residuals. It does not invent an experimental pass/fail threshold. Assess residuals alongside uncertainty, thickness, panel bending, crease obstruction and springback.

| Computed reference pose | X (mm) | Y (mm) | H (mm) |
|---|---:|---:|---:|
| Deployed, 8° | 244.06 | 151.53 | 3.11 |
| Partial, 45° | 189.09 | 145.21 | 15.78 |
| Packed, 87.359144° | 110.69 | 22.93 | 22.29 |

Compare at the same angle. Agreement would support this sample and protocol; strength, self-locking, durability, finite-thickness packing and repeatable operation remain unverified.

General folding background: [Woodruff's ENGN250 Miura folding lab, first three pages](https://www.stevenrwoodruff.com/wp-content/uploads/2023/05/ENGN250_S23_AllHandouts.pdf). The pattern and pose drawings are generated from this project's geometry.

To regenerate the manifest/exports: `python scripts/prepare_paper_model.py --run ebd847afdf79`. Existing measurement CSV files are preserved; check their design IDs when changing designs. Render the PDF with `python scripts/create_paper_print_pack.py` in an environment with ReportLab.
