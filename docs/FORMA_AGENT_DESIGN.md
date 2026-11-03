# Muse design-agent engineering standard

This is a development contract, not a claim that the target architecture is implemented. It applies to new designs and revisions, including the adjustable box. The product goal is correct, verified, practical and visually considered output with measured interactive performance.

## Existing pipeline and target

Quick edit uses one `muse-wonder-1.0` planner conversation, supported declarative feature operations, deterministic regeneration/validation and at most one feedback repair. Exact proposal cache hits revalidate without a new model call. The opt-in [Design with tools mode](FORMA_DESIGN_TOOLS.md) adds a bounded, single-conversation tool loop with candidate branches, native inspection, actual CAD images, sampled rigid-body mechanisms and checked exports. There is no cooperating multi-agent mechanism-design system or arbitrary mechanism solver today. See `crate_studio/workspace_agent.py` and `crate_studio/design_agent.py`.

Extend that path toward requirements → alternative mechanisms → editable assembly → tool verification → targeted revision → visual review → export qualification. These stages need not be separate model agents. Compare role separation against a single-agent control before promoting it.

## Requirements and engineering judgment

- Keep units, required dimensions, variable dimensions, material, loads, manufacturing process and unknowns explicit. Label provisional assumptions and preserve the user's constraints across revisions.
- Choose mechanisms from requirements, not a fixed preferred family. Consider assembly, actuation, stability after release, locking, clearance, retention, access, serviceability and material behavior when relevant.
- Separate measured geometry, analytical estimates, sampled kinematics, physical simulation and physical tests. State what each actually supports. Unknown load/material properties remain unknown.
- Keep a human-editable source of truth. A changed parameter invalidates dependent drawings, motion, manufacturing checks and exports until regenerated or requalified.

## Engineering tools

Expose applicable tools through explicit typed calls with inputs, units, revision identity, limits, outputs and structured failure feedback. Available integrations should be discoverable by the design agent; unavailable operations must be reported honestly. Desired coverage includes:

| Tool area | Intended use |
|---|---|
| Project inspection and editing | Read requirements, feature history, selections, imported geometry and prior verified revisions; propose editable changes |
| Geometry and assembly | Create native solids, measure dimensions/thickness, inspect topology and contacts, place components and evaluate compatible constraints |
| Mechanism checks | Evaluate declared motion paths, joint closure, finite-volume interference and locking behavior with the appropriate implemented method |
| Visual inspection | Render consistent views, inspect geometry/drawings and identify proportions, usability or presentation problems |
| Manufacturing and interoperability | Export, reopen and compare files; prepare layouts, fit coupons and supported slicer checks |
| Reference and computation | Consult relevant primary references and use supported numerical/search tools; retain provenance and distinguish references from proof |

This table is a target coverage map. The implemented registry and its actual boundaries are in `crate_studio/design_tools.py`; reference browsing, force/fatigue and general sketch constraints remain unavailable. Existing geometry helpers do not become model-callable simply because they exist. Broad tool access must operate within the current project authorization, application budget and revision safeguards; no blanket authority for unrelated data or external actions is implied.

## Verification and speed

Run inexpensive requirement/schema/unit checks before native geometry, then relevant current-pose checks before expensive motion/export checks. Feed actionable failures to the planner, retaining the original proposal and every repair. Bound iterations and stop with an explicit unresolved result when a tool, budget or constraint blocks progress.

Cache exact reusable work using geometry/dependency, tool-version and relevant settings identities. Coalesce duplicate requests, invalidate changed dependencies and prevent stale jobs from replacing newer revisions. A cache hit is not a fresh model experiment. Measure cold/warm latency, model calls, estimated cost and success rate on the same tasks before claiming an improvement.

Verification must match the deliverable: finite thickness, usable dimensions, compatible joints and interfaces, appropriate clearance checks, functional requirements and export read-back. A zero-thickness surface is an exploratory tool, not a printable mechanism. Sampled collision checks are not continuous-motion proofs; native solids and successful slicing are not physical strength or fit tests.

## Visual judgment and practical taste

After functional checks, inspect silhouettes, proportions, consistency, unnecessary bulk, exposed hardware, finger access and readable drawings. Prefer a small number of useful, understandable alternatives with explicit trade-offs. Treat aesthetics as a review with evidence and user preferences; do not invent a certification score. Visual criticism may trigger another editable revision, which must rerun affected engineering checks.

## Adjustable-box acceptance target

One permanent open-top object must reach small, medium, large and rectangular useful states, retain a usable floor and hold each selected state without being held. Flattening/refolding is allowed. The adjustment mechanism is open for model proposals; the authored sheet baseline is optional. Nonzero thickness is mandatory. Thickness, hinge sections and clearances need declared manufacturing assumptions; a nominal 2 mm panel is only a provisional starting point. One print job is preferred where practical, and initial assembly is acceptable. Preserve a trace separating model-selected mechanisms, developer-built tools and deterministic sizing. Printer-specific physical testing remains a separate acceptance gate.
