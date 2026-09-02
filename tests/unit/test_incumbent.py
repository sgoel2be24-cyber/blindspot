from __future__ import annotations

import numpy as np

from blindspot.data.split import temporal_split
from blindspot.model.incumbent import (
    IncumbentConfig,
    choose_decline_threshold,
    evaluate_incumbent,
    fit_incumbent,
)


def test_incumbent_is_deterministic_and_excludes_protected_columns(synthetic_transactions):
    split = temporal_split(synthetic_transactions)
    config = IncumbentConfig(
        max_features=6,
        max_iter=30,
        min_samples_leaf=8,
        private_feature_columns=("incumbent_private_signal",),
    )

    first = fit_incumbent(split.train, config)
    second = fit_incumbent(split.train, config)
    first_scores = first.predict_fraud_probability(split.calibration)
    second_scores = second.predict_fraud_probability(split.calibration)

    assert np.allclose(first_scores, second_scores, rtol=0, atol=1e-12)
    assert {"isFraud", "TransactionID", "TransactionDT"}.isdisjoint(first.feature_columns)
    assert "incumbent_private_signal" in first.feature_columns

    threshold = choose_decline_threshold(first_scores, target_decline_rate=0.20)
    metrics = evaluate_incumbent(
        split.calibration["isFraud"].to_numpy(),
        first_scores,
        threshold=threshold,
    )
    assert 0 <= metrics.average_precision <= 1
    assert 0 <= metrics.precision <= 1
    assert 0 < metrics.decline_rate < 1
