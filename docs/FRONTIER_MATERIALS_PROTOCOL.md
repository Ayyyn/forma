# Frontier scout: measured-materials representation/experiment-selection pilot

October 30, 2026. Freeze this document, source, data checksums, seeds, baselines,
budgets and gate before numerical/Meta policy runs. This is exploratory problem
selection and system engineering, not an untouched scientific benchmark.

Use three experimental tables from PV-Lab/Benchmarking at the pinned commit in
the download receipt. Crossed barrels: 1,800 compression tests in 600 three-repeat
geometry groups; manufacturing calibration: 100 unique recipes; perovskite
stability: 139 rows in 94 composition groups. These counts are verified from the
downloaded files, not substituted from the older article's summary table.
Group identical input features before any splitting so replicates cannot leak
between train/unrevealed pools. Outcome is the mean of the recorded group; sample
variance/count are revealed only when the group is queried. This is not a fresh
measurement or a model validating an unmeasured structure. Original row order
is randomized; original experiment IDs are not features.

Each task has eight common seeded initial groups and 24 sequential choices,
32 group revelations total. Seeds: 31,47,71,97, all three cases. No exclusion of
easy starts or starts already containing a top-5% result. Primary score: average
range-normalized simple regret after initial observations, queries9–32; smaller
is better. Full-pool outcomes are used only by the offline evaluator, not the
policy. Report final result, top5% discovery count/first hit, initial state,
historical source-row count, surrogate fits, actual API requests and failures.
Equal group budgets are not always equal numbers of original measurements:
crossed-barrel groups all have three repeats, perovskite counts vary. No claim
about actual experiments/prototypes saved follows from this replay.

Controls: random; GP with Matern5/2, ARD, noise and EI; bootstrap RF128 with EI
from tree spread; and a domain-informed GP with the exact same numerical engine
as Meta. All raw features are retained. GP fits use one optimizer restart, fixed
random seed and identical bounds. Input normalization uses public unlabelled
pool coordinates. Observed group-mean variances enter GP alpha after target
standardization. Additional WhiteKernel noise is learned; predictive uncertainty
is not assumed calibrated. All learned fits use only revealed outcomes.

Domain features are fixed before runs: annular area/inertia, total area, wall
ratio and sine/cosine twist for barrels; offset magnitudes/squares and prime-speed
product for printing; pair interactions and squares for compositions. These
features are representations, not exact nonlinear toughness/stability laws.

Meta gets verified task semantics, column ranges, revealed raw group means,
variance/count, prior feature plan and recent prequential prediction errors.
At8,16,24 observations it proposes <=6 bounded feature operations. Original raw
features stay available. The shared GP/EI engine then selects the next eight
points. This tests a role beyond suggesting the next floating point parameters:
Meta supplies revisable statistical/physical representation hypotheses while
numerical inference/acquisition makes the selection. Every operation is validated
on the public pool; no arbitrary model-written Python, external browsing,
unrevealed outcomes or changed objective is allowed. Invalid commands use an
explicit raw-feature fallback, retained in the ledger, with no automatic retry.
The supplied annular operations are equally available to Meta and domain controls.

At most36 genuine Muse Wonder1.0 calls, reasoning high, max6144 output tokens,
temperature.2, at most three concurrent case workers, estimated phase cap$12.
Reserve worst-case input UTF8 bytes plus maximum output and an overhead allowance
under a locked budget before dispatch. Retain public request/response/tool data,
HTTP status, provider IDs, token usage and estimated cost; omit keys/private
reasoning. Missing usage conservatively consumes the reservation, not zero cost.
No API call is counted for local analysis. Real billing is unverified.

All60 episodes must finish: five policies × three tables × four seeds. Keep
failures and all negative results. Exploratory continuation gate: Meta must beat
each GP-raw/RF/domain control in at least8/12 paired episodes and achieve >=15%
median relative reduction in post-initial regret against each control. This is
a directional feasibility gate, not significance testing. No causal/general AI
effect from three public datasets/four seeds. Public/pretraining contamination
cannot be ruled out. No fresh materials, new-to-science structures, hardware,
drug efficacy or manufactured-part verification is claimed.

The broader25k-experiment BEAR shell archive is an interesting later application,
but its NC-SA license is a real public-reuse consideration; it is not downloaded
or bundled for this pilot. The selected repository's LICENSE says MIT while its
README says BSD-2-Clause; retain both and original study citations. Publication
and commercial-use assumptions require explicit attribution/source review before
submission; this pilot performs local research only.

## Transport correction, v2

The first frozen batch used an unsupported named-function `tool_choice` and
received36 HTTP400 errors. These were raw-feature fallbacks, not Meta inference;
retain v1 as integration-failure evidence and draw no model-performance conclusion.
v2 uses supported `tool_choice=auto` and halts new dispatches on a transport
failure (already-in-flight calls may still finish). An unscored compatibility
probe precedes the proper v2 inference batch. No hypothesis prompt, numerical
algorithm, task, seed, budget or score is tuned using v1 results.

v1 numerical controls may be copied to v2 only after exact input/source/runtime,
task and episode-function equality checks. Retain provenance and output hashes;
report this as reuse, not new computation. Require36 HTTP200 responses with
provider IDs and usage for an inference-valid comparison. Rejected feature
plans after valid inference remain end-to-end system failures with explicit
fallbacks. All v1 records remain immutable.
