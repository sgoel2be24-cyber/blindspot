from __future__ import annotations

import numpy as np
import pandas as pd

from blindspot.product.verification import (
    create_verification_plan,
    propensities_from_weights,
)


def _decline_pool(rows: int = 100) -> pd.DataFrame:
    scores = np.linspace(0.7, 0.99, rows)
    return pd.DataFrame(
        {
            "row_id": [f"row-{index:04d}" for index in range(rows)],
            "transaction_id": np.arange(rows),
            "transaction_dt": np.arange(rows),
            "transaction_amount": np.linspace(1, 200, rows),
            "risk_score": scores,
            "decline_threshold": np.full(rows, 0.7),
        }
    )


def test_water_filling_preserves_positive_support_and_budget():
    weights = np.array([0.1, 0.2, 1.0, 10.0])
    propensities = propensities_from_weights(weights, expected_budget=2.5)

    assert np.all(propensities > 0)
    assert np.all(propensities <= 1)
    assert np.isclose(propensities.sum(), 2.5)
    assert np.any(np.isclose(propensities, 1.0))


def test_plan_is_deterministic_and_input_order_invariant():
    pool = _decline_pool()
    first = create_verification_plan(
        pool,
        policy="margin_weighted",
        expected_budget=20,
        seed=44,
    )
    replay = create_verification_plan(
        pool.sample(frac=1, random_state=2),
        policy="margin_weighted",
        expected_budget=20,
        seed=44,
    )
    changed_seed = create_verification_plan(
        pool,
        policy="margin_weighted",
        expected_budget=20,
        seed=45,
    )

    assert first.commitment == replay.commitment
    assert np.allclose(first.ledger["propensity"], changed_seed.ledger["propensity"])
    assert not first.ledger["selected"].equals(changed_seed.ledger["selected"])
    assert first.commitment != changed_seed.commitment


def test_uniform_policy_has_equal_propensities():
    plan = create_verification_plan(
        _decline_pool(50),
        policy="uniform",
        expected_budget=5,
        seed=12,
    )
    assert np.allclose(plan.ledger["propensity"], 0.1)
