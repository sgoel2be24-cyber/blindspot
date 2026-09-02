"""Product-visible dataframe and verification-plan contracts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from blindspot.contracts import (
    SchemaError,
    outcome_columns,
    require_columns,
    require_unique_non_null,
)

DECLINE_POOL_COLUMNS = (
    "row_id",
    "transaction_id",
    "transaction_dt",
    "transaction_amount",
    "risk_score",
    "decline_threshold",
)
PLAN_COLUMNS = (
    "row_id",
    "propensity",
    "priority",
    "selected",
    "policy",
    "expected_budget",
    "seed",
)


@dataclass
class VerificationPlan:
    """A complete, pre-outcome randomized plan over the declined population."""

    ledger: pd.DataFrame
    policy: str
    expected_budget: float
    seed: int
    commitment: str

    def __post_init__(self) -> None:
        self.ledger = self.ledger.copy(deep=True)

    @property
    def population_size(self) -> int:
        return len(self.ledger)

    @property
    def selected_count(self) -> int:
        return int(self.ledger["selected"].sum())


def validate_decline_pool(
    frame: pd.DataFrame,
    *,
    private_feature_columns: tuple[str, ...] = (),
) -> None:
    """Fail closed when product-visible data contains labels or invalid decline rows."""

    require_columns(frame, DECLINE_POOL_COLUMNS, context="product decline pool")
    require_unique_non_null(frame, "row_id", context="product decline pool")

    forbidden = outcome_columns(frame.columns)
    private_overlap = set(frame.columns).intersection(private_feature_columns)
    if forbidden or private_overlap:
        raise SchemaError(
            f"product decline pool contains forbidden fields: {sorted(forbidden | private_overlap)}"
        )

    for column in ("transaction_amount", "risk_score", "decline_threshold"):
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=np.float64)
        if not np.isfinite(values).all():
            raise SchemaError(f"product decline pool.{column} must be finite numeric data")
    if (frame["transaction_amount"] < 0).any():
        raise SchemaError("product decline pool.transaction_amount must be non-negative")
    if (frame["risk_score"] < frame["decline_threshold"]).any():
        raise SchemaError("product decline pool contains a row below the frozen threshold")
