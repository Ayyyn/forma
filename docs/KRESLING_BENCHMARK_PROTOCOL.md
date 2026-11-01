# Kresling experiment-selection protocol — October 28, 2026

Purpose: decide whether actual Meta model decisions improve a bounded scientific task enough to justify continuing an AI-centered Kresling hackathon demo. This is a newly implemented benchmark of established mechanics and established Bayesian experimental design, not an invention of either field.

## Task choice

Choose four virtual measurements to identify one unknown mechanical hypothesis, while accounting for a fixed unknown instrument offset. This is more substantive sequential reasoning than asking a language model to tune two numerical design parameters that an ordinary optimizer can search directly. A successful selection policy could reduce the number of later real calibration tests. This experiment does not yet establish that real-world benefit.

The mechanical responses come from our independently checked implementation of the published two-coordinate bar-and-hinge Kresling model. See `KRESLING_PROOF.md` for equations, source attribution, reproduced published results and excluded physics. Each experiment constrains compression **and** twist, then observes their two generalized reactions together. It is a virtual controlled-pose reaction test, not a torque-free deployment trajectory, equilibrium test or proof of mechanical stability. No contact, material failure, sensor hardware or physical measurements are simulated as validated physics.

The catalogue has 16 mechanical hypotheses: four effective hinge coefficients crossed with no axial spring, weak unprestressed spring, weak prestressed spring and stronger prestressed spring. The bilateral spring is an ideal energy term, not a claim about a fabricated tension-only component. Twelve candidate poses span compression 3/12/21/30 mm and additional twist 8/28/48 degrees. Eight different poses are reserved for prediction scoring.

Observation assumptions are explicitly synthetic: independent Gaussian standard deviations 0.015 N and 0.20 N mm, plus one fixed unknown additive calibration profile with force offset {-0.1,0,+0.1} N and torque offset {-1,0,+1} N mm. The independent uniform priors over 16 mechanical models and nine calibration profiles form 144 joint latent hypotheses. The objective is the marginal mechanical identity; instrument calibration is nuisance uncertainty. These noise levels and calibration profiles are not measured properties of a sensor.

Before freezing, an unscored design diagnostic with *known* calibration showed that a first measurement could resolve most uncertainty. We therefore added unknown calibration to test consequential sequential measurement choices. Only numerical catalogue/quadrature diagnostics and synthetic unit tests were run before this freeze: no scored policy comparison or model API request. This design decision must not be described as prospective physical validation.

## Policies and fairness

1. **Bayesian EIG:** enumerate all 12 candidate tests, integrate each Gaussian-mixture predicted readout using deterministic 25-by-25 Gauss-Hermite quadrature, and maximize expected reduction in *mechanical* posterior entropy. Marginalize calibration. Repeats are allowed; listed order breaks ties. Check quadrature against order 35 on uniform, seeded-random and concentrated priors before accepting the freeze. This is a strong greedy policy, not a claim of global four-step optimality.
2. **Meta:** actual Baseten `meta-models/muse-spark-open-1026`, medium reasoning requested, automatic tool choice, temperature 0.2, output ceiling 8192 tokens per decision, 180-second timeout, one request per decision, no retries or fallback. At each turn it receives the full public response catalogue, calibration/noise assumptions, remaining allowance, history and joint/marginal Bayesian posterior. It chooses one experiment ID. Baseline information scores, hidden truth, noise realizations, held-out responses and earlier cases are excluded. Public tool arguments, provider identity, request hashes and usage are retained; private reasoning text and keys are excluded.
3. **Four-corner space filling:** a fixed outcome-independent secondary control; this is not the main comparator.

All methods use the same numerical catalogue, observation likelihood and Bayesian estimator. Each has **at most four paired measurements**; invalid actions and repeats consume slots. They share identical potential observations for the same hidden case, experiment ID and replicate number. Different experiments receive separately keyed noise. No truth-aware success stopping, seed injection, silent retries, best-of selection or replacement of failed outcomes is allowed. A failed API transport ends that case; remaining scoring rounds retain its last belief without manufacturing observations. Such failures are separately labeled.

Measurement allowances are equal. Compute, API calls, latency and money are measured separately; they are not claimed to be equal. Cached prior EIG setup is reported separately from per-case timing. Two concurrent workers limit run duration; they do not share case observations. Every saved public request hash, observation, action, posterior and score is replay-checked.

## Matrix, metrics and decision rule

There are 48 matched cases: every mechanical truth, each with noise seeds 101, 202 and 303. True calibration index is `(mechanical_index*3 + seed_index*4) mod 9`; this is evaluator-only. Mechanical identities form **16 clusters**, not 48 independent physical systems. The same noise seeds do not imply that model generation is perfectly deterministic on a remote provider.

The primary loss is true-mechanical-model negative log posterior probability, averaged over measurement steps 1 through 4. This rewards early accurate identification. Also report final correctness, confidently wrong cases at 90%, correct 90% attainment, held-out unbiased mechanical-response RMSE normalized by the stated noise, invalid actions, transport completion, usage and latency.

Pair differences within cases, then average within each mechanical cluster. Bootstrap the 16 clusters with replacement 10,000 times, seed 28102026, and report the percentile 95% interval of baseline loss minus Meta loss. This interval is conditional on the fixed synthetic catalogue; it is not a universal capability bound.

**Continue an AI selection demo only if all predeclared conditions hold:** Meta reduces primary loss by at least 10% relative to EIG; the paired cluster interval lower bound exceeds zero; final correctness is no lower; invalid decisions are at most 5%; and at least 95% of Meta cases complete transport. Otherwise no Meta selection advantage is demonstrated. If transport completion is below 95%, distinguish infrastructure-inconclusive evidence from a model-capability conclusion. Equal final accuracy alone does not establish value if selection is slower or costs more.

## Reproduction and provenance

`python -m kresling_bench freeze` verifies the independent 320-pose prediction oracle and quadrature precision, then saves a source-hashed manifest and catalogue **before scored execution**. `python -m kresling_bench run --methods bayes_eig space_filling` runs controls; `python -m kresling_bench run --methods meta --workers 2` makes paid API calls using the existing ignored `.env`. `python -m kresling_bench summarize` requires the entire matrix, rejects source/catalogue drift, replays cells and generates tables/plots. Existing run files are never overwritten. To change a protocol, create another version and retain previous outcomes separately.

Source implementation and benchmark are dated October 28. Earlier studio/proof work remains attributed and separately documented. No pre-existing simulator source was copied, no physical data were fabricated, and no model calls are claimed without provider records. No public release, submission or eligibility certification is implied by this local experiment.

General Bayesian experimental design and information-gain methods predate this benchmark: [Foster et al., Deep Adaptive Design, 2021](https://proceedings.mlr.press/v139/foster21a.html) and [Huan and Marzouk, Simulation-based optimal Bayesian experimental design, 2013](https://doi.org/10.1016/j.jcp.2012.08.013). We implement a small finite-hypothesis greedy method, not their trained policies. Mechanics references are in the scientific proof report.

Cost estimates use [Baseten's published generic Muse Spark Open rates](https://www.baseten.co/library/muse-spark-open/), checked October 28: $1.25/M input, $0.15/M cached input, $4.25/M output tokens. Actual promotional credit deductions and charges for responses without usage remain unverified.
