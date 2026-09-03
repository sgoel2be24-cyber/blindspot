# Data provenance

Status: full local IEEE-CIS run verified on 2026-09-03; raw data is never bundled.

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

## Verified IEEE-CIS acquisition and run · 2026-09-03

The user supplied `train_transaction.csv.zip` from their Kaggle download after the CLI returned HTTP 403. Archive integrity passed; its only member is `train_transaction.csv` (683,351,067 uncompressed bytes). The archive remains in Downloads; a non-overwriting extraction placed the CSV in the ignored local raw directory. No access controls were bypassed and no credentials or signed download links were stored.

- ZIP SHA-256: `d426943b810094085d572023df5e7d52e57d67f6e40d087bd88a3ebeae0b6c4a`.
- CSV SHA-256: `3a5c83ab6b3cc13dcabe5ffa9f522307fd5f7f7b6e6f6a60c32284ca6283d642`.
- Full input: 590,540 rows, 394 columns; no duplicate IDs or missing required fields. Identity file not used; no prefix restriction in the full run.
- Full run: `e48d50631fc2ac97`, `artifacts/ieee-full-2026-09-03`; 413,378 train, 88,581 calibration, 88,581 evaluation rows; strict time separation.
- The source hash, all seven export hashes and all 3,200 registered draws were checked. Independent oracle and summary recalculations passed in `docs/IEEE_CIS_VALIDATION.ipynb`.
- Detailed measured findings and limitations: [IEEE-CIS benchmark report](docs/IEEE_CIS_BENCHMARK_2026-09-03.md).

The earlier no-data status above is historical. Dataset access does not imply redistribution permission; keep raw, selected and sealed row-level competition artifacts local. Public demo packaging and competition-license suitability still require care; no public publication occurred in this run.

## Secondary evidence simulation · 2026-09-03

Reliability run `1fbc8fe54f2bad87` derives fixed potential evidence from the existing sealed decline population solely inside the trusted offline simulator. Missingness, delay and label flips are constructed scenarios, not observed analyst behavior, chargeback timing or measured IEEE-CIS label error. All 16,000 registered trials are retained, and an independent full replay matches all five exports byte for byte. The seven original benchmark exports are unchanged.

The separate local audit interface accepts user-supplied review CSVs without reading sealed outcomes. Its real-data smoke run ingested an entirely pending template; no real analyst verification is claimed. Evidence batches, local receipts and generated stress bundles remain ignored. The dashboard's reliability files contain aggregates only; offline truth remains behind its separate presentation reveal.
