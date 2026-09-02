"""Deterministic synthetic transactions for the no-data/no-key smoke path."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from blindspot.contracts import DEFAULT_SEED


@dataclass(frozen=True)
class SyntheticConfig:
    rows: int = 1_200
    seed: int = DEFAULT_SEED


def make_synthetic_transactions(config: SyntheticConfig | None = None) -> pd.DataFrame:
    """Generate a small labeled table with time drift and an incumbent-private signal."""

    config = config or SyntheticConfig()
    if config.rows < 120:
        raise ValueError("synthetic flow requires at least 120 rows")
    generator = np.random.Generator(np.random.PCG64(config.seed))
    rows = config.rows

    transaction_dt = np.repeat(np.arange((rows + 1) // 2), 2)[:rows]
    amount = generator.lognormal(mean=3.2, sigma=0.7, size=rows)
    velocity = generator.normal(size=rows)
    device_risk = generator.normal(size=rows)
    customer_age = generator.exponential(scale=40.0, size=rows)
    private_signal = generator.normal(size=rows)
    time_drift = (transaction_dt / max(float(transaction_dt.max()), 1.0)) - 0.5

    logit = (
        -1.8
        + 0.75 * velocity
        + 0.55 * device_risk
        - 0.012 * customer_age
        + 0.85 * private_signal
        + 0.5 * time_drift
        + 0.002 * amount
    )
    fraud_probability = 1.0 / (1.0 + np.exp(-logit))
    is_fraud = generator.binomial(1, fraud_probability)

    return pd.DataFrame(
        {
            "TransactionID": np.arange(10_000_000, 10_000_000 + rows),
            "TransactionDT": transaction_dt,
            "TransactionAmt": amount,
            "velocity_24h": velocity,
            "device_risk": device_risk,
            "customer_age_days": customer_age,
            "incumbent_private_signal": private_signal,
            "ProductCD": generator.choice(["C", "H", "R", "S", "W"], size=rows),
            "isFraud": is_fraud,
        }
    )
