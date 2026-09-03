# BlindSpot

BlindSpot answers one question:

> How do you know your fraud model was right about the payments it never allowed to happen?

BlindSpot helps a risk team check whether its fraud rules are blocking good payments. It picks a sample to review, estimates what may be happening in the whole group, and shows when there is not enough evidence to conclude. It does not approve or block payments.

Start with the [plain-language explanation](docs/PLAIN_LANGUAGE_GUIDE.md). The technical method and test results remain available below.

## Status

The three-screen application, local review-evidence import and no-key synthetic flow work. A full 590,540-row IEEE-CIS benchmark retains all 3,200 registered trials. A separate 16,000-trial reliability experiment tests pending, delayed and incorrect evidence; both experiments replay identically. All 40 tests pass.

Start with the [submission guide](docs/SUBMISSION_KIT.md), [five-minute pitch script](docs/PITCH_SCRIPT.md) and [architecture](docs/ARCHITECTURE.md). Inspect the [engineering spec](docs/ENGINEERING_SPEC_V1.md), [build state](BUILD_STATE.md), [synthetic results](docs/SYNTHETIC_BENCHMARK_2026-09-02.md), [real-data findings](docs/IEEE_CIS_BENCHMARK_2026-09-03.md) and [reliability results](docs/RELIABILITY_RESULTS_2026-09-03.md). Weighted sampling improves review-queue discovery here, not population-estimation accuracy. Video, public judge access and final submission are not complete.

## Core flow

```text
IEEE-CIS or synthetic labeled transactions
  -> chronological train/calibration/evaluation split
  -> deterministic incumbent baseline and frozen threshold
  -> product decline pool + separately sealed oracle
  -> randomized verification plan with known propensities
  -> Horvitz-Thompson estimate, confidence interval, and offline proof
```

No API key, hosted service, database, LLM, or raw IEEE-CIS bundle is required for the synthetic test flow.

## Local setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
blindspot-demo
```

`blindspot-demo` prints aggregate JSON and explicitly labels its numbers as synthetic smoke-test evidence. It never prints sealed row-level outcomes.

IEEE-CIS placement and limitations are documented in [DATA_PROVENANCE.md](DATA_PROVENANCE.md).

## Run the interactive demo

From this repository directory:

```bash
python -m pip install -e '.[dev,ui]' -c requirements-verified.txt
blindspot-benchmark --source synthetic --rows 50000 --repetitions 200 --output artifacts/synthetic-2026-09-02
streamlit run apps/dashboard.py --server.address 127.0.0.1 --server.headless true
```

Open `http://127.0.0.1:8501`. If the bundle already exists, skip the benchmark command; it deliberately refuses to overwrite an earlier run. Use a new output directory for a new experiment, then set `BLINDSPOT_RUN_DIR` to that directory before launching the dashboard. Always launch from the repository root so its readable light theme and disabled usage telemetry apply.

The default prefers the local `artifacts/ieee-full-2026-09-03` bundle when present, otherwise `artifacts/synthetic-2026-09-02`. A clean checkout contains neither; the command above builds the generated-data demo. Set `BLINDSPOT_RUN_DIR` explicitly for recording or reproducibility.

The dashboard has three working views:

1. **Blocked payments:** were good payments blocked? See estimates and how uncertain they are.
2. **Check a sample:** inspect the chosen reviews, show their answers, find a payment and export the list.
3. **Can we trust the result?:** compare review methods and try simulated late or wrong answers. Download a review summary. Cost controls show assumptions, not money saved. Technical comparisons remain in expandable sections.

The offline answer key is opt-in and separate from verified-sample evidence. These are presentation gates, not authentication. The dashboard reads allowlisted, hash-checked exports; it never loads `sealed/truth.csv` or imports the evaluator. Selection code sees neither outcome set.

At the default 5% display budget, the small synthetic population provides insufficient evidence. On that fixture, use 25% **diagnostic** budget to inspect a larger-sample state; do not present it as a 5% result. Neither the synthetic nor real-data comparison establishes weighted superiority for population estimation.

## Run IEEE-CIS locally

Once you have obtained the licensed files:

```bash
blindspot-benchmark --source ieee-cis --raw-dir data/raw/ieee-cis --nrows 50000 --repetitions 2 --output artifacts/ieee-prefix-smoke
blindspot-benchmark --source ieee-cis --raw-dir data/raw/ieee-cis --repetitions 200 --output artifacts/ieee-full
BLINDSPOT_RUN_DIR=artifacts/ieee-full streamlit run apps/dashboard.py --server.address 127.0.0.1
```

The first command is only a prefix smoke test, not a full-data result. Add `--identity` to include the optional identity file. The CLI records input hashes, temporal windows, configuration, package versions and all trial results. No Kaggle credentials are read or needed by the core.

## Reliability experiment and review import

Build a separate stress bundle against an existing benchmark without changing its model, policy or primary estimates:

```bash
python -m blindspot.reliability --source-bundle artifacts/synthetic-2026-09-02 --output artifacts/synthetic-2026-09-02-reliability --repetitions 200
```

The dashboard finds the adjacent `-reliability` directory; `BLINDSPOT_RELIABILITY_DIR` overrides it. The experiment uses simulated evidence, not live analyst decisions. See the [contract and assumptions](docs/EVIDENCE_RELIABILITY_CONTRACT.md).

A separate local interface accepts actual review batches without reading oracle truth:

```bash
python -m blindspot.audit prepare --pool artifacts/synthetic-2026-09-02/product/declines.csv --output artifacts/new-audit --policy uniform --budget-rate 0.05
python -m blindspot.audit ingest --plan artifacts/new-audit --evidence artifacts/new-audit/evidence-template.csv --output artifacts/new-audit/pending-receipt.json --max-population-label-error 1
```

The untouched template has all reviews pending, so the receipt correctly reports insufficient evidence. Populate a copy with real review outcomes, keeping every selected ID and leaving unresolved labels blank. A smaller error allowance needs independent justification across the whole declined population; unknown error means allowance 1 and no certification. This is a CSV interface, not an authenticated production evidence connector.

## Verification

```bash
ruff check src apps tests
ruff format --check src apps tests
pytest -q
```

UI tests skip if Streamlit is not installed. Core tests use generated data only. Output bundles, selected evidence, sealed truth and raw inputs are ignored by Git. No external publication is part of these commands.

## Claims discipline

- Benchmark labels are an offline sealed oracle, not guaranteed production truth.
- Discovery precision is a queue metric, not population block precision.
- Discovery recall and oracle block precision are offline-only.
- Dataset amounts are currency units, not INR.
- IEEE-CIS claims refer only to the recorded full-data controlled-censoring experiment, never Razorpay traffic or production performance.
