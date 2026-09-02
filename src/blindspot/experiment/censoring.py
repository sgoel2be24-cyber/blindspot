"""Create physically separate label-free product and sealed oracle artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from blindspot.contracts import (
    AMOUNT_COLUMN,
    TARGET_COLUMN,
    TIME_COLUMN,
    TRANSACTION_ID_COLUMN,
    SchemaError,
    outcome_columns,
    require_columns,
    require_unique_non_null,
    stable_row_id,
)

PRODUCT_COLUMNS = (
    "row_id",
    "transaction_id",
    "transaction_dt",
    "transaction_amount",
    "risk_score",
    "decline_threshold",
)
SEALED_COLUMNS = ("row_id", "is_fraud", "transaction_amount")


@dataclass(frozen=True)
class CensoringConfig:
    target_column: str = TARGET_COLUMN
    id_column: str = TRANSACTION_ID_COLUMN
    time_column: str = TIME_COLUMN
    amount_column: str = AMOUNT_COLUMN
    private_feature_columns: tuple[str, ...] = ()
    row_id_namespace: str = "blindspot-v1"


@dataclass(frozen=True)
class CensoredArtifacts:
    """Trusted harness output. Pass only ``product_declines`` into product code."""

    product_declines: pd.DataFrame
    sealed_truth: pd.DataFrame
    decline_threshold: float
    evaluation_population_size: int


def _validate_binary_target(series: pd.Series, *, column: str) -> None:
    values = set(series.dropna().unique().tolist())
    if series.isna().any() or not values.issubset({0, 1}):
        raise SchemaError(f"{column} must contain only binary 0/1 values")


def create_censored_artifacts(
    evaluation: pd.DataFrame,
    scores: np.ndarray,
    *,
    threshold: float,
    config: CensoringConfig | None = None,
) -> CensoredArtifacts:
    """Apply the incumbent gate and separate product-visible rows from oracle outcomes."""

    config = config or CensoringConfig()
    required = [
        config.target_column,
        config.id_column,
        config.time_column,
        config.amount_column,
        *config.private_feature_columns,
    ]
    require_columns(evaluation, required, context="censoring input")
    require_unique_non_null(evaluation, config.id_column, context="censoring input")
    _validate_binary_target(evaluation[config.target_column], column=config.target_column)

    probabilities = np.asarray(scores, dtype=np.float64)
    if probabilities.ndim != 1 or len(probabilities) != len(evaluation):
        raise SchemaError("censoring scores must align one-to-one with evaluation rows")
    if not np.isfinite(probabilities).all():
        raise SchemaError("censoring scores must be finite")
    threshold = float(threshold)
    if not np.isfinite(threshold):
        raise SchemaError("decline threshold must be finite")

    declined_mask = probabilities >= threshold
    if not declined_mask.any():
        raise SchemaError("the frozen threshold produced an empty declined population")

    declined = evaluation.loc[declined_mask].copy().reset_index(drop=True)
    declined_scores = probabilities[declined_mask]
    row_ids = [
        stable_row_id(value, namespace=config.row_id_namespace)
        for value in declined[config.id_column]
    ]
    if len(row_ids) != len(set(row_ids)):
        raise SchemaError("derived row_id collision detected")

    product = pd.DataFrame(
        {
            "row_id": row_ids,
            "transaction_id": declined[config.id_column].to_numpy(copy=True),
            "transaction_dt": declined[config.time_column].to_numpy(copy=True),
            "transaction_amount": declined[config.amount_column].to_numpy(copy=True),
            "risk_score": declined_scores,
            "decline_threshold": np.full(len(declined), threshold, dtype=np.float64),
        }
    )
    forbidden = outcome_columns(product.columns)
    private_overlap = set(product.columns).intersection(config.private_feature_columns)
    if forbidden or private_overlap:
        raise SchemaError(
            f"product artifact contains forbidden fields: {sorted(forbidden | private_overlap)}"
        )

    sealed = pd.DataFrame(
        {
            "row_id": row_ids,
            "is_fraud": declined[config.target_column].astype(np.int8).to_numpy(copy=True),
            "transaction_amount": declined[config.amount_column].to_numpy(copy=True),
        }
    )
    return CensoredArtifacts(
        product_declines=product.loc[:, PRODUCT_COLUMNS].copy(),
        sealed_truth=sealed.loc[:, SEALED_COLUMNS].copy(),
        decline_threshold=threshold,
        evaluation_population_size=len(evaluation),
    )


def write_censored_artifacts(
    artifacts: CensoredArtifacts,
    *,
    product_path: str | Path,
    sealed_path: str | Path,
) -> tuple[Path, Path]:
    """Write product and oracle CSVs to explicitly different paths."""

    product_file = Path(product_path).expanduser().resolve()
    sealed_file = Path(sealed_path).expanduser().resolve()
    if product_file == sealed_file:
        raise SchemaError("product and sealed artifacts must use different paths")
    product_file.parent.mkdir(parents=True, exist_ok=True)
    sealed_file.parent.mkdir(parents=True, exist_ok=True)
    artifacts.product_declines.to_csv(product_file, index=False)
    artifacts.sealed_truth.to_csv(sealed_file, index=False)
    return product_file, sealed_file
