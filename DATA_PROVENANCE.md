# Data provenance

Status: source path defined; raw IEEE-CIS data is not bundled.

## Source

BlindSpot uses the official [IEEE-CIS Fraud Detection competition data](https://www.kaggle.com/c/ieee-fraud-detection/data), published on Kaggle by IEEE Computational Intelligence Society in collaboration with Vesta Corporation.

The competition states that:

- fraud is the binary target `isFraud`
- transaction and identity files join on `TransactionID`
- not every transaction has identity information
- `TransactionDT` is a relative time delta, not a calendar timestamp
- use of the files is subject to the competition rules

The project does not redistribute those files or bypass Kaggle access controls.

## Expected local layout

```text
data/raw/ieee-cis/
├── train_transaction.csv   # required
└── train_identity.csv      # optional
```

The unlabeled Kaggle test files are not used for the sealed evaluation.

After accepting the competition rules, a user may download the files manually or with the Kaggle CLI. The core code only accepts a local directory; it does not require a Kaggle credential at runtime.

## Source recording

Before a full run, record local hashes without committing the data:

```bash
shasum -a 256 data/raw/ieee-cis/train_transaction.csv
shasum -a 256 data/raw/ieee-cis/train_identity.csv
```

The run manifest must also record row/column counts, load options, package versions, and split time bounds.

## Known limitations

1. IEEE-CIS is a historical competition dataset and is not asserted to match Razorpay traffic, fraud prevalence, currencies, or current production features.
2. The labeled rows were already observed by the source system. Transactions rejected before entering that dataset may be absent.
3. BlindSpot applies a second, controlled censoring gate. The benchmark validates estimation under known experimental censoring, not a real merchant's absolute false-decline rate.
4. `TransactionAmt` is reported in unspecified dataset currency units. Core outputs use `CU`, not `₹`.
5. Offline `isFraud` is a sealed benchmark oracle. Production verification evidence may be delayed, incomplete, or noisy.

## Raw-data handling

- `data/raw/**` is gitignored.
- No tests require raw IEEE-CIS files.
- Synthetic fixtures mirror only the minimum schema and contain no copied competition rows.
- Sealed truth artifacts are also gitignored because they are outcome-bearing evaluation material.

## Verified run · 2026-09-02

No IEEE-CIS raw files were found in the project or the checked Downloads location. No real-data metric is claimed.

The implemented `blindspot-benchmark` command accepts the local IEEE-CIS directory, hashes each input file, records load options, the processed input-frame digest, row count, feature list, split bounds, seeds and package versions, and writes a fresh artifact directory. `--nrows` is explicitly a file-prefix smoke test; omit it for full-data evidence.

The current dashboard bundle `artifacts/synthetic-2026-09-02/` contains 50,000 generated transactions (generator seed 1729), a 35,000/7,500/7,500 temporal split, and 353 evaluation declines. Its run identifier is `11a911eb5d6b31ad`. These figures describe the synthetic fixture only. The source configuration is preserved in the manifest; the complete measured comparison is documented in `docs/SYNTHETIC_BENCHMARK_2026-09-02.md`.

`observations.json` contains only outcomes for the pre-registered displayed verification samples. `public.json` contains their queues and estimated aggregates; `benchmark.json` contains explicitly offline oracle aggregates. The selection package never reads any of these outcome-bearing exports. All are gitignored and should not be uploaded as raw or row-level competition evidence.
