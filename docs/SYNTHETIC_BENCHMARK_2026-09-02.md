# Synthetic benchmark · 2026-09-02

## Scope and evidence

This is a controlled synthetic experiment, not IEEE-CIS, Razorpay traffic or merchant performance. The population, threshold and weights are frozen; repeated trials redraw verification, not training data.

- Run: `11a911eb5d6b31ad`
- Bundle: `artifacts/synthetic-2026-09-02/` (local, gitignored)
- Generator: 50,000 rows, seed 1729, incumbent-private signal enabled
- Chronological train / calibration / evaluation: 35,000 / 7,500 / 7,500
- Calibration target decline rate: 5%; frozen threshold: 0.8410365074671364
- Evaluation declines: 353; legitimate declines: 126
- Sealed block precision: 64.305949%; legitimate declined amount: 4,100.62 CU
- Eight budget rates × two policies × 200 consecutive seeds (1729–1928): 3,200 draws
- Rates 0.25%, 0.5%, 1%, 2%, 5% are the spec sweep; 10%, 25%, 50% are explicitly diagnostic.
- First registered seed is displayed in the UI. No best-seed selection or oracle-based weight tuning.

`registered_design.json` is written before training/evaluation. `runs.csv` retains all trials, including zero-sample and unstable draws. `summary.csv` and `benchmark.json` hold aggregate results; `checksums.json` detects changed export bytes. A checksum is not authentication or protection against malicious code.

A separate full 3,200-draw rerun in `artifacts/synthetic-replay-2026-09-02/` matched all seven registered/exported file hashes and both population CSV files byte for byte in the verified local environment.

## Measured comparison

RMSE and theoretical standard error are in percentage points of population block precision. Coverage includes deliberately uninformative full-range intervals. Stability means the implementation's sample-count, effective-sample-size, class and range checks pass; it does not certify nominal coverage.

| Expected rate | Policy | RMSE (pp) | Exact design SE (pp) | Coverage | Stable trials | Full-range fallbacks |
|---:|---|---:|---:|---:|---:|---:|
| 0.5% | Uniform | 44.82 | 44.86 | 100% | 0% | 67.5% |
| 0.5% | Weighted | 46.09 | 46.72 | 100% | 0% | 65.0% |
| 5% | Uniform | 13.85 | 13.86 | 96% | 0% | 0% |
| 5% | Weighted | 13.28 | 14.46 | 91% | 0% | 0% |
| 25% · diagnostic | Uniform | 5.57 | 5.51 | 94% | 100% | 0% |
| 25% · diagnostic | Weighted | 5.40 | 5.81 | 94% | 100% | 0% |
| 50% · diagnostic | Uniform | 3.32 | 3.18 | 94.5% | 100% | 0% |
| 50% · diagnostic | Weighted | 3.55 | 3.44 | 92.5% | 100% | 0% |

At 5%, expected verification is only 17.65 cases. Both policies fail the stability gate in every trial. Weighted mean discovery precision is 40.23%, versus 35.35% for uniform. These are averages of defined selected-sample ratios, not population block precision and not evidence of approval or revenue recovery.

At this budget the paired Monte Carlo difference in squared error (weighted minus uniform) is −15.49 pp², with approximate 95% interval [−46.75, 15.77]. It crosses zero. All eight paired comparison intervals cross zero. The sample of 200 trials does not establish a weighted-policy accuracy advantage.

More strongly, the exact conditional design variance can be computed offline:

```text
Var(HT legitimate share) = sum_i Z_i * (1 - pi_i) / pi_i / N_declines^2
```

On this fixed population it is higher for weighted sampling at every tested budget. Small empirical RMSE wins in some settings should not override that result. Queue enrichment and population-estimation efficiency are different objectives.

## What is established

- The end-to-end no-key flow, randomized selections and estimator are reproducible on generated data.
- A tiny verification budget can leave decision quality poorly measured even when the estimator is design-unbiased.
- A selected queue may find more false declines while estimating the entire declined population less efficiently.
- Empty/single-class samples cannot legitimately be shown as certain answers. Their full-range fallback is explicitly counted.

## What remains open

- Full IEEE-CIS runtime, temporal data behavior and numerical results; raw files have not been provided.
- Useful interval precision at submission-relevant budgets on a sufficiently large real benchmark decline pool.
- Verification-evidence noise, delays and missingness. Current sampled labels are perfect offline oracle observations.
- Production applicability, real economic parameters and realized savings.
- Optional per-seed distribution charts and final submission packaging. Full trial distributions are exported to CSV now.

Do not tune weights, seeds or the threshold against this evaluation population and re-present it as fresh validation. Any new methodology needs separately registered evaluation evidence.
