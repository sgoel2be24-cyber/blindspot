"""Local CLI to create reproducible benchmark evidence and dashboard artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from collections.abc import Callable
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from blindspot.data.ieee_cis import load_ieee_cis
from blindspot.evaluation.sweep import SweepConfig, run_budget_sweep
from blindspot.experiment.censoring import CensoringConfig, write_censored_artifacts
from blindspot.experiment.pipeline import ExperimentConfig, run_experiment
from blindspot.model.incumbent import IncumbentConfig
from blindspot.synthetic import SyntheticConfig, make_synthetic_transactions


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_json(value):
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    if isinstance(value, np.generic):
        return _safe_json(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _write_json(path: Path, value: dict) -> None:
    with path.open("x") as handle:
        json.dump(_safe_json(value), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def build_benchmark(
    frame: pd.DataFrame,
    *,
    output: str | Path,
    source: dict,
    experiment_config: ExperimentConfig | None = None,
    sweep_config: SweepConfig | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Train once, freeze the population, retain every pre-specified draw and export."""

    config = experiment_config or ExperimentConfig()
    sweep = sweep_config or SweepConfig()
    sweep.validate()
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)  # Never overwrite evidence from an earlier run.
    ordered = frame.sort_values(["TransactionDT", "TransactionID"]).reset_index(drop=True)
    frame_digest = hashlib.sha256(
        pd.util.hash_pandas_object(ordered, index=False).values.tobytes()
    ).hexdigest()
    registered = {
        "schema_version": 1,
        "source": source,
        "input_frame_sha256": frame_digest,
        "experiment_config": asdict(config),
        "sweep_config": asdict(sweep),
        "display_seed": sweep.seed_start,
        "pairing": "Common seed and row order pair independent Bernoulli draws across policies.",
        "scope": "No adaptive tuning or seed selection using held-out outcomes.",
    }
    # Register before scoring. Hashes are tamper evidence, not a security sandbox.
    _write_json(root / "registered_design.json", registered)
    if progress:
        progress("Design registered; fitting incumbent on the chronological training window")
    result = run_experiment(ordered, config)
    artifacts = result.artifacts
    write_censored_artifacts(
        artifacts,
        product_path=root / "product" / "declines.csv",
        sealed_path=root / "sealed" / "truth.csv",
    )
    comparison = run_budget_sweep(
        artifacts.product_declines, artifacts.sealed_truth, sweep, progress=progress
    )
    manifest = {
        **registered,
        "run_id": file_sha256(root / "registered_design.json")[:16],
        "rows": len(frame),
        "split": result.split.manifest(),
        "declines": len(artifacts.product_declines),
        "decline_threshold": artifacts.decline_threshold,
        "feature_columns": result.incumbent.feature_columns,
        "private_feature_columns": result.incumbent.private_feature_columns,
        "calibration_metrics": asdict(result.calibration_metrics),
        "versions": {
            "python": platform.python_version(),
            **{package: version(package) for package in ("numpy", "pandas", "scikit-learn")},
        },
        "limitations": [
            "Conditional on one frozen population; repetitions are verification draws, "
            "not retraining.",
            "Normal intervals are approximate. Empty/single-class non-census samples "
            "use the full range.",
            "Budget rates above 5% are diagnostic only for small populations.",
            "Margin-weighted sampling has no guaranteed advantage over uniform sampling.",
            "The oracle boundary and hashes are not hostile-code isolation or authentication.",
            "No production latency/noise or real merchant economics have been validated.",
        ],
    }
    _write_json(root / "manifest.json", manifest)
    _write_json(root / "public.json", {"cases": comparison.displays})
    _write_json(root / "observations.json", {"cases": comparison.observations})
    _write_json(
        root / "benchmark.json",
        {
            "oracle": {
                "block_precision": result.evaluation.oracle_block_precision,
                "false_declines": result.evaluation.oracle_false_declines,
                "false_decline_amount": result.evaluation.oracle_false_decline_amount,
            },
            "summary": comparison.summary.to_dict("records"),
            "paired_comparison": comparison.comparison.to_dict("records"),
        },
    )
    comparison.runs.to_csv(root / "runs.csv", index=False)
    comparison.summary.to_csv(root / "summary.csv", index=False)
    filenames = (
        "manifest.json",
        "public.json",
        "observations.json",
        "benchmark.json",
        "runs.csv",
        "summary.csv",
        "registered_design.json",
    )
    _write_json(root / "checksums.json", {name: file_sha256(root / name) for name in filenames})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("synthetic", "ieee-cis"), default="synthetic")
    parser.add_argument("--rows", type=int, default=50_000, help="Synthetic population size")
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--identity", action="store_true")
    parser.add_argument(
        "--nrows", type=int, help="IEEE-CIS prefix smoke test; not a full-data benchmark"
    )
    parser.add_argument("--repetitions", type=int, default=200)
    parser.add_argument(
        "--output", type=Path, required=True, help="New directory; overwrites refused"
    )
    args = parser.parse_args()
    if args.source == "synthetic":
        synthetic = SyntheticConfig(rows=args.rows)
        frame = make_synthetic_transactions(synthetic)
        source = {
            "kind": "synthetic",
            "generator": asdict(synthetic),
            "label": "Synthetic experiment — not IEEE-CIS or Razorpay results",
        }
        private = ("incumbent_private_signal",)
    else:
        if args.raw_dir is None:
            parser.error("--raw-dir is required for IEEE-CIS")
        frame = load_ieee_cis(args.raw_dir, include_identity=args.identity, nrows=args.nrows)
        source = {
            "kind": "ieee-cis",
            "label": "IEEE-CIS controlled censoring benchmark",
            "nrows": args.nrows,
            "include_identity": args.identity,
            "files": [
                {"name": Path(path).name, "sha256": file_sha256(Path(path))}
                for path in frame.attrs["blindspot_source_files"]
            ],
        }
        private = ()
    try:
        manifest = build_benchmark(
            frame,
            output=args.output,
            source=source,
            experiment_config=ExperimentConfig(
                incumbent=IncumbentConfig(private_feature_columns=private),
                censoring=CensoringConfig(private_feature_columns=private),
            ),
            sweep_config=SweepConfig(repetitions=args.repetitions),
            progress=lambda message: print(message, flush=True),
        )
    except (ValueError, FileExistsError) as error:
        parser.exit(1, f"Benchmark stopped: {error}\n")
    print(f"Run {manifest['run_id']} ready at {args.output.resolve()}")


if __name__ == "__main__":
    main()
