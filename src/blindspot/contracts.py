"""Shared schema constants and fail-closed validation helpers."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable

import pandas as pd

DEFAULT_SEED = 1729

TRANSACTION_ID_COLUMN = "TransactionID"
TIME_COLUMN = "TransactionDT"
AMOUNT_COLUMN = "TransactionAmt"
TARGET_COLUMN = "isFraud"

OUTCOME_ALIASES = frozenset(
    {
        "isfraud",
        "is_fraud",
        "fraudlabel",
        "fraud_label",
        "label",
        "outcome",
        "oracle",
        "oraclelabel",
        "oracle_label",
        "target",
        "y",
        "ytrue",
        "y_true",
    }
)


class BlindSpotError(ValueError):
    """Base error for invalid BlindSpot inputs or contracts."""


class SchemaError(BlindSpotError):
    """Raised when a dataframe violates a declared schema."""


class IntegrityError(BlindSpotError):
    """Raised when a sealed or committed artifact was changed."""


def normalized_column_name(name: object) -> str:
    """Normalize a column name for conservative outcome-alias detection."""

    return "".join(
        character for character in str(name).lower() if character.isalnum() or character == "_"
    )


def outcome_columns(columns: Iterable[object]) -> set[str]:
    """Return columns whose normalized names look like outcome data."""

    return {str(column) for column in columns if normalized_column_name(column) in OUTCOME_ALIASES}


def require_columns(frame: pd.DataFrame, required: Iterable[str], *, context: str) -> None:
    """Fail with a stable error if required columns are absent."""

    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise SchemaError(f"{context} is missing required columns: {missing}")


def require_unique_non_null(frame: pd.DataFrame, column: str, *, context: str) -> None:
    """Require a non-null unique key column."""

    require_columns(frame, [column], context=context)
    if frame[column].isna().any():
        raise SchemaError(f"{context}.{column} contains null values")
    if frame[column].duplicated().any():
        raise SchemaError(f"{context}.{column} must be unique")


def require_finite_scalar(value: float, *, name: str) -> float:
    """Validate and return a finite floating-point scalar."""

    converted = float(value)
    if not math.isfinite(converted):
        raise SchemaError(f"{name} must be finite")
    return converted


def stable_row_id(transaction_id: object, *, namespace: str) -> str:
    """Derive a deterministic experiment key without exposing outcome data."""

    payload = f"{namespace}:{transaction_id}".encode()
    return hashlib.sha256(payload).hexdigest()[:24]
