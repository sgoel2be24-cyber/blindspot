from __future__ import annotations

from blindspot.economics import EconomicConfig
from blindspot.experiment.censoring import CensoringConfig
from blindspot.experiment.pipeline import ExperimentConfig, run_experiment
from blindspot.model.incumbent import IncumbentConfig


def test_full_synthetic_flow_needs_no_data_file_or_api_key(synthetic_transactions):
    private = ("incumbent_private_signal",)
    result = run_experiment(
        synthetic_transactions,
        ExperimentConfig(
            incumbent=IncumbentConfig(
                max_features=6,
                max_iter=35,
                min_samples_leaf=8,
                private_feature_columns=private,
            ),
            censoring=CensoringConfig(private_feature_columns=private),
            economics=EconomicConfig(verification_cost_per_case=2.0),
            target_decline_rate=0.25,
            expected_budget_rate=0.60,
            sampling_seed=88,
        ),
    )

    report = result.evaluation
    assert report.population_size == len(result.artifacts.product_declines)
    assert set(result.artifacts.product_declines.columns) == {
        "row_id",
        "transaction_id",
        "transaction_dt",
        "transaction_amount",
        "risk_score",
        "decline_threshold",
    }
    assert "isFraud" not in result.artifacts.product_declines
    assert "incumbent_private_signal" not in result.artifacts.product_declines
    assert 0 <= report.estimate.block_precision <= 1
    assert 0 <= report.oracle_block_precision <= 1
    assert report.discovery_precision is None or 0 <= report.discovery_precision <= 1
    assert report.discovery_recall is None or 0 <= report.discovery_recall <= 1
    assert result.economics.currency_unit == "CU"
    assert result.economics.verification_program_cost == report.realized_verifications * 2.0
