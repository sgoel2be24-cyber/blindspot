# IEEE-CIS full-data benchmark · 2026-09-03

The real-data pipeline runs successfully without an API key or a change to the frozen design. Margin weighting enriches the review queue, but does **not** establish better population estimation than uniform sampling. Tiny verification budgets remain unreliable.

## Evidence and reproduction

- Input: user-supplied `train_transaction.csv.zip`, archive integrity checked, extracted locally without overwriting or uploading data. CSV SHA-256: `3a5c83ab6b3cc13dcabe5ffa9f522307fd5f7f7b6e6f6a60c32284ca6283d642`.
- Full run: `artifacts/ieee-full-2026-09-03`, ID `e48d50631fc2ac97`; no row limit, no identity join. Original model, threshold rule, sampling policies and seeds unchanged.
- Runtime: 91.69 seconds end-to-end on this Mac; maximum resident set size 4,463,755,264 bytes. The OS separately reported peak memory footprint 9,986,121,552 bytes; RSS alone understates the memory envelope. No swaps reported for the process.
- Preliminary 50,000-row prefix smoke test: 6.48 seconds, run `8992f449434a6b93`. Its results are not used as full-data evidence.
- Eight registered rates × two policies × 200 seeds (1729–1928): all 3,200 trials retained. Higher 10%, 25%, 50% rates remain diagnostic, not substitutes for primary-budget results.
- Complete replay: `artifacts/ieee-full-replay-2026-09-03`, 93.96 seconds. All seven registered/exported file hashes and both product/sealed population CSVs match byte-for-byte. All 28 tests pass; the real-data bundle also passes Streamlit application tests for all three screens and both reveal gates. No fresh browser screenshot review or change to the running synthetic dashboard was made in this data-validation turn.
- [Validation notebook](IEEE_CIS_VALIDATION.ipynb): all five Python cells executed top-to-bottom using the project environment; actual aggregate stdout is saved. A lightweight cell runner was used, not a Jupyter kernel. Checks reconcile the raw data, sealed decisions, exported summaries and all 16 displayed HT estimates. No raw rows are embedded.

```bash
.venv/bin/blindspot-benchmark --source ieee-cis --raw-dir data/raw/ieee-cis --repetitions 200 --output artifacts/ieee-full-new
```

Never overwrite existing evidence. The registered design, manifest, all-seed results and seven export checksums are saved in each bundle. This report contains aggregates only; all row-level data and generated bundles stay local and gitignored.

## Data quality and chronological isolation

590,540 transactions, 394 input columns, 20,663 fraud labels. No duplicate transaction IDs, no missing required ID/time/amount/target values, no nonfinite required numeric values, no negative amounts and no invalid binary targets.

| Window | Rows | Fraud rows | Relative time bounds |
|---|---:|---:|---|
| Train | 413,378 | 14,538 | 86,400–10,437,996 |
| Calibration | 88,581 | 3,042 | 10,438,003–13,151,840 |
| Evaluation | 88,581 | 3,083 | 13,151,880–15,811,131 |

All rows are assigned once with strict time separation. `TransactionDT` is relative time, not a calendar date. Fraud prevalence is approximately 3.52%, 3.43%, 3.48% respectively; these descriptive checks do not rule out feature drift or unavailable post-outcome information.

64 numeric features were selected using training-only nonmissing rates and lexical tie-breaking. Of those, 48 have at least one missing value across the full file; the largest selected-feature null rate is 0.0532%. The incumbent's existing missing-value handling is unchanged. The other input columns were not profiled for every possible data-quality defect.

## Incumbent: calibration is not held-out evaluation

Frozen threshold: **0.7330326382903609**. Calibration average precision 0.442856, ROC-AUC 0.879948, precision 34.54%, recall 50.39%, decline rate 5.01%. Average precision is the implemented PR summary; it is not relabeled as trapezoidal PR-AUC.

Independent held-out confusion counts reconstructed from raw labels and frozen declined IDs:

| Metric | Held-out result |
|---|---:|
| True positives / false positives | 1,600 / 3,558 |
| False negatives / true negatives | 1,483 / 81,940 |
| Fraud precision (= oracle block precision) | 31.02% |
| Fraud recall | 51.90% |
| False-positive rate among legitimate payments | 4.16% |
| Declines / evaluated transactions | 5,158 / 88,581 (5.82%) |

Of the 5,158 declines, 3,558 (68.98%) are legitimate under the offline oracle. Their total amount is **599,035.699 CU**. This is a deliberately modest frozen incumbent, not a competitive fraud detector or an estimate of Razorpay's performance. Full-evaluation average precision and ROC-AUC are not exported and are not claimed; decline-only score exports cannot reconstruct them.

## Verification results

Budget is an expected fraction of the **5,158 declined rows**, not all input transactions. Realized counts fluctuate. RMSE and interval widths are percentage points of block precision; coverage is the fraction of 200 intervals containing this fixed oracle value. Discovery precision is the legitimate share of the selected queue, never the population estimate.

| Budget | Expected checks | Policy | BP RMSE (pp) | Mean CI width (pp) | Coverage | Stable draws | Discovery precision |
|---|---:|---|---:|---:|---:|---:|---:|
| 0.25% | 12.895 | Uniform | 22.62 | 69.76 | 93.5% | 0% | 68.94% |
| 0.25% | 12.895 | Weighted | 22.99 | 72.54 | 94.5% | 0% | 79.16% |
| 0.5% | 25.79 | Uniform | 15.68 | 55.88 | 90.5% | 17.5% | 68.31% |
| 0.5% | 25.79 | Weighted | 15.98 | 56.96 | 93.5% | 0% | 79.65% |
| 1% | 51.58 | Uniform | 10.95 | 43.08 | 95.5% | 99% | 69.18% |
| 1% | 51.58 | Weighted | 10.56 | 44.34 | 93.5% | 91.5% | 80.03% |
| 2% | 103.16 | Uniform | 7.83 | 31.48 | 95.0% | 100% | 69.28% |
| 2% | 103.16 | Weighted | 7.29 | 32.60 | 96.0% | 100% | 80.00% |
| 5% | 257.90 | Uniform | 4.90 | 19.78 | 96.0% | 100% | 69.18% |
| 5% | 257.90 | Weighted | 5.21 | 20.51 | 96.5% | 100% | 80.20% |

At 5%, mean discovery recall is 5.02% uniform versus 5.82% weighted; the denominator is all 3,558 legitimate declined transactions and is offline-only. Discovery precision/recall are means across the registered draws, not pooled or cherry-picked single-run metrics.

### What the comparison does and does not support

- Weighted sampling increases the proportion of false declines in the review queue in this experiment: at 5%, 80.20% versus 69.18%, a descriptive 11.02 percentage-point difference.
- It does not improve the primary population estimator here. Exact conditional design variance is higher for weighted sampling at all eight rates. At 5%, exact design SE is 5.24 pp weighted versus 5.04 pp uniform. All five primary-budget paired MSE-difference intervals include zero. The diagnostic 50% rate has a positive difference interval (0.204–0.806 pp²), favoring uniform.
- The default core 0.5% budget is not sufficient for precise estimates. Uniform coverage is 90.5%, with Wilson Monte Carlo interval 85.64%–93.83%, below nominal 95%. Weighted stability is 0% at this budget; nominal-looking aggregate coverage is not a guarantee.
- At 0.25%, fallback fractions are 1% uniform and 7% weighted; at 0.5%, 0% and 1%. No empty draws occurred. Full-range fallbacks do not count as useful precision.
- Even at 5%, mean interval widths remain about 20 percentage points. Stability checks passing does not imply a narrow interval or a universally valid confidence procedure. Coverage MC bounds at 5% are 92.31%–97.96% uniform and 92.95%–98.29% weighted.
- Repetitions vary verification draws, not the trained model or underlying dataset. They do not establish cross-merchant generalization, production label reliability, or causal savings.

## Frozen demonstration seed and economics

At pre-registered seed 1729 and 5% budget, weighted sampling verifies 238 cases and finds 187 legitimate declines. Its HT block-precision estimate is 37.61%, CI 27.89%–47.33%, containing the 31.02% offline truth. The single draw is illustrative only; use the repeated-seed table for performance claims.

Weighted estimated false-decline amount: 611,583.29 CU (CI 426,132.01–797,034.58). At the explicitly assumed 10% contribution margin, this corresponds to 61,158.33 CU margin at risk, not recovered savings. At 1 CU per review, review cost is 238 CU. If every sampled case had instead been approved and every fraudulent amount lost, sampled fraud exposure would be 8,147.456 CU. That is a hypothetical evidence-mechanism scenario, not an action BlindSpot takes.

## Remaining submission work

The data-access and full-runtime gates are cleared. No sampling/model retuning was performed after seeing evaluation outcomes. Remaining work includes realistic evidence noise/missingness/latency assumptions, judge-safe demo packaging, pitch and architecture materials, verified submission requirements, and explicit approval before public publishing or final submission. Real-data metrics alone do not make the project production-ready or guarantee a win.
