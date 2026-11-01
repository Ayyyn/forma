# Evidence-gated material discovery experts: algorithm revision

October30,2026. The preceding representation pilot did not beat strong controls.
This new study tests one specific system-design response: retain strong numerical
experts and let Meta's proposal earn weight through prequential evidence. It also
compares Wonder versus Spark within the same portfolio. Do not overwrite the
earlier pilot or call this an untouched-data replication.

Same three experimental tables/definitions as FRONTIER_MATERIALS_PROTOCOL.md;
new initial seeds106,137,193,239, eight common initial groups plus24 sequential
reveals. All seven methods ×12 task/seeds=84 episodes must be reported, including
initially solved starts. Initial seeds differ from v2, so v2/v3 comparisons are
not a causal architecture ablation. Public/pretraining contamination remains
possible. This remains historical replay, not a new physical experiment.

Controls: random, raw GP/EI, RF/EI, domain GP/EI, and a numerical expert portfolio.
All three numerical experts remain in the portfolio. Their Gaussian EI values
are mixed by current weights. At each step, record all forecasts BEFORE reveal,
then update weights using Gaussian negative log scores: standardized sigma floor
.05, loss clipped[-5,20], learning rate.2 and active weight floor.02 followed by
renormalization. This is a transparent robust forecasting heuristic; RF spread
and GP variances are not promised calibrated. No missing outcome is used.

The numerical portfolio starts with equal base weights. At8,16,24 observations,
the Meta variant proposes <=6 features in the same validated DSL. A nonempty
valid proposal adds a fourth GP expert at weight.1 while preserving relative
base weights in the remaining.9. Empty/invalid proposals disable that expert.
New feature plans reset only the Meta weight. Earlier forecasts remain in the
evidence log. The next prompt gets all revealed groups, previous hypothesis,
validation feedback, and the last8 prequential expert forecasts/losses/weights.
No arbitrary code, altered objectives or secret table outcomes are available.

Two separate ablation conditions, not a communicating agent team:
Muse Wonder1.0 high reasoning, and Muse Spark1.3 standard API with its default
reasoning settings. Each gets8192 output tokens and temperature.2. Same
downstream engine. No images, generated visuals, RL or fine-tuning. At most72
requests total,36/model, and a shared locked estimated$15 phase cap. Prices from
official Meta pages: Wonder4/.2/20 and Spark1.25/.15/4.25 per million
input/cached/output tokens. Standard, not Contributor model IDs are used.
Compatibility probe(s) are unscored and separately reported. Stop new dispatch
after a transport failure; preserve already-in-flight requests and all fallbacks.

Primary score is mean normalized regret over queries9–32 as before. Gate for
each Meta condition: transport-valid36 HTTP200 responses/IDs/usage; at least8/12
paired wins AND >=15% lower pooled mean regret against EACH non-AI control.
Using pooled means avoids ill-conditioned per-case percentage ratios at zero
control regret. Report all comparisons and both models; no significance claim
or best-model post-selection claim. Passing is a directional research gate.

Label budgets are equal32 group revelations; numerical work is NOT equal:
single-model controls fit24 surrogates/episode, the three-expert portfolio72,
and a fully active Meta portfolio96. Report actual fits, source-row counts,
model calls/cost and failures. No CPU/time-efficiency or prototype-savings claim.
Freeze source, inputs, methods, seeds and this document before proper runs.
