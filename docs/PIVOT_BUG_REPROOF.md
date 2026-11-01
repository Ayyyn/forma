# Pivot decision: execution-backed bug reproduction

October 28, 2026. Research and bounded capability pilot; no product UI or general coding agent has been built.

**Selected candidate:** a tool that turns a bug report into a small executable regression check, then shows actual before/after evidence and explicit unresolved outcomes. Meta interprets intended behavior and designs examples; an independent local runner executes the checks. It should help a developer establish the defect before trusting a proposed fix.

**Decision:** retain this as the strongest feasible candidate researched in this round, but **hold the main product build**. The test-design capability has useful execution-backed examples. The frozen overall pilot gate did **not** pass because one missing-information response was not machine-readable. A reviewed research demo is feasible; autonomous readiness, user time savings and competitive differentiation remain unproven. Do not rename a failed gate as a pass.

## Why this direction

The earlier Kresling experiment asked a model to compete with numerical inference on a fully specified finite problem. Here the essential input is informal human meaning: what behavior is wrong, what correct behavior would look like, and which examples distinguish them. Interpreting that meaning is the proposed Meta contribution. Running tests, recording versions and deciding whether the observed checks pass remain deterministic.

The supplied participant guide weights impact 30%, Meta tooling 25%, execution 20% and demo 25%; it excludes generic RAG and simple image analyzers. We prioritize an executable artifact and a visible failure/fix narrative. These are selection judgments, not predicted judging scores or proof of eligibility. The public-repository, three-minute video, attribution and November 4 submission requirements remain unfinished.

| Candidate researched | Meta contribution | Main obstacle this week | Decision |
|---|---|---|---|
| Extend Kresling selection/inverse design | Numerical planning | Our frozen evidence did not demonstrate sufficient incremental value | Stop expansion |
| CAD/material-change automation | Interpret requests and propagate edits | Integration/adoption gaps; substantial overlap with existing engineering agents | Do not return to the previous editor concept |
| Assembly-error detection from video | Perception and procedural reasoning | Suitable clips, observable ground truth and task-specific validation needed before a credible live claim | Defer |
| Reproduce scientific papers | Read methods and generate scientific code | Large scope and substantial existing benchmarks; the same model-validation bottleneck returns | Defer |
| Accessibility/web-test repair | Interpret UI meaning and repair code | Crowded tools/research; automatic check scores cannot establish complete accessibility | Not selected |
| Bug report → executed regression evidence | Infer intended behavior and create discriminating checks | Output reliability, incomplete reports and proving differentiation | **Selected for the capability test** |

Prior-art checks matter. [Siemens describes AI BOM change execution](https://blogs.sw.siemens.com/teamcenter/ai-bom-agent-plm-engineering-change/), and [Adam advertises CAD/PLM/simulation workflows](https://adam.new/). These are vendor claims, not hands-on comparisons. [Assembly101](https://assembly-101.github.io/) already provides procedural-action and mistake-detection resources. [CORE-Bench](https://crab.cs.princeton.edu/core-website/) covers computational reproduction. [Momentic](https://momentic.ai/) and [Applitools](https://cookbook.applitools.com/solutions/localization-testing/) cover related testing workflows.

## This is established research, not an invention claim

[SWT-Bench](https://swtbench.com/) already evaluates issue-derived tests that fail before a repair and pass afterward. [Salesforce TEX](https://www.salesforce.com/blog/tex-test-time-scaling/) explores test-generation agents and execution-based validation. [Jam](https://jam.dev/resolve) supplies rich bug-report evidence to engineers and agents. [Hypothesis Ghostwriter](https://hypothesis.readthedocs.io/en/latest/ghostwriter.html) provides automated property-based test scaffolds and explicitly distinguishes generated properties from knowing the intended oracle.

We did **not** invent regression reproduction, red/green validation, mutation testing, test generation or execution receipts. A defensible contribution is the new constrained Meta-to-test-contract implementation, its local execution boundary, explicit unresolved states and transparent evaluation. This is an engineering contribution; it does not establish a world-first combination or a competitive advantage over current coding agents.

## Test and result

Selected eight lightweight public historical issues from [SWE-bench Verified](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified): Flask #5014 and Requests #1142, #1766, #1921, #2317, #2931, #5414 and #6028. We downloaded their exact base commits, made separate fixed copies by applying only their published production patches, and verified adapted upstream regression expectations before calling Meta. The model saw the report, library name and bounded API SDK; fixes and gold tests stayed evaluator-only.

Each generation could propose up to four JSON test contracts or ask for missing information. Four allowlisted API operations were supported: request preparation, digest-header construction, URL-scheme normalization and Flask Blueprint creation. The runner executes actual upstream library code in a keyless child process. Request transport is replaced with a recorder: **no HTTP server, real proxy, network authentication or full repository suite was tested.** Shared collection-import compatibility aliases support old Python code, and test nonce/time sources are controlled for replay. These changes do not replace the upstream bug logic.

Two generation seeds were used for each real issue, plus two underspecified synthetic controls at both seeds: 20 calls per protocol. These are eight issue families and two control prompts, not 20 independent tasks. The baseline extracts literal examples and explicit expected outcomes using rules; it is a **limited baseline, not a strong modern coding agent**. This experiment establishes a bounded capability difference, not state-of-the-art superiority.

| Protocol/method | Verified real-issue suites | Distinct issues with a verified suite | Correct structured clarification controls |
|---|---:|---:|---:|
| v1 strict native-tool adapter / Meta | 2/16 | 2/8 | 0/4 |
| v2 repaired adapter / Meta | **13/16** | **7/8** | **3/4** |
| Literal report rules, either protocol | 6/16 | 3/8 | 4/4 |

v1 was preserved in full. A separate diagnostic found that the endpoint sometimes emitted `<atem:function_calls>` in ordinary content rather than a native tool-call field. v2 added strict data-only decoding of that observed format, native tools and plain JSON, retained public output, added a header-value assertion and clarified which fields exist. Its source/settings and unchanged success thresholds were frozen before the fresh v2 run. **v2 is a development retest on the same historical cases, not a new untouched holdout.** No successful v1/v2 cells were mixed into a best-of score.

The overall gate required at least 12/16 verified suites, at least six distinct reproduced issues, all four missing-information controls handled correctly, at least four more verified cells than literal extraction, and actual replayable evidence for every accepted claim. v2 passes every condition except the **4/4 clarification requirement**. One response said only that it needed more detail without a supported structured envelope. The saved gate remains **failed**.

The semantic failures are informative. One digest suite asserted support for `auth-int`, which the fixed implementation did not provide; the checker rejected the whole suite. Both proxy suites merely checked supplied headers and were green on both versions, so they were not accepted as reproductions. We did not discard bad tests from a suite to improve its score.

### Fresh project-code check

Historical issues can be in a model's training data. We therefore separately tested a newly reproduced defect in our own adapter: malformed XML containing an unescaped ampersand raises `ParseError`, which escapes the caller's intended `ValueError` boundary. This issue was identified and independently reproduced by us; **Meta did not discover it or write the correction**.

Given the original source and the expected boundary behavior, one actual Meta call generated two message/assertion inputs: an unescaped ampersand expected to raise `ValueError`, and an escaped `&amp;` control expected to decode successfully. Independent execution showed:

| Implementation | Malformed-input check | Valid-input control |
|---|---|---|
| Original | Fails: unexpected `ParseError` | Passes |
| Separately written correction | Passes | Passes |
| Overbroad mutant rejecting every message | Passes | **Fails** |

This demonstrates a useful local test-design contribution and a control that rejects one false correction. It is **one assisted example**, not a generalization rate, a discovery claim, or a certification of all fixes. The frozen historical score was not changed. Its protocol adapter remains untouched; the correction is a separate reviewed-example wrapper.

## Verification, costs and scope

- Both 40-cell protocol matrices are complete, including unusable responses and failed suites. Every execution-backed cell was rerun; saved results reproduce. Strict model-output validation rejects unknown actions, arbitrary code and excess tests. Green-on-both, red-on-both, missing imports and empty suites cannot count as verified.
- All eight upstream reference adaptations reproduce before calling either scored protocol. Source archives, production patches, selected files and the untouched archive contents are independently hash-checked. Third-party source/licenses remain distinct from new hackathon code.
- All **65 software/reference tests** pass. The fresh parser example additionally replays against original, corrected and overbroad-mutant behavior.
- This research round made **43 actual Meta requests**: 20 v1, 20 v2, two format diagnostics and one fresh-code probe. Estimated reported token cost is **$0.294** at [published generic Baseten rates](https://www.baseten.co/library/muse-spark-open/); actual credit deductions are unverified. The v2 median end-to-end generation/check time is about **6.72 seconds**, versus 0.73 seconds for the limited rules.
- Meta received no credentials or local files beyond the explicitly supplied public report/SDK and fresh parser source. Child workers receive an environment whitelist without API keys. No private reasoning text is saved. These constrained workers are not a general-purpose secure code sandbox.
- Docker CLI is present, but its engine was unavailable in a read-only check. Unrestricted repository execution/container support is **not validated**. The current runnable proof supports the stated API operations and one separate parser example; it cannot accept arbitrary repositories.

Before/after agreement establishes the test's observed behavior under the chosen fixtures. It does not prove complete fix correctness, absence of other regressions, production safety, broad coding-agent superiority or customer time savings. Several cases contain explicit reproduction hints. A developer may solve them quickly without our tool; no human-time comparison was measured.

## What to build, only after the remaining gates

The feasible demo scope is a **reviewed proof runner for small trusted Python/API changes**: report and supported code context → proposed checks → visible review → actual failing run → rerun on a candidate fix → downloadable checks and execution receipts, with unresolved outcomes shown explicitly. Its purpose is a reliable handoff for a coding workflow, not a general coding assistant or an autonomous fix approver.

The next gate is one fresh developer workflow and a comparison against an ordinary coding-agent prompt on the same task, measuring time to a valid reproducer and false-fix rejection. Also resolve structured clarification reliability without weakening the gate, and confirm the execution environment for the intended scope. **Until then, do not commit the remaining week to product UI or claim a winning idea.** We have evidence of useful Meta test design; differentiation and impact still need evidence.

## Run the evidence

```powershell
# Offline, no model calls:
python scripts/replay_bugproof_pilot.py --version 1
python scripts/replay_bugproof_pilot.py --version 2
python scripts/probe_fresh_parser_bug.py --replay

# Example: this should exit 1 on buggy code and 0 on fixed code:
python -m bugproof_pilot_v2 check --case psf__requests-2317 --variant buggy --suite examples/bugproof/bytes-method-suite.json
python -m bugproof_pilot_v2 check --case psf__requests-2317 --variant fixed --suite examples/bugproof/bytes-method-suite.json
```

Evidence: `benchmarks/bugproof-pilot-v1/`, `benchmarks/bugproof-pilot-v2/`, `research/bugproof/fresh-parser-probe.json`, and `research/bugproof/source-integrity-audit.json`. Baseline, failed protocol, diagnostics and current pilot remain separate. This work is dated October 28; upstream code/bugs/fixes and earlier origami/Kresling work are explicitly prior assets.
