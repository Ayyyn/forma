# Muse design tools

In Studio, choose **Design with tools** beside the prompt composer. **Quick edit** retains the shorter feature-planner path for ordinary edits. Both create reviewable proposals; neither automatically changes the saved project. The API equivalent is `POST /api/studio/agent` with `agent_mode: "tools"` and the existing document ID/prompt fields.

Design mode uses one Muse conversation with bounded tool calls. It first records alternatives, assumptions and an implementation strategy, then inspects/builds trial candidates, obtains actual tool feedback and can revise them. It has access to native feature references, project/topology inspection, body measurements, targeted construction, solid interference, prescribed general mechanism paths, supported folding studies, four CAD review views and checked exports. Tool errors and trial sources are retained locally, including unsuccessful runs.

## Scope of verification

A selected design is a **geometry proposal for review**, not certification that the mechanism works physically. Selection requires valid native geometry, a passing independent-body interference check, STEP/STL read-back checks and image delivery followed by a written visual review. A motion check that was run must also pass. Assumptions, alternatives and unresolved work appear in the proposal review. Geometric qualification is tied to the source and tool versions; later changes mark it stale.

General motion accepts model-declared root-first fixed/revolute/prismatic trees on actual native solids, named configurations and optional point/axis loop constraints. It checks all body pairs at sampled poses. The declared joints are virtual: manufactured guides, engagement, locks, floor usability, strength, friction, fatigue and continuous swept volumes require additional evidence. A valid path does not satisfy those requirements automatically. General mechanism source is retained in portable JSON and can be rerun in Motion; playback reports path progress rather than a fictitious common hinge angle.

No general force solver, arbitrary sketch constraint solver, autonomous novelty assessment, unrestricted code execution or reference-browser tool is implemented in this mode. Unsupported work remains explicit rather than being silently replaced by a folding template.

## Editable rigid components

Primitive additions/cuts and holes accept an optional `target_part_id` to modify one existing body. Without it, legacy global behavior is preserved. Union accepts optional `part_ids` to join selected bodies while preserving others. Body ordinals can change after these operations; inspect the returned geometry before choosing subsequent targets. A disconnected union can still produce multiple solids and does not establish a physical joint. Target bodies and union selections are editable in Properties.

## Runtime and cost

The loop limits model turns, tools per turn, candidates and motion samples. Exact tool results and native builds are reused within their actual source/asset identities. A failed HTTP 429/502/503/504 can receive one retry; ambiguous timeouts are not retried automatically. Empty actionable output is never forwarded as an invalid assistant message; one bounded larger-output retry is permitted before an explicit incomplete result. The existing shared application budget guard and receipts apply to every request and retry. Estimates, reservations and actual provider billing remain different quantities.

An incomplete run with retained tool actions offers **Continue design**. It requires the same original project, instruction and selection. The checkpoint replays prior native tool actions locally under current code/assets, supplies a current render, and resumes the model conversation. Replayed actions carry zero new provider charge and retain their source run/response provenance; new responses are counted separately. Changed sources require a new proposal. This is checkpoint continuation, not a fresh design or automatic physical approval; completed projects and budgets are never reset.

Portable source retains the design review and model-response provenance. The export workflow report explicitly marks a review current or stale, and includes a declared general mechanism study when configured. Review identity accounts for source, imported bytes, tool/package versions and font; numeric browser serialization and expanded folding defaults alone do not invalidate it.

This mode adds more inspections than Quick edit and has not established a general speed or quality advantage on a held-out benchmark. Experimental reasoning policies are explicit and do not change production defaults automatically.

Offline regression: `research/vendor/cad-runtime/Scripts/python.exe -m research.run_forma_checks`. The manifest covers Forma and excludes the separately scoped earlier research apps. Paid development checks use `research.verify_design_agent` only with an explicit `--run-paid` flag; original failures, source snapshots and continuation provenance remain local.
