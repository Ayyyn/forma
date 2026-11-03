# Forma project continuity

For work on Forma CAD (`crate_studio`, its evaluation/research helpers, examples or documentation):

- Read `docs/FORMA_ENGINEERING_LOG.md` before planning significant changes. It is the current internal record of problems, decisions, verified capabilities and priorities. Older dated reports are historical evidence.
- Maintain that log with each meaningful implementation/evaluation batch: exact problem, severity, current status, original intuition versus observed result, action, verification, remaining work, feature/architecture changes and evidence links. Preserve original failures and corrections; do not claim an experiment was promoted or a replay was a fresh model run.
- Before and after paid Forma batches, and after accounting corrections, run `python -m research.update_forma_engineering_budget`. It reads local receipts only. If ledgers are unavailable, retain the previous snapshot and state that it could not be refreshed; never replace missing history with a zero-spend claim.
- Keep `docs/FORMA_BUDGET_SNAPSHOT.json` and the log's budget section consistent through that helper. The application guard, recorded estimates and actual provider billing/credits are different quantities. Do not raise a cap without the user's authorization.
- Maintain the log locally alongside source changes. The engineering log and budget snapshot are private, ignored files: never stage them, embed their content in public documentation or add them to release archives without explicit user approval. Raw projects, receipts, evidence, credentials and vendor runtimes remain in their existing ignored locations; a source commit does not back them up.
- Documentation maintenance itself should not trigger paid calls, new evaluations, publication, deployment or product changes. Continue within the user's current requested scope.

These continuity rules apply to Forma work. Preserve the independent scope and evidence of earlier research modules.

## Muse design-agent standard

- Follow `docs/FORMA_AGENT_DESIGN.md` when evolving the design pipeline. Correctness, practical usefulness, visual judgment and measured latency are product requirements.
- Give Muse callable access to relevant available engineering tools; do not confuse a documented tool or a prompt instruction with an implemented integration. Report unsupported tools/operations explicitly.
- Preserve mechanism freedom: propose and compare mechanisms from the user's requirements rather than silently forcing a preselected template. Distinguish developer-authored baselines, model proposals and deterministic solver decisions.
- Real manufacturing deliverables require finite-thickness geometry and revision-bound verification. An attractive render, valid solid or sampled motion alone does not establish a working physical mechanism.
- Keep requirements and assumptions inspectable and human-editable. Do not relax requirements to pass a check. Visual taste is a review criterion, never a substitute for functional acceptance.
- Prefer exact reuse and staged checks for speed; measure improvements without reducing validation quality. Add model roles only when a controlled comparison supports their cost/quality trade-off.
