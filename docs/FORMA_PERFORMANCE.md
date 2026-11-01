# Exact reuse and planner experiments — November 2, 2026

Open `http://127.0.0.1:8770/performance` for results and hashed evidence.
The original frozen report and its evidence remain unchanged.

## Production changes

- Studio and the AI validator share a bounded exact geometry cache. Imported
  assets are keyed by file bytes. Cached BREP objects follow the existing
  read-only contract.
- Successful proposal reuse keys bind the complete document, exact instruction,
  selection, model/settings, validator source hashes, CAD versions and asset
  hashes. No approximate prompt matching is used.
- Cached plans are revalidated and record zero new model calls/cost, retaining
  the original run/response IDs under `cache`. Changed intent or geometry
  invalidates reuse.
- Identical active/completed requests share a job. `New proposal` bypasses
  completed-job and proposal reuse. Active duplicates still coalesce. Job reuse
  is in memory; proposal reuse persists across server restarts.
- Stable system prefixes have a stable Meta cache-routing key. Provider cache
  hits are measured, not assumed. Estimates distinguish cached input pricing.
- Identical first/final evaluation outputs are scored once, copied into both
  artifact locations and explicitly marked as reused.

Full topology context and medium reasoning remain production defaults. The
experimental focused-context/low-reasoning policy was not promoted.

## Measurements

One synthetic box edit through the actual HTTP API took **3.164 s** cold and
**0.0949 s** on an identical second saved revision. Completed-job reuse returned
in **0.0334 s**. The cold response estimate was **$0.012148**; repeats added no
model calls or cost. CAD and project data were identical and revalidated.
These are exact-repeat timings, not fresh-generation promises.

All **31 retained plans** produced identical cached/uncached results, with native
STEP/STL readback for ready plans. This replay uses the separately retained r15
repair; it is not new generation. Local apply-plan medians were 0.1807 s uncached
and 0.000229 s warm, excluding inference, HTTP and rendering.

**88 offline checks passed:** 49 Studio, 35 enclosure and four evaluation controls.
Seven cache tests cover invalidation, concurrency, assets, provenance, cached
pricing, topology preservation and explicit regeneration. The live HTTP exercise
has ten additional checks.

## Experimental policy and quality gate

Fresh focused-context/low-reasoning generation scored **19/20 revisions and
11/11 public CAD-bench geometry tasks** on the unchanged suite. All six added
constructed cases passed: selected face, selected edge, selected mate, absent
selection, dense profile and dependent pattern.

The steel-material task r12 regressed. Medium reasoning with the same incomplete
stock context also failed; reasoning effort alone was therefore not isolated as
the cause. The planner had been given only the current polypropylene catalogue.
The context now supplies all four material catalogues and explains that stock
membership must be recomputed for the proposed material. The unchanged r12 task
then passed under full context/medium reasoning in one response.

The failures remain visible. No complete fresh suite followed that fix; the
targeted pass is not a 20/20 result. The planned paired six-case control was not
run after the overall candidate failed the per-task quality gate. The candidate
remains opt-in.

Historical/trial median latency: revisions **4.20/3.78 s**, public geometry
**9.42/7.34 s**. These historical comparisons combine context, reasoning and cache
differences and are not randomized concurrent controls. Consistently repriced
cached-token estimates are **$0.729720** for the historical initial suite and
**$0.4412408** for the trial. The original estimate ignored cache discounts;
original receipts and conservative guard charges remain untouched.

The trial, six added cases, two material follow-ups and live cache cold request
produced **40 responses**, estimated **$0.565112** combined. Billing is unverified.
The approved $10 conservative application guard and prior reservations remain.

## Reproduction and limits

`research/run_forma_eval.py` accepts explicit context/reasoning settings and
bypasses proposal reuse for fresh evaluation. `research/forma_performance.py`
freezes selection cases and runs explicit policies. Keep each output directory;
inspect interrupted requests rather than repeating paid calls.

`research/verify_forma_cache_replay.py` is offline. The HTTP verifier makes one
paid synthetic request and then exact repeats; saved results prevent automatic
reruns. `research/forma_performance_report.py` produces the separate report and
credential-scanned evidence ZIP. Every run has matching source snapshots.

Progressive tessellation, broader retrieval and cheaper-model routing remain
future work. Geometry and export checks do not validate physical fit, load
strength or aesthetic quality.
