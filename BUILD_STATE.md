# BlindSpot build state

Last updated: 2026-09-03

## Frozen identity

- Track: 02 — AI Risk Manager
- Thesis: false-positive verification under decision-induced missing outcomes
- Scope source: `docs/ENGINEERING_SPEC_V1.md`

## Current gate

P0/P1 complete on deterministic synthetic data. Repeated-seed benchmark and three interactive screens are implemented and tested. Real-data validation and final submission readiness are not complete.

## Implemented

- Engineering Spec v1 frozen
- repository guardrails and raw-data boundary
- data provenance and failure-log templates
- IEEE-CIS local loader with optional identity join and schema validation
- stable, time-tie-safe train/calibration/evaluation split
- deterministic numeric HistGradientBoosting incumbent and calibration-only threshold
- trusted censoring harness with label-free product pool and separate sealed oracle
- uniform and margin-weighted Bernoulli verification with non-zero propensities
- canonical full-ledger SHA-256 commitment and evaluator integrity checks
- Horvitz–Thompson/Hájek estimates, 95% design intervals, discovery metrics, and economics
- runnable `blindspot-demo` aggregate JSON path
- `blindspot-benchmark` local CLI for either generated data or IEEE-CIS, with pre-run design registration, source hashes, all-seed CSV and JSON exports
- paired uniform/weighted comparison, exact conditional design variance, Monte Carlo coverage bounds, and explicit fallback/stability accounting
- empty/single-class non-census CI fallback with exact-census exception; no minimum-one expected-budget rounding
- three working Streamlit views: evidence-aware overview, searchable/exportable queue, and offline budget comparison with economic sliders
- artifact-only dashboard reader; hash verification and filename allowlist; separate sampled-evidence and offline-oracle reveals
- repository-scoped readable light theme and disabled usage telemetry
- optional verified-version constraints for local reproducibility

## Verified

- The repository is isolated under `blindspot/`; the project mirror's root `AGENTS.md` and `sources/` remain untouched.
- Editable installation succeeded with Python 3.12.
- `ruff check` and `ruff format --check` pass.
- 28 tests pass, including AC-01 through AC-06, exact design-unbiasedness enumeration, empty/single-class/census bounds, all-seed retention, oracle-label permutation, shuffle replay, artifact tampering, overwrite refusal and interactive screen tests.
- `blindspot-demo` exits 0, emits valid JSON, and marks its synthetic estimate stable.
- Raw, processed, sealed, virtual-environment, and artifact paths are ignored by Git.
- Synthetic run `11a911eb5d6b31ad`: 50,000 inputs, 353 evaluation declines, 126 legitimate declines, 64.305949% oracle block precision. Eight rates × two policies × 200 seeds = 3,200 retained trials.
- A second complete 3,200-draw replay in `artifacts/synthetic-replay-2026-09-02` matched all seven registered/exported file hashes; the product and sealed CSVs also matched byte for byte.
- At 5% expected budget (17.65 cases), both policies fail stability checks in all trials. Weighted sampling's population-estimation advantage is not established; exact design variance is worse than uniform on this population. See `docs/SYNTHETIC_BENCHMARK_2026-09-02.md`.
- Actual browser verified hidden overview, sampled reveal, queue navigation, benchmark reveal and rendered comparison chart. Browser console error check returned none. Screenshot QA found and fixed a dark-theme contrast issue.
- Git branch: `main`. Source repository: `https://github.com/sgoel2be24-cyber/blindspot` (private), created for the initial GitHub handoff on 2026-09-03. No hosted app deployment. Raw data, generated evidence, local environments and credentials are excluded from source control.
- Pre-push verification on 2026-09-03: all 28 tests, lint and formatting checks pass; upload candidates were reviewed for raw/artifact files and obvious credential patterns.

## Not yet verified

- real IEEE-CIS load or full-data runtime
- real IEEE-CIS numerical metrics
- production verification-evidence noise/latency sensitivity
- acceptable interval precision/coverage at relevant budgets on real data
- optional per-seed distribution charts in the UI (all trials already exported in CSV)
- final submission materials, rehearsal and official current deadline/rubric check

## Next action

Provide the local folder containing `train_transaction.csv` (and optionally `train_identity.csv`). The project and checked Downloads location had no matching raw files. Follow the prefix-smoke command in README, then run the registered full-data benchmark without `--nrows`; record runtime and retain all outcomes even if uniform wins.

The no-key demo is available without those files: build the synthetic bundle, then launch the dashboard from the repository root. The default artifact directory is `artifacts/synthetic-2026-09-02`; do not overwrite it. Use a fresh directory for new evidence.

## Methodology amendment

`ENGINEERING_SPEC_V1.md` section 18 records the failing-test-driven empty/single-class uncertainty fix, exact expected budgets, diagnostic rate labeling and sampled-evidence export boundary. `FAILURE_LOG.md` contains the actual regression and visual QA failure. Core identity, estimand and policies remain frozen.

## Scope watch

No RiskTwin, rescue scorer, multi-agent framework, LLM, database, or API-key dependency has been approved.
