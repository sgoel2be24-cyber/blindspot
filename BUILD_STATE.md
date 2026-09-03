# BlindSpot build state

Last updated: 2026-09-03

## Frozen identity

- Track: 02 — AI Risk Manager
- Thesis: false-positive verification under decision-induced missing outcomes
- Scope source: `docs/ENGINEERING_SPEC_V1.md`

## Current gate

P0/P1 and the bounded evidence-reliability extension are complete. Synthetic/full IEEE-CIS benchmarks and the separate 16,000-trial stress run replay identically; three interactive screens and a local evidence-import interface are implemented and tested. Pitch script, architecture and submission control sheet exist. Video, public judge access and final submission remain incomplete. No primary model or sampler settings were changed.

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
- local label-free plan preparation, complete pending/resolved CSV ingestion and immutable audit receipts
- conservative partial-identification bounds under explicitly assumed whole-population label-error budgets; pointwise, not anytime-valid
- eight fixed missing/delayed/noisy evidence scenarios in an independently replayable secondary experiment
- aggregate reliability lab inside Budget Lab, with separate sampled-evidence/oracle gates and receipt download
- architecture, five-minute pitch script and claim/proof submission checklist

## Verified

- The repository is isolated under `blindspot/`; the project mirror's root `AGENTS.md` and `sources/` remain untouched.
- Editable installation succeeded with Python 3.12.
- `ruff check` and `ruff format --check` pass.
- 40 tests pass, including AC-01 through AC-06, exact design-unbiasedness enumeration, empty/single-class/census bounds, all-seed retention, oracle-label permutation, shuffle replay, artifact tampering, overwrite refusal, committed pending/resolved batches, exact evidence-bound enumeration, source-bound reliability exports and interactive screen tests.
- `blindspot-demo` exits 0, emits valid JSON, and marks its synthetic estimate stable.
- Raw, processed, sealed, virtual-environment, and artifact paths are ignored by Git.
- Synthetic run `11a911eb5d6b31ad`: 50,000 inputs, 353 evaluation declines, 126 legitimate declines, 64.305949% oracle block precision. Eight rates × two policies × 200 seeds = 3,200 retained trials.
- A second complete 3,200-draw replay in `artifacts/synthetic-replay-2026-09-02` matched all seven registered/exported file hashes; the product and sealed CSVs also matched byte for byte.
- At 5% expected budget (17.65 cases), both policies fail stability checks in all trials. Weighted sampling's population-estimation advantage is not established; exact design variance is worse than uniform on this population. See `docs/SYNTHETIC_BENCHMARK_2026-09-02.md`.
- Actual browser verified hidden overview, sampled reveal, queue navigation, benchmark reveal and rendered comparison chart. Browser console error check returned none. Screenshot QA found and fixed a dark-theme contrast issue.
- Git branch: `main`. Source repository: `https://github.com/sgoel2be24-cyber/blindspot` (private), created for the initial GitHub handoff on 2026-09-03. No hosted app deployment. Raw data, generated evidence, local environments and credentials are excluded from source control.
- Pre-push verification on 2026-09-03: all 28 tests, lint and formatting checks pass; upload candidates were reviewed for raw/artifact files and obvious credential patterns.
- Real-data verification on 2026-09-03: full run `e48d50631fc2ac97` and full 3,200-trial replay have identical seven export hashes and both population CSVs. Raw-to-oracle confusion counts, summary calculations and displayed HT estimates independently reconcile. Real-data bundle passes application tests through all three screens and both reveal gates. The dashboard now prefers that local real-data bundle when present, otherwise the generated-data default; `BLINDSPOT_RUN_DIR` overrides either.
- Reliability run `1fbc8fe54f2bad87`: eight scenarios × five primary budgets × two policies × 200 seeds = 16,000 retained trials. Independent full replay matches all five stress export hashes; seven primary exports remain unchanged. All simulated ranges cover here, often by being wide/uninformative; this is not 100% accuracy or production validation.
- Actual browser verified delayed day 1 (0 resolved/244 pending, full range), day 7 (165/79, 0–47.6%) and day 30 (244/0, 13.7–47.6%), plus separate oracle reveal (31.02%). Screenshot reviewed the day-7 section. A stale-module import required restarting only this local app; see FAILURE_LOG.
- Actual local audit CLI prepared 244 reviews and ingested an untouched pending template: immutable receipt, full range and insufficient evidence. Resolved ingestion is covered by generated-label tests, not claimed as real analyst verification.
- Isolated source-copy setup on 2026-09-03 excluded all ignored data/artifacts/environments, installed fresh dependencies using `requirements-verified.txt`, passed all 40 tests, ran the no-key demo/new CLI entrypoints, and regenerated the documented 50,000-row/3,200-trial synthetic benchmark. This tests current local source, not yet a public GitHub checkout.

## Not yet verified

- production usefulness or generalization beyond the controlled benchmark
- actual production evidence quality and selection-independent availability; simulated noise/missingness/latency are now tested but do not establish these properties
- useful interval precision at realistic operational budgets; low-budget limitations remain
- optional per-seed distribution charts in the UI (all trials already exported in CSV)
- finished video, access through the final published checkout, public release approval, rehearsal and exact current portal/deadline check

## Next action

The user supplied the official training archive on 2026-09-03. Full IEEE-CIS run `e48d50631fc2ac97` completed in 91.69 seconds: 590,540 rows; split 413,378/88,581/88,581; 5,158 declines, 3,558 legitimate; all 3,200 trials retained. Source and seven export hashes, independent confusion counts, displayed HT estimates and summary aggregates reconcile. See `docs/IEEE_CIS_BENCHMARK_2026-09-03.md` and the executed validation notebook.

At 5% expected budget, weighted discovery precision is 80.20% versus uniform 69.18%, but BP RMSE is 5.21 versus 4.90 pp and exact design variance is worse for weighted at every budget. The core default 0.5% budget remains unreliable. The extended suite now has 40 passing tests.

Next: follow `docs/SUBMISSION_KIT.md` to record/review the five-minute video and obtain explicit approval before public visibility/final submission. Isolated source-copy setup passes; recheck public judge access after release. The reliability contract, results, architecture and pitch script are included in this source revision; no finished video exists. Do not retune against held-out results or upload row-level artifacts.

GitHub source update · 2026-09-03: Shikhar authorized syncing all remaining work to the existing private repository. This revision includes the full-data aggregate report and executed validation notebook, review-import tools, reliability extension, plain-language UI and submission documents. Pre-sync checks: all 40 tests, lint, formatting and whitespace checks pass; source candidates and notebook outputs reviewed; no raw/selected/sealed transaction rows or obvious credentials included. GitHub visibility and final-submission approval are unchanged.

The no-key demo is available without licensed files: build the synthetic bundle, then launch from the repository root. Defaults prefer `artifacts/ieee-full-2026-09-03` if present, otherwise `artifacts/synthetic-2026-09-02`. Use explicit `BLINDSPOT_RUN_DIR` for recording and fresh directories for new runs; never overwrite earlier evidence.

## Methodology amendment

`ENGINEERING_SPEC_V1.md` section 18 records the failing-test-driven empty/single-class uncertainty fix, exact expected budgets, diagnostic rate labeling and sampled-evidence export boundary. `FAILURE_LOG.md` contains the actual regression and visual QA failure. Core identity, estimand and policies remain frozen.

Section 19 and `docs/EVIDENCE_RELIABILITY_CONTRACT.md` document the user-requested secondary robustness extension and its assumptions. It does not replace or improve the original primary benchmark by assertion.

## Scope watch

### Plain-language presentation · 2026-09-03

At Shikhar's request, the app now presents three steps: Blocked payments, Check a sample, and Can we trust the result? Headings, review controls, missing-answer warnings and the pitch use everyday language. Detailed statistical comparisons remain in expandable sections; the engineering contract and numeric evidence are unchanged. `docs/PLAIN_LANGUAGE_GUIDE.md` defines the explanation and vocabulary. Updated UI tests cover the new labels, separate reveal gates and missing-answer warning. No new model, feature pipeline, service or public publication is part of this change.

Verification: all 40 tests, lint, formatting and whitespace checks pass. Actual browser checks confirmed the new opening screen, review-results switch, third-screen navigation and day-1 missing-answer state; a screenshot confirmed readable labels at the current viewport. Restarting only the local server cleared cached wording. No narrow/mobile viewport check was performed in this copy pass.

No RiskTwin, rescue scorer, multi-agent framework, LLM, database, or API-key dependency has been approved.
