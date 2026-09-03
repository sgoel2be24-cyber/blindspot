# Evidence reliability results · 2026-09-03

## What changed

BlindSpot now accepts a committed review batch with both resolved and pending cases, reports conservative bounds under explicit label-error assumptions, and produces a human-review audit receipt. The local CSV ingestion workflow does not read the oracle. The separate stress simulator tests the workflow against known truth; it is not a live analyst or dispute integration.

The original fraud model, uniform/weighted policies and primary HT/normal-interval benchmark are unchanged. This is post-benchmark sensitivity work, not a new held-out dataset or an improved primary estimator.

## Registered experiment

- Parent run: `e48d50631fc2ac97`, full IEEE-CIS controlled-censoring experiment.
- Reliability run: `1fbc8fe54f2bad87`, `artifacts/ieee-full-2026-09-03-reliability`.
- Eight fixed evidence scenarios × five primary budgets × two policies × 200 draw seeds = **16,000 trials**. Scenarios and evidence seed 90203 were recorded before running the stress simulation; all original selection seeds 1729–1928 are retained.
- Runtime: 190.95 seconds; maximum resident set size 217,645,056 bytes on this Mac. No retraining or raw-file load needed.
- All five output hashes, 80 scenario/policy/budget settings, and 16,000 unique trial keys checked. No raw rows are exported to this report or the reliability UI.
- A second complete 16,000-trial run in `artifacts/ieee-full-2026-09-03-reliability-replay` took 190.15 seconds and matched all five exports byte for byte. The seven original primary benchmark exports remain unchanged.
- Method and proof: [evidence reliability contract](EVIDENCE_RELIABILITY_CONTRACT.md). The new envelope is conservative and pointwise under fixed potential evidence, independent Bernoulli selection and a valid whole-population error allowance.

## A visible failure and a defensible response

At the pre-registered display seed 1729, uniform sampling and 5% expected budget select 244 reviews. In the deliberately simulated delay model, legitimate evidence arrives on day 2 and fraudulent evidence on day 14:

| As of | Resolved | Pending | Completed-only shortcut | Conservative BP range |
|---|---:|---:|---:|---:|
| Day 1 | 0 | 244 | Unavailable | 0%–100% |
| Day 7 | 165 | 79 | 0% | 0%–47.58% |
| Day 30 | 244 | 0 | 32.38% | 13.69%–47.58% |

The sealed population truth is 31.02%. The day-7 shortcut is wrong by 31.02 percentage points because it drops the unresolved fraudulent cases. The conservative range contains the truth without assuming missing-at-random response. These are fixed snapshot bounds, not an anytime-valid confidence sequence. Even by day 30, the interval is wide.

At an explicitly illustrative minimum acceptable block precision of 50%, the day-1 state cannot certify the policy; the later upper bound below 50% supports escalation to a human policy reviewer under the stated assumptions. It never recommends approving or rescuing an individual transaction.

## All scenarios at 5% budget

Each row is 200 draw seeds. Width is percentage points. The completed-only comparator is an inverse-selection-weighted ratio over resolved rows; it has no correction for selective missingness. It is different from the original primary HT estimator.

| Scenario | Policy | Mean resolved | Mean width (pp) | Completed-only RMSE (pp) | Abstention at 50% target |
|---|---|---:|---:|---:|---:|
| Perfect / delayed day 30 | Uniform | 258.07 | 33.89 | 2.64 | 25.0% |
| Perfect / delayed day 30 | Weighted | 258.03 | 41.68 | 3.74 | 55.0% |
| 30% randomly missing | Uniform | 178.93 | 64.52 | 3.35 | 100% |
| 30% randomly missing | Weighted | 180.22 | 70.32 | 4.78 | 100% |
| Truth-dependent missingness | Uniform | 192.05 | 54.08 | 15.70 | 83.5% |
| Truth-dependent missingness | Weighted | 206.97 | 57.64 | 16.17 | 94.5% |
| Delayed day 1 | Both | 0 | 100 | Unavailable | 100% |
| Delayed day 7 | Uniform | 178.49 | 47.80 | 31.02 | 25.0% |
| Delayed day 7 | Weighted | 206.91 | 51.37 | 31.02 | 55.0% |
| 5% wrong labels, allowance 5% | Uniform | 258.07 | 43.89 | 3.69 | 92.5% |
| 5% wrong labels, allowance 5% | Weighted | 258.03 | 51.56 | 4.18 | 96.0% |
| 5% wrong labels, wrongly assumed perfect | Uniform | 258.07 | 33.89 | 3.69 | 49.5%* |
| 5% wrong labels, wrongly assumed perfect | Weighted | 258.03 | 41.68 | 4.18 | 76.5%* |

*The assumption-violation rows have no stated coverage guarantee; the UI refuses to endorse their audit status. Numerical status rates are retained for diagnostics, not presented as valid confidence statements.*

All 16,000 simulated ranges contained the oracle value and no computed non-abstaining 50%-threshold statement contradicted it. **This is not 100% accuracy, universal coverage, or a production safety claim.** Broad/full ranges make coverage easier. At 0.25% and 0.5% budgets every scenario/policy combination abstains at that target; at 5%, many still abstain. The 2,000 deliberately invalid-assumption trials happened to cover here, which cannot validate their false assumptions.

## Implemented evidence interface

```bash
python -m blindspot.audit prepare \
  --pool artifacts/ieee-full-2026-09-03/product/declines.csv \
  --output artifacts/new-audit --policy uniform --budget-rate 0.05

# Copy evidence-template.csv, then populate actual resolved review labels.
# Every committed row must remain present; unresolved rows stay pending with no label.
python -m blindspot.audit ingest \
  --plan artifacts/new-audit --evidence path/to/review-batch.csv \
  --output artifacts/new-audit/review-receipt.json \
  --max-population-label-error 1
```

The example uses error allowance 1 when no externally justified bound is available, so it deliberately cannot certify anything. A smaller allowance must be independently justified, not chosen to obtain a pleasing answer. The local smoke receipt in `artifacts/ieee-audit-demo-2026-09-03/pending-receipt.json` has 244 pending cases and range 0–100%. No actual analyst decisions were fabricated.

## Acceptance and remaining gaps

40 tests pass, including commitment/ID validation, pending-label rejection, true-census bounds, monotone uncertainty, exact finite-population enumeration, scenario replay, immutable receipts, source-run binding and UI reveal tests. The existing benchmark and no-key tests still pass. A browser check found a cached-module import failure in the long-running demo; restarting that exact local server loaded the updated real-data app.

Actual-browser interactions verified day 1, day 7 and day 30 counts/ranges, pending-case retention, the insufficient-evidence state and separate offline reveal of 31.02%. The day-7 section was also reviewed in a screenshot. The receipt button is rendered and its payload construction is implemented; an actual browser download was not independently inspected in this check.

An isolated source copy excluded ignored raw data, artifacts and the original environment. Fresh installation from the documented constraints passed all 40 tests, the no-key demo, new command entrypoints and the full documented 50,000-row synthetic benchmark (3,200 trials). This checks current local source without licensed inputs; public checkout availability still depends on release.

The new capability establishes a functioning local evidence interface and a falsifiable robustness demonstration. It does not establish live evidence-source quality, authenticated provenance, workload-independent delays, actual merchant savings, or winning odds. Public release, final video and submission approval remain separate gates.
