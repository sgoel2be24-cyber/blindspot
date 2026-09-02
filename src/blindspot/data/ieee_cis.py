"""Local-only loader for the labeled IEEE-CIS competition files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from blindspot.contracts import (
    AMOUNT_COLUMN,
    TARGET_COLUMN,
    TIME_COLUMN,
    TRANSACTION_ID_COLUMN,
    SchemaError,
    require_columns,
    require_unique_non_null,
)

TRANSACTION_FILENAME = "train_transaction.csv"
IDENTITY_FILENAME = "train_identity.csv"
REQUIRED_TRANSACTION_COLUMNS = (
    TRANSACTION_ID_COLUMN,
    TIME_COLUMN,
    AMOUNT_COLUMN,
    TARGET_COLUMN,
)


def _validate_transaction_frame(frame: pd.DataFrame) -> None:
    require_columns(frame, REQUIRED_TRANSACTION_COLUMNS, context="IEEE-CIS transaction data")
    require_unique_non_null(
        frame,
        TRANSACTION_ID_COLUMN,
        context="IEEE-CIS transaction data",
    )

    if frame[TIME_COLUMN].isna().any():
        raise SchemaError(f"IEEE-CIS transaction data.{TIME_COLUMN} contains null values")
    if not pd.api.types.is_numeric_dtype(frame[TIME_COLUMN]):
        raise SchemaError(f"IEEE-CIS transaction data.{TIME_COLUMN} must be numeric")

    if frame[AMOUNT_COLUMN].isna().any():
        raise SchemaError(f"IEEE-CIS transaction data.{AMOUNT_COLUMN} contains null values")
    if not pd.api.types.is_numeric_dtype(frame[AMOUNT_COLUMN]):
        raise SchemaError(f"IEEE-CIS transaction data.{AMOUNT_COLUMN} must be numeric")
    if (frame[AMOUNT_COLUMN] < 0).any():
        raise SchemaError(f"IEEE-CIS transaction data.{AMOUNT_COLUMN} must be non-negative")

    target_values = set(frame[TARGET_COLUMN].dropna().unique().tolist())
    if frame[TARGET_COLUMN].isna().any() or not target_values.issubset({0, 1}):
        raise SchemaError(
            f"IEEE-CIS transaction data.{TARGET_COLUMN} must contain only binary 0/1 values"
        )


def load_ieee_cis(
    raw_dir: str | Path,
    *,
    include_identity: bool = True,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Load labeled IEEE-CIS training rows from a user-supplied local directory.

    The function never downloads data. ``nrows`` exists only for smoke tests and local
    iteration; final run manifests must record when it is used.
    """

    directory = Path(raw_dir).expanduser().resolve()
    transaction_path = directory / TRANSACTION_FILENAME
    if not transaction_path.is_file():
        raise FileNotFoundError(
            f"Missing {TRANSACTION_FILENAME} in {directory}. "
            "See DATA_PROVENANCE.md for the accepted local layout."
        )
    if nrows is not None and nrows <= 0:
        raise SchemaError("nrows must be positive when provided")

    transaction = pd.read_csv(transaction_path, nrows=nrows, low_memory=False)
    _validate_transaction_frame(transaction)

    source_files = [str(transaction_path)]
    if include_identity:
        identity_path = directory / IDENTITY_FILENAME
        if not identity_path.is_file():
            raise FileNotFoundError(
                f"include_identity=True but {IDENTITY_FILENAME} is missing in {directory}"
            )
        identity = pd.read_csv(identity_path, low_memory=False)
        require_unique_non_null(identity, TRANSACTION_ID_COLUMN, context="IEEE-CIS identity data")
        transaction = transaction.merge(
            identity,
            how="left",
            on=TRANSACTION_ID_COLUMN,
            validate="one_to_one",
            sort=False,
        )
        source_files.append(str(identity_path))

    transaction.attrs["blindspot_source_files"] = tuple(source_files)
    transaction.attrs["blindspot_nrows_requested"] = nrows
    return transaction
