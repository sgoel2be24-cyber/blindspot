# BlindSpot

BlindSpot answers one question:

> How do you know your fraud model was right about the payments it never allowed to happen?

It creates a controlled declined population, allocates randomized verification with known non-zero propensities, and estimates block precision and false-decline cost with confidence intervals. It measures fraud-policy decisions; it does not make them.

## Status

P0/P1 core, repeated-seed comparisons and all three dashboard screens work on the synthetic no-key path. Real IEEE-CIS validation remains open. See [the engineering spec](docs/ENGINEERING_SPEC_V1.md), [build state](BUILD_STATE.md) and [measured synthetic results](docs/SYNTHETIC_BENCHMARK_2026-09-02.md).

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

The dashboard has three working views:

1. **Blind Region Overview:** starts with unknown outcomes; opt into the committed sample's estimates and uncertainty.
2. **Verification Queue:** actual randomized selections, propensities, evidence reveal, transaction search and CSV export.
3. **Budget Lab:** explicitly opt into offline truth-based comparisons; inspect error, interval width, coverage, stability and discovery recall. Economic sliders show assumptions, not savings.

The offline answer key is opt-in and separate from verified-sample evidence. These are presentation gates, not authentication. The dashboard reads allowlisted, hash-checked exports; it never loads `sealed/truth.csv` or imports the evaluator. Selection code sees neither outcome set.

At the default 5% budget, this small synthetic population provides insufficient evidence. Use 25% **diagnostic** budget to inspect a larger-sample state; do not present that as a 5% result. The 200-seed comparison has not established that weighted sampling improves population estimation.

## Run IEEE-CIS locally

Once you have obtained the licensed files:

```bash
blindspot-benchmark --source ieee-cis --raw-dir data/raw/ieee-cis --nrows 50000 --repetitions 2 --output artifacts/ieee-prefix-smoke
blindspot-benchmark --source ieee-cis --raw-dir data/raw/ieee-cis --repetitions 200 --output artifacts/ieee-full
BLINDSPOT_RUN_DIR=artifacts/ieee-full streamlit run apps/dashboard.py --server.address 127.0.0.1
```

The first command is only a prefix smoke test, not a full-data result. Add `--identity` to include the optional identity file. The CLI records input hashes, temporal windows, configuration, package versions and all trial results. No Kaggle credentials are read or needed by the core.

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
- No real IEEE-CIS metric is claimed until a local full-data run is recorded.
