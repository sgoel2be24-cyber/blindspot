# BlindSpot Engineering Spec v1

Status: frozen for P0/P1 implementation

Date: 2026-08-24

Track: Razorpay Buildathon — Track 02, AI Risk Manager

Primary user: a risk operations lead who must quantify how much legitimate business a fraud policy blocks

## 1. Product contract

BlindSpot is a false-positive verifier for fraud systems.

> How do you know your fraud model was right about the payments it never allowed to happen?

An incumbent fraud model creates a declined population whose outcomes would normally be missing. BlindSpot allocates a small randomized verification budget with known, non-zero inclusion probabilities and estimates block precision, false-decline volume, and false-decline cost with explicit uncertainty.

The product measures decisions; it does not make or reverse fraud decisions.

### Frozen scope

Included:

- IEEE-CIS local data path and a labeled, semi-synthetic censoring experiment
- chronological model development and evaluation
- one deterministic incumbent fraud baseline
- uniform and margin-weighted randomized verification policies
- Horvitz–Thompson estimation and design-based confidence intervals
- offline discovery precision/recall and economic sensitivity
- a sealed oracle boundary and anti-cheating tests
- three risk-operations screens

Excluded:

- RiskTwin, self-healing policies, policy generation, and rescue scoring
- transaction approval recommendations or autonomous fraud actions
- multi-agent, RAG, vector database, or LLM dependencies
- streaming infrastructure, a payments gateway, or a production fraud claim
- claims that IEEE-CIS represents Razorpay traffic or current merchant economics

## 2. Units, notation, and target estimands

The unit is one transaction in the sealed evaluation window.

- `Y_i = 1` means the benchmark labels transaction `i` as fraud; `Y_i = 0` means legitimate.
- `s_i` is the incumbent fraud probability.
- `tau` is the decline threshold frozen before the evaluation window is opened.
- `D_i = 1[s_i >= tau]` identifies the incumbent-declined population.
- `N_D = sum(D_i)` is known because decisions are observable.
- `A_i >= 0` is `TransactionAmt`, expressed as dataset currency units rather than INR.

### Primary estimand

The false-decline share among incumbent declines is

```text
theta_FD = (1 / N_D) * sum_i D_i * (1 - Y_i)
```

The corresponding block precision is

```text
theta_BP = 1 - theta_FD = P(Y = 1 | D = 1)
```

This is the number BlindSpot exists to estimate. It is conditional on the frozen incumbent and the frozen temporal evaluation population; it is not a universal fraud-system score.

### Secondary estimands

```text
T_FD = sum_i D_i * (1 - Y_i)                    # false-decline count
G_FD = sum_i D_i * (1 - Y_i) * A_i              # false-decline amount
M_FD = margin_rate * G_FD                        # merchant margin at risk
```

The experiment may also report the offline false-positive rate

```text
FPR = false declines / all legitimate evaluation transactions
```

only after the oracle is revealed. FPR is not presented as observable in the censored product flow.

### Naive comparator

The controlled demo includes a deliberately labeled comparator that assumes every decline is fraud, which implies `block precision = 100%`. It is called the **naive policy assumption**, not an industry-wide claim.

## 3. IEEE-CIS data contract and temporal split

Only the labeled Kaggle training files are used for model development and sealed evaluation:

- required: `data/raw/ieee-cis/train_transaction.csv`
- optional: `data/raw/ieee-cis/train_identity.csv`

The Kaggle test files are not useful for the sealed benchmark because they do not contain `isFraud`. Raw files are never committed.

Required transaction columns:

- `TransactionID`: unique join and tie-break key
- `TransactionDT`: relative time from an undisclosed reference, not a calendar timestamp
- `TransactionAmt`: amount in unspecified dataset currency units
- `isFraud`: binary oracle outcome

If identity data is enabled, it is left-joined on `TransactionID`; missing identity rows are valid.

### Stable three-way split

1. Sort ascending by `TransactionDT`, then `TransactionID`.
2. Split by complete `TransactionDT` groups so the same time value never crosses a boundary.
3. Target row proportions are 70% train, 15% calibration, and 15% sealed evaluation. Moving a boundary to the right edge of a tied time group is allowed.
4. Require strict temporal separation:

```text
max(train.TransactionDT) < min(calibration.TransactionDT)
max(calibration.TransactionDT) < min(evaluation.TransactionDT)
```

5. Fit feature selection, missing-value handling, and the model on train only.
6. Freeze `tau` on calibration as the score quantile for a configured 5% target decline rate. Calibration outcomes may be used for baseline metrics but not to tune against the evaluation window.
7. Evaluation outcomes enter only the sealed artifact and evaluator.

The split manifest records row counts, time bounds, source file hashes, selected features, configuration, seed, and package versions.

## 4. Incumbent baseline

The P1 incumbent is `sklearn.ensemble.HistGradientBoostingClassifier` because it is deterministic with a fixed seed, accepts missing numeric values, exposes probabilities, and does not require a native third-party boosting runtime.

Baseline rules:

- Exclude `isFraud`, `TransactionID`, and `TransactionDT` from model features.
- Consider numeric columns only in P1.
- Rank candidate columns on train by non-missing rate, then column name; keep at most 64.
- Cast the model matrix to `float32`.
- Use balanced sample weights derived from train outcomes.
- Freeze all hyperparameters and `random_state = 1729` in the run manifest.
- Report calibration-window PR-AUC, ROC-AUC, precision, recall, decline rate, and threshold. Accuracy is not a headline metric.

This is an incumbent baseline, not a leaderboard model. Categorical modeling and stronger optional boosters are post-P1 only.

### Adversarial private-signal mode

P1 fixtures include an optional `incumbent_private_signal` available to the incumbent but prohibited from the BlindSpot product view. This demonstrates that model-based label imputation can fail when the decision process uses unavailable signals. It is a red-team scenario, not a requirement for design-based estimation inside the already-declined population.

## 5. Censoring experiment and sealed boundary

The trusted experiment harness performs these steps once:

1. Score the sealed evaluation rows with the frozen incumbent.
2. Apply `D_i = 1[s_i >= tau]`.
3. Derive a deterministic `row_id` from a fixed run namespace and `TransactionID`.
4. Write a product decline pool with no outcome or private-signal columns.
5. Write a separate sealed oracle table keyed by `row_id`.

### Product decline-pool schema

| Column | Meaning |
|---|---|
| `row_id` | deterministic opaque experiment key |
| `transaction_id` | original `TransactionID` for traceability |
| `transaction_dt` | relative transaction time |
| `transaction_amount` | dataset currency units |
| `risk_score` | frozen incumbent score |
| `decline_threshold` | frozen `tau` |

No target, outcome alias, oracle statistic, evaluator object, or incumbent-private feature may appear.

### Sealed oracle schema

| Column | Meaning |
|---|---|
| `row_id` | experiment key |
| `is_fraud` | benchmark oracle outcome |
| `transaction_amount` | copied for sealed amount estimands |

The trusted harness may create both artifacts. Modules under `blindspot.product` may consume only the product artifact and must not import `blindspot.evaluation` or `blindspot.experiment`.

Offline IEEE-CIS labels are called **oracle truth**. Production sources such as eventual disputes, analyst disposition, step-up results, or approval holdouts are called **verification evidence** because they differ in latency, missingness, and reliability. P1 estimates with a perfect offline oracle; evidence-noise sensitivity is a later extension.

### Dataset limitation

IEEE-CIS contains transactions already observed by the dataset provider. Any transactions excluded by an earlier real decision system are absent. BlindSpot therefore validates the estimation method on a second, controlled censoring gate; it does not estimate an absolute real merchant false-decline rate.

## 6. Randomized verification policy

Let `pi_i = P(S_i = 1)` be the first-order inclusion probability for declined transaction `i`. P1 uses independent Bernoulli (Poisson) sampling, so the realized sample count varies around the configured expected budget.

Every policy must satisfy

```text
0 < pi_i <= 1 for every declined transaction
sum_i pi_i = B
```

where `B` is the expected number of verifications and `0 < B <= N_D`.

### Uniform policy

```text
w_i = 1
pi_i = B / N_D
```

### BlindSpot margin-weighted policy

The policy uses no second classifier. It uses only distance from the incumbent boundary:

```text
margin_i = max(risk_score_i - tau, 0)
scale = max(median(margin_i where margin_i > 0), 1e-6)
priority_i = exp(-margin_i / scale)
w_i = exploration_floor + (1 - exploration_floor) * priority_i
```

The default `exploration_floor` is `0.10`. Positive weights are converted to propensities by deterministic water-filling:

```text
pi_i = min(1, lambda * w_i)
```

with `lambda` chosen so `sum(pi_i) = B`. The floor gives every decline support; capping handles large budgets.

Sampling uses NumPy `Generator(PCG64(seed))` and selects independently when `u_i < pi_i`. The complete plan—every `row_id`, propensity, priority, selection bit, policy name, expected budget, and seed—is canonicalized and SHA-256 committed before any oracle join.

Default budget sweep: `0.25%, 0.5%, 1%, 2%, 5%` of `N_D`, evaluated over at least 200 seeds for final coverage claims. P1 smoke tests use fewer seeds.

## 7. Estimator and confidence intervals

For a sampled decline, define `Z_i = 1 - Y_i`.

### Horvitz–Thompson primary estimate

```text
T_hat_FD = sum_i S_i * Z_i / pi_i
theta_hat_FD = T_hat_FD / N_D
theta_hat_BP = 1 - theta_hat_FD
```

Under independent Bernoulli sampling, the design-based variance estimator is

```text
V_hat(T_hat_FD) = sum_i S_i * (1 - pi_i) * Z_i^2 / pi_i^2
SE(theta_hat_FD) = sqrt(V_hat(T_hat_FD)) / N_D
```

The P1 95% interval is the normal design interval, clipped to `[0, 1]`:

```text
CI_FD = clip(theta_hat_FD ± 1.959964 * SE, 0, 1)
CI_BP = [1 - CI_FD.upper, 1 - CI_FD.lower]
```

For totals, clip the interval to `[0, N_D]`. Amount estimates replace `Z_i` with `Z_i * A_i` and are lower-bounded at zero.

The report marks an interval **unstable** when any of these hold:

- fewer than 30 realized verifications
- inverse-probability effective sample size below 30
- the verified sample contains no legitimate or no fraudulent decline
- a non-finite estimate or variance occurs

Final claims require Monte Carlo coverage on the sealed simulation; the approximate normal interval is not described as exact at tiny budgets.

### Sensitivity estimate

Report the Hájek ratio only as a labeled sensitivity estimate:

```text
theta_hat_Hajek = sum(S_i * Z_i / pi_i) / sum(S_i / pi_i)
```

The Horvitz–Thompson estimate remains primary because its design unbiasedness follows from the known inclusion probabilities.

## 8. False-decline discovery metrics

These metrics describe the sampled review queue, not the population estimator.

```text
discovery_precision = verified legitimate declines / all verified declines
discovery_recall = verified legitimate declines / all legitimate declines in the sealed decline pool
```

- Discovery precision is visible after sampled verification evidence arrives, but it is selection-policy dependent and must not be substituted for block precision.
- Discovery recall requires the full sealed oracle denominator and is **offline-only**.
- If a denominator is zero, return `null` with an explicit reason rather than `0`.

At each budget and policy, also report:

- absolute block-precision estimation error in percentage points
- 95% CI width and oracle coverage
- realized and expected verification count
- effective sample size
- estimated and oracle false-decline count/amount

Policy comparisons use repeated seeds and distributions, not a single favorable draw.

## 9. Economic assumptions

All defaults are transparent demo parameters in dataset currency units; none are claimed Razorpay or merchant facts.

| Parameter | P1 default | Interpretation |
|---|---:|---|
| `merchant_margin_rate` | 0.10 | contribution margin lost on a legitimate declined amount |
| `verification_cost_per_case` | 1.00 CU | operational cost per verification |
| `fraud_loss_given_approval` | 1.00 | share of a fraudulent approved amount lost |
| `approval_exposure_share` | 1.00 | share of sampled cases experimentally approved in an approval-holdout scenario |

Required sensitivity ranges:

- margin rate: 5%, 10%, 20%
- verification cost: 0.25, 1, 5 CU
- fraud loss given approval: 50%, 100%

The core report shows separate quantities:

```text
estimated_false_decline_amount
estimated_margin_at_risk = margin_rate * estimated_false_decline_amount
verification_program_cost = realized_verifications * verification_cost_per_case
realized_fraud_exposure = selected_fraud_amount * fraud_loss_given_approval * approval_exposure_share
```

It does not claim net savings because BlindSpot does not decide which transactions to rescue. The Budget Lab visualizes the trade between verification cost, fraud exposure for a chosen evidence mechanism, and statistical precision.

## 10. Six anti-cheating controls

These are named acceptance tests, not documentation-only promises.

1. **AC-01 Temporal isolation** — split IDs are disjoint, input order does not change membership, and strict time inequalities hold across train/calibration/evaluation.
2. **AC-02 Target and private-feature firewall** — model features exclude ID/time/target; product artifacts exclude oracle aliases and declared incumbent-private features.
3. **AC-03 Import seal** — an AST scan fails if any module under `blindspot.product` imports `blindspot.evaluation` or `blindspot.experiment`.
4. **AC-04 Label-blind selection** — permuting sealed outcomes while keeping the product pool fixed cannot change propensities, selected IDs, or the plan commitment.
5. **AC-05 Propensity and ledger integrity** — every decline appears once, every propensity is finite and in `(0, 1]`, propensities sum to the expected budget, and the evaluator rejects duplicate/unknown IDs, changed propensities, or an invalid commitment.
6. **AC-06 Deterministic replay** — the same data, configuration, and seed reproduce split membership, selected feature order, model scores within tolerance, propensities, selected IDs, and aggregate report; a changed sampling seed changes only the Bernoulli draw.

## 11. Three UI screens

### Screen 1 — Blind Region Overview

Answers: *How much of our decision quality is currently unmeasured?*

- total evaluated payments, decline count/rate, and unverified decline count
- naive policy assumption versus BlindSpot block-precision estimate and CI
- estimated false-decline count, amount, and margin at risk
- clear `Oracle hidden` / `Oracle revealed for benchmark` state
- incumbent calibration metrics and data-window provenance

### Screen 2 — Verification Queue

Answers: *Which declines are in this randomized verification run, and why?*

- sampled cases only, with propensity, priority, selection reason (`exploration` or `near boundary`), amount, and evidence status
- expected versus realized verification count
- before/after estimate width as evidence arrives
- no approve/rescue recommendation and no fraud label before the sealed reveal

### Screen 3 — Budget Lab

Answers: *How much verification is enough?*

- uniform versus margin-weighted policy across the frozen budget sweep
- CI width, empirical coverage, estimation error, effective sample size
- discovery precision/recall clearly separated from block precision
- verification cost and optional approval-exposure sensitivity
- repeated-seed distributions with the chosen demo run highlighted, never substituted for them

P0/P1 scaffolds these screens but does not prioritize visual polish over statistical tests.

## 12. Repository architecture

```text
blindspot/
├── AGENTS.md                         # frozen scope and contributor guardrails
├── BUILD_STATE.md                    # current gate, evidence, and next action
├── DATA_PROVENANCE.md                # source, placement, hashes, limitations
├── FAILURE_LOG.md                    # factual failures and recoveries only
├── README.md                         # setup and no-key demo path
├── pyproject.toml                    # package, runtime, and quality tooling
├── docs/
│   └── ENGINEERING_SPEC_V1.md        # this frozen contract
├── data/
│   ├── README.md                     # local raw-data instructions
│   └── raw/                          # gitignored IEEE-CIS files
├── artifacts/                        # gitignored run outputs
├── apps/
│   └── dashboard.py                  # later three-screen Streamlit shell
├── src/blindspot/
│   ├── contracts.py                  # shared constants and validation errors
│   ├── economics.py                  # transparent cost calculations
│   ├── data/
│   │   ├── ieee_cis.py               # local loader and schema validation
│   │   └── split.py                  # stable chronological three-way split
│   ├── model/
│   │   └── incumbent.py              # feature firewall, baseline, threshold
│   ├── experiment/
│   │   └── censoring.py              # trusted product/oracle artifact creation
│   ├── product/
│   │   ├── contracts.py              # label-free decline and plan schemas
│   │   └── verification.py           # weights, propensities, Bernoulli draw
│   └── evaluation/
│       ├── estimators.py              # HT/Hájek estimates and intervals
│       └── sealed.py                  # oracle join, integrity, offline metrics
└── tests/
    ├── conftest.py                    # deterministic synthetic transaction data
    ├── unit/                          # loader, split, model, estimator tests
    ├── integration/                   # end-to-end synthetic experiment
    └── anti_cheating/                 # AC-01 through AC-06
```

Dependency direction:

```text
data -> model -> trusted experiment harness
                         |
                         +-> label-free product -> committed verification plan
                         +-> sealed oracle ------> evaluator -> aggregate report
```

`blindspot.product` never depends on the trusted harness or evaluator.

## 13. Core API contracts

```python
load_ieee_cis(raw_dir, include_identity=True, nrows=None) -> DataFrame
temporal_split(frame, config) -> TemporalSplit
fit_incumbent(train, config) -> IncumbentModel
choose_decline_threshold(calibration_scores, target_decline_rate) -> float
create_censored_artifacts(evaluation, scores, threshold, config) -> CensoredArtifacts
create_verification_plan(decline_pool, policy, expected_budget, seed) -> VerificationPlan
evaluate_plan(plan, sealed_truth, confidence_level=0.95) -> EvaluationReport
```

All public functions validate schemas and fail closed on missing, duplicate, non-finite, or forbidden fields.

## 14. Reproducibility contract

- Global default seed: `1729`.
- Split membership is a function of values, not current row order.
- Feature ordering is deterministic.
- Model and sampling seeds are recorded separately.
- Each run writes configuration, source hashes, package versions, plan commitment, and output hashes.
- Synthetic fixtures are the CI path; IEEE-CIS is an opt-in local integration path.
- No API key, network call, hosted database, or external model is required after dependencies and data are present.

## 15. Twelve-day build gates

| Day | Date | Gate | Exit evidence |
|---:|---|---|---|
| 1 | Aug 24 | Freeze v1 and scaffold | spec, repo docs, package imports, initial state |
| 2 | Aug 25 | Data path | IEEE loader/schema tests; raw data remains ignored; provenance recorded |
| 3 | Aug 26 | Temporal isolation | stable 70/15/15 split and AC-01 green on shuffled fixtures |
| 4 | Aug 27 | Incumbent baseline | deterministic fit/score/threshold; leakage and metric tests green |
| 5 | Aug 28 | Censoring boundary | product/oracle artifacts, private-signal scenario, AC-02/03/04 green |
| 6 | Aug 29 | Verification policies | uniform and weighted propensities, water-filling, commitment, AC-05/06 green |
| 7 | Aug 30 | Sealed evaluator | HT/Hájek, 95% CIs, discovery metrics, integrity rejection tests |
| 8 | Aug 31 | Experiment proof | repeated-seed budget sweep, coverage/error/economic outputs, random comparison |
| 9 | Sep 1 | Overview UI | Screen 1 driven only by aggregate artifacts; smoke test and screenshot |
| 10 | Sep 2 | Queue and Budget Lab | Screens 2–3, no-label queue states, policy comparison interaction |
| 11 | Sep 3 | Adversarial QA | full tests/lint, full-data runtime profile, limitations, real failure entry |
| 12 | Sep 4 | Feature freeze | reproducible demo command, README, architecture image, metrics export, rehearsal |

September 5 is reserved for submission packaging and contingency, not feature work.

## 16. P0/P1 acceptance criteria

P0 is complete when this spec, repository guardrails, data provenance, failure log, build state, packaging, and synthetic fixture contract exist.

P1 is complete when a clean environment can run a synthetic

```text
load -> temporal split -> train -> threshold -> censor -> verify -> sealed evaluate
```

flow; all six anti-cheating control groups pass; no raw data or API key is required; and the build state names concrete remaining work without claiming IEEE-CIS metrics that have not been run.

## 17. Change control

This spec is frozen for P0/P1. A change requires one of:

- a failing test demonstrates the statistical contract is wrong
- IEEE-CIS runtime evidence makes the baseline infeasible
- the official challenge requirement contradicts the contract
- Shikhar explicitly changes scope

Any change is recorded in `BUILD_STATE.md`; genuine failures and recovery evidence go in `FAILURE_LOG.md`.

## 18. Implemented clarifications and regression amendment · 2026-09-02

The frozen thesis, estimand and randomized policies are unchanged.

1. **Empty/single-class uncertainty fix (failing-test evidence).** An empty verification sample previously produced a zero-width interval at 100% block precision. The regression test in `tests/unit/test_estimators.py` failed before the fix. Empty or single-class non-census samples now return the full parameter interval [0, 1], count interval [0, N_D], and amount interval [0, total declined amount]. The last bound uses observable transaction amounts, not oracle outcomes. These intervals are labeled `uninformative_fallback`, not successful 95% precision. HT point estimates remain unclipped for design-unbiasedness; the UI suppresses the empty-sample point. A true full census remains exact and stable even with one class.
2. **Exact expected budgets.** The core defaults now match the frozen 5% calibration decline rate and 0.5% expected verification rate. Do not round an expected budget up to one: 0.5 expected checks legitimately permits an empty sample. The standalone 1,200-row demo retains visibly labeled larger smoke-test settings.
3. **Registered comparison.** Use the five original budget rates and at least 200 consecutive seeds for the full comparison. Additional 10%, 25%, 50% rates diagnose small synthetic populations; they are not substitutes for the primary rates and are hidden from default Budget Lab curves. Preserve all draws and report empty, fallback and stability fractions alongside coverage. Report Wilson Monte Carlo coverage bounds, paired squared-error differences and exact offline design variance. No empirical winner is promoted from one favorable seed.
4. **UI evidence boundary.** After commitment, the trusted evaluator exports only selected row-level observations into a separate evidence artifact. The dashboard may render those after explicit sample reveal; full-population oracle rows are never loaded. Offline truth-dependent aggregates require a separate benchmark reveal. These UI gates are presentation controls, not authenticated security boundaries. Selection code never receives labels.
5. **Selection explanation.** The specified additive weight floor does not assign a latent `exploration`/`near boundary` reason to each selected case. Show its actual sampling weight and probability; do not invent per-case mechanism labels. Evidence arrives as one committed batch, not a simulated live stream.
6. **Architecture additions.** `evaluation/sweep.py` runs the offline paired comparison; `benchmark.py` registers and exports a non-overwriting bundle; `dashboard_data.py` verifies four allowlisted dashboard JSON files; `apps/dashboard.py` renders them. Core selection, oracle evaluation and UI remain separate. No service, database or API key is added.

The measured limitations are in `docs/SYNTHETIC_BENCHMARK_2026-09-02.md`. This amendment does not establish IEEE-CIS or production performance. Build-gate dates above remain the original internal plan; they are not current verification of an official submission deadline.

## 19. Evidence reliability extension · 2026-09-03

Shikhar requested a materially stronger submission. The bounded extension adds an auditable local evidence-import workflow and a secondary robustness demonstration, without changing the frozen primary model, threshold, selection policies, estimand or HT/normal-interval results.

- `evaluation/evidence.py` validates complete committed review batches and computes conservative partial-identification bounds under explicit population-level label-error assumptions. Pending cases cannot be dropped.
- `audit.py` prepares a label-free committed plan and ingests review CSVs without an oracle; receipts are non-overwriting. This is not an authenticated production connector.
- `reliability.py` pre-registers eight simulated evidence mechanisms, all five primary budgets, both policies and 200 consecutive draw seeds. It is post-benchmark sensitivity analysis, not fresh held-out validation.
- `apps/reliability_view.py` renders aggregate stress cases within Budget Lab. Sample and offline-oracle reveal gates remain separate; the original three screens are retained. This explicitly simulated snapshot sequence does not change the original core's single-batch evidence contract.
- UI allowlisting now includes the two additional reliability exports, bound to the exact parent run. No sealed CSV is loaded by the UI.

The mathematical assumptions, Bernstein bound derivation, registered scenarios and acceptance tests are in [EVIDENCE_RELIABILITY_CONTRACT.md](EVIDENCE_RELIABILITY_CONTRACT.md). Results and replay evidence are in [RELIABILITY_RESULTS_2026-09-03.md](RELIABILITY_RESULTS_2026-09-03.md). Wide intervals and abstention are limitations to disclose, not reasons to tune against the answer key.
