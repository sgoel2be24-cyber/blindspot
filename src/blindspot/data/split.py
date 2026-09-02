"""Stable, tie-safe chronological dataset splitting."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from blindspot.contracts import (
    TIME_COLUMN,
    TRANSACTION_ID_COLUMN,
    SchemaError,
    require_columns,
    require_unique_non_null,
)


@dataclass(frozen=True)
class TemporalSplitConfig:
    """Configuration for the frozen three-way chronological split."""

    train_fraction: float = 0.70
    calibration_fraction: float = 0.15
    time_column: str = TIME_COLUMN
    id_column: str = TRANSACTION_ID_COLUMN

    @property
    def evaluation_fraction(self) -> float:
        return 1.0 - self.train_fraction - self.calibration_fraction

    def validate(self) -> None:
        fractions = (
            self.train_fraction,
            self.calibration_fraction,
            self.evaluation_fraction,
        )
        if any(fraction <= 0 or fraction >= 1 for fraction in fractions):
            raise SchemaError("train, calibration, and evaluation fractions must all be in (0, 1)")


@dataclass(frozen=True)
class TemporalSplit:
    """Chronologically isolated train, calibration, and evaluation frames."""

    train: pd.DataFrame
    calibration: pd.DataFrame
    evaluation: pd.DataFrame
    config: TemporalSplitConfig

    def manifest(self) -> dict[str, object]:
        time_column = self.config.time_column

        def json_scalar(value: object) -> object:
            return value.item() if isinstance(value, np.generic) else value

        return {
            "row_counts": {
                "train": len(self.train),
                "calibration": len(self.calibration),
                "evaluation": len(self.evaluation),
            },
            "time_bounds": {
                "train": [
                    json_scalar(self.train[time_column].min()),
                    json_scalar(self.train[time_column].max()),
                ],
                "calibration": [
                    json_scalar(self.calibration[time_column].min()),
                    json_scalar(self.calibration[time_column].max()),
                ],
                "evaluation": [
                    json_scalar(self.evaluation[time_column].min()),
                    json_scalar(self.evaluation[time_column].max()),
                ],
            },
        }


def _right_edge_of_time_group(times: np.ndarray, target_count: int) -> int:
    """Move a desired row cut to the right edge of its complete time group."""

    target_count = min(max(target_count, 1), len(times) - 1)
    boundary_value = times[target_count - 1]
    return int(np.searchsorted(times, boundary_value, side="right"))


def temporal_split(
    frame: pd.DataFrame,
    config: TemporalSplitConfig | None = None,
) -> TemporalSplit:
    """Return a deterministic 70/15/15-style split without splitting time ties."""

    config = config or TemporalSplitConfig()
    config.validate()
    require_columns(frame, [config.time_column, config.id_column], context="temporal split input")
    require_unique_non_null(frame, config.id_column, context="temporal split input")
    if frame[config.time_column].isna().any():
        raise SchemaError(f"temporal split input.{config.time_column} contains null values")

    ordered = frame.sort_values(
        [config.time_column, config.id_column],
        kind="mergesort",
    ).reset_index(drop=True)
    if len(ordered) < 3 or ordered[config.time_column].nunique() < 3:
        raise SchemaError("temporal split requires at least three distinct time groups")

    times = ordered[config.time_column].to_numpy()
    train_target = int(np.floor(len(ordered) * config.train_fraction))
    calibration_target = int(
        np.floor(len(ordered) * (config.train_fraction + config.calibration_fraction))
    )
    train_end = _right_edge_of_time_group(times, train_target)
    calibration_end = _right_edge_of_time_group(times, calibration_target)

    if calibration_end <= train_end:
        calibration_end = int(np.searchsorted(times, times[train_end], side="right"))
    if train_end <= 0 or calibration_end <= train_end or calibration_end >= len(ordered):
        raise SchemaError(
            "time-group boundaries cannot produce three non-empty strictly ordered splits"
        )

    train = ordered.iloc[:train_end].reset_index(drop=True)
    calibration = ordered.iloc[train_end:calibration_end].reset_index(drop=True)
    evaluation = ordered.iloc[calibration_end:].reset_index(drop=True)

    if not (
        train[config.time_column].max() < calibration[config.time_column].min()
        and calibration[config.time_column].max() < evaluation[config.time_column].min()
    ):
        raise SchemaError("temporal split failed strict time isolation")

    return TemporalSplit(
        train=train,
        calibration=calibration,
        evaluation=evaluation,
        config=config,
    )
