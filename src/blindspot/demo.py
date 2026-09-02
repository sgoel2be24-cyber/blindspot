"""Command-line synthetic proof of the complete no-key BlindSpot flow."""

from __future__ import annotations

import json
from dataclasses import asdict

from blindspot.experiment.censoring import CensoringConfig
from blindspot.experiment.pipeline import ExperimentConfig, run_experiment
from blindspot.model.incumbent import IncumbentConfig
from blindspot.synthetic import make_synthetic_transactions


def main() -> None:
    """Run a deterministic synthetic experiment and print only aggregate evidence."""

    frame = make_synthetic_transactions()
    private_features = ("incumbent_private_signal",)
    result = run_experiment(
        frame,
        ExperimentConfig(
            incumbent=IncumbentConfig(
                max_features=6,
                max_iter=50,
                min_samples_leaf=10,
                private_feature_columns=private_features,
            ),
            censoring=CensoringConfig(private_feature_columns=private_features),
            target_decline_rate=0.25,
            expected_budget_rate=0.75,
        ),
    )
    report = result.evaluation
    output = {
        "data": {
            "rows": len(frame),
            "split": result.split.manifest(),
            "declines": report.population_size,
        },
        "incumbent_calibration": asdict(result.calibration_metrics),
        "verification": {
            "policy": report.policy,
            "expected_budget": report.expected_budget,
            "realized": report.realized_verifications,
            "commitment": report.plan_commitment,
        },
        "estimate": {
            "block_precision": report.estimate.block_precision,
            "block_precision_ci": report.estimate.block_precision_ci,
            "oracle_block_precision": report.oracle_block_precision,
            "absolute_error_pp": report.absolute_block_precision_error_pp,
            "ci_covers_oracle": report.ci_covers_oracle,
            "stable": report.estimate.stable,
            "warnings": report.estimate.warnings,
        },
        "discovery": {
            "precision": report.discovery_precision,
            "recall_offline_only": report.discovery_recall,
        },
        "economics": asdict(result.economics),
        "scope": "synthetic smoke test; not an IEEE-CIS or Razorpay performance claim",
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
