# Failure log

Record factual build or methodology failures only. Do not invent a failure for the submission narrative.

| Date | Gate | Failure | Evidence | Recovery | Verification |
|---|---|---|---|---|---|
| 2026-08-24 | P1 no-key demo | Split manifest contained NumPy scalar time bounds, so `json.dumps` raised `TypeError: Object of type int64 is not JSON serializable`. | `blindspot-demo` failed after the statistical pipeline completed. | Convert NumPy manifest scalars to Python scalars and add a JSON serialization regression assertion. | Demo rerun exited 0; 19 tests and lint passed. |
| 2026-09-02 | Low-budget uncertainty | Empty sample claimed zero-width certainty at 100% block precision. | New empty-sample regression failed: actual CI `(1, 1)`, expected `(0, 1)`. | Full-range fallback for empty/single-class non-census samples; retain instability and count fallbacks. | Regression, census exceptions and tiny-budget sweep tests pass. |
| 2026-09-02 | Browser QA | Light card backgrounds inherited white text from the browser's dark theme. | Actual dashboard screenshot showed unreadable metrics and sidebar labels; functional tests did not catch it. | Repository-scoped explicit light theme, then browser refresh. | Follow-up screenshot showed readable navy text and all values. |

### 2026-08-24 — Run manifest was not JSON-safe

- Gate: P1 no-key synthetic demo.
- Expected: `blindspot-demo` prints a complete aggregate JSON report.
- Observed: the experiment completed, then serialization failed on `numpy.int64` time bounds.
- Reproduction: run `.venv/bin/blindspot-demo` before the fix.
- Root cause: `TemporalSplit.manifest()` returned pandas/NumPy reduction scalars directly.
- Recovery: normalize NumPy scalars through `.item()` at the manifest boundary.
- Verification: demo rerun exited 0 and printed valid JSON; 19 tests and lint passed.
- Follow-up: keep run-artifact contracts JSON-safe and test serialization explicitly.

### 2026-09-02 — Empty verification falsely implied certainty

- Gate: repeated-seed, low-budget comparison.
- Expected: no observed outcomes must not imply known population block precision.
- Observed: an empty sample returned HT legitimate count 0, plug-in SE 0, and block-precision interval [1, 1].
- Reproduction: `test_empty_verification_does_not_claim_perfect_block_precision` failed before the change.
- Root cause: the normal plug-in variance treated an empty sum as sufficient evidence of no variance.
- Recovery: preserve the design-unbiased point estimate, but use the full possible range and an explicit uninformative fallback for non-census empty/single-class samples. Apply the analogous bound to amount intervals. Suppress the empty-sample point in the UI.
- Verification: empty/single-class and exact-census regressions pass; sweep test keeps all empty draws with full-range bounds. The 3,200-draw report counts fallback intervals separately from useful uncertainty.
- Follow-up: the fallback is conservative but not informative. Nondegenerate normal intervals remain approximate; report their empirical coverage and do not imply the bug fix proves universal 95% coverage.

### 2026-09-03 — CLI data access and low-budget validation limits

- Data-access failure: Kaggle CLI returned HTTP 403 for the training download, including after a user-reported browser step. Root cause was not conclusively established. Recovery: the user supplied their browser-downloaded archive; integrity and source hashes passed, and the full local benchmark completed without a download API or credentials in the core.
- Statistical limitation observed, not a software regression: on the full IEEE-CIS population, the frozen 0.5% budget produces uniform empirical coverage 90.5% (200 draws; Wilson bounds 85.64%–93.83%) and weighted stability 0%. No settings or intervals were silently retuned. All draws are retained and the limitation is disclosed in `docs/IEEE_CIS_BENCHMARK_2026-09-03.md`.

### 2026-09-03 — Live demo retained a stale imported module

- Gate: actual-browser QA of the reliability extension.
- Expected: the running Streamlit app imports the new hash-checked reliability reader.
- Observed: the browser displayed `ImportError: cannot import name read_reliability`; fresh application tests passed.
- Root cause: the long-running server retained an older imported `blindspot.dashboard_data` module after the source edit.
- Recovery: verify the exact process serving this project on local port 8501, stop that process only, and restart the same local app. No unrelated process or user data was changed.
- Verification: actual browser loaded the IEEE-CIS bundle, the selected-evidence reveal and day-1/day-7 reliability states; the suite also passes in fresh processes.
- Follow-up: include a clean server restart in rehearsal after module changes; application tests alone do not prove that an already-running demo has refreshed imports.
- Later plain-language pass: the running process also retained old `reliability_view` wording while the main screen refreshed. Confirmed the mismatch in the actual browser, restarted only the verified local demo process, and rechecked the updated section. The automated suite stayed green; this was stale presentation code, not changed evidence.

## New entry template

```text
### YYYY-MM-DD — Short title

- Gate:
- Expected:
- Observed:
- Reproduction:
- Root cause:
- Recovery:
- Verification:
- Follow-up:
```
