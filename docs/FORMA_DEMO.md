# Forma hackathon demonstration

Positioning: **Meta AI turns functional requirements into checked, editable engineering revisions.** This fits Push the Frontier by giving a software system a requirement-to-CAD capability backed by executable geometry and numerical checks.

## Three-minute sequence

**0:00–0:20 — State the task.** Open a new 72 L crate. Show that internal clearance, sheet thickness, outside envelope and mass are distinct quantities. The designer wants 80 L within a fixed outside envelope and a 10 kg nominal empty-mass limit.

**0:20–1:00 — Inverse design.** Ask:

> Use polypropylene. Resize as needed to provide at least 80 litres within the existing outside envelope. Find the lightest stock-size design.

Meta interprets the request and invokes the supported stock search. Preview the proposal and inspect the capacity/envelope/mass checks. Expected numerical candidate under reference assumptions: 3 mm polypropylene, 80 L, approximately 2.474 kg. Apply the revision.

**1:00–1:40 — A new requirement changes the conclusion.** Ask:

> Screen a uniformly distributed payload of 20 kg with floor deflection no more than 2 mm. Keep the capacity, mass limit and outside envelope. Find the lightest supported design.

The idealized floor screening and mass limit conflict for the configured polypropylene stock choices. The system must withhold approval. Show the actual failing check or question; never claim a load-safe design from geometry alone.

**1:40–2:15 — Revise the design.** Reply:

> Try those same requirements in birch plywood.

The follow-up should retain the pending 20 kg / 2 mm requirements. Under the stated reference model, 12 mm plywood produces 80 L, approximately 7.343 kg and 1.027 mm idealized floor deflection. Show the preserved requirements and changed thickness/material. These are conditional model results, not physical load certification.

**2:15–2:45 — Verify the artifacts.** Apply, open Drawing and Cut list, then export the package. Show separate valid panel solids in STEP and the reproducible parametric source. Export verification reimports STEP and independently checks a watertight STL union.

**2:45–3:00 — Show measured evidence and boundaries.** Refer to the frozen live integration results and independent verification. State the supported family and the remaining need for joint, tolerance and material qualification. Credit the CAD kernel, libraries and existing API transport. Identify new work built during the event.

## Evidence and claims

- Eight constructed live integration tasks passed initial acceptance, with actual Meta response IDs and local receipts. They are not a public CAD benchmark or real customer trial.
- Unit/property tests cover independent shell arithmetic, 384 seeded geometries, optimization boundaries, proposal checks and CAD exports.
- HTTP checks exercise real project persistence, formats and local access boundaries.
- Any demo using recorded results should label replay. A fresh live request should remain live; do not silently substitute a cached response.
- The model handles intent and tool selection. Fixed code computes numerical values and verdicts. A direct numerical form/search is a baseline already available in the interface; no claim that Meta improves numerical optimization itself.
- Existing research and tools already cover CAD generation and test-guided generation. Claim this implementation's completed workflow and verified scope, not world-first invention.

## Remaining submission work

Obtain one designer-reviewed revision and, if feasible, a physical dimensional-fit demonstration. Publish a sanitized public repository with licenses and event contribution attribution. Record and submit the three-minute video before November 5, 2026, 07:30 IST. None of these outcomes should be represented as completed by the current local tests.
