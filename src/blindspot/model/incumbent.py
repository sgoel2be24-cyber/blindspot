"""A deterministic, deliberately modest fraud-scoring incumbent."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score

from blindspot.contracts import (
    DEFAULT_SEED,
    TARGET_COLUMN,
    TIME_COLUMN,
    TRANSACTION_ID_COLUMN,
    SchemaError,
    require_columns,
)


@dataclass(frozen=True)
class IncumbentConfig:
    target_column: str = TARGET_COLUMN
    id_column: str = TRANSACTION_ID_COLUMN
    time_column: str = TIME_COLUMN
    max_features: int = 64
    max_iter: int = 80
    learning_rate: float = 0.08
    max_leaf_nodes: int = 31
    min_samples_leaf: int = 20
    l2_regularization: float = 1.0
    random_state: int = DEFAULT_SEED
    private_feature_columns: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.max_features <= 0:
            raise SchemaError("max_features must be positive")
        if len(self.private_feature_columns) > self.max_features:
            raise SchemaError("private feature count cannot exceed max_features")
        protected = {self.target_column, self.id_column, self.time_column}
        overlap = protected.intersection(self.private_feature_columns)
        if overlap:
            raise SchemaError(
                f"protected columns cannot be private model features: {sorted(overlap)}"
            )


@dataclass(frozen=True)
class BaselineMetrics:
    average_precision: float
    roc_auc: float
    precision: float
    recall: float
    decline_rate: float
    threshold: float


@dataclass
class IncumbentModel:
    """Fitted model plus its frozen ordered feature contract."""

    estimator: HistGradientBoostingClassifier
    feature_columns: tuple[str, ...]
    private_feature_columns: tuple[str, ...]
    config: IncumbentConfig

    def predict_fraud_probability(self, frame: pd.DataFrame) -> np.ndarray:
        require_columns(frame, self.feature_columns, context="incumbent scoring input")
        matrix = _numeric_matrix(frame, self.feature_columns)
        probabilities = self.estimator.predict_proba(matrix)[:, 1]
        if not np.isfinite(probabilities).all():
            raise SchemaError("incumbent produced non-finite probabilities")
        return probabilities.astype(np.float64, copy=False)


def _numeric_matrix(frame: pd.DataFrame, columns: tuple[str, ...]) -> np.ndarray:
    converted = frame.loc[:, columns].apply(pd.to_numeric, errors="coerce")
    return converted.to_numpy(dtype=np.float32, copy=True)


def _select_numeric_features(frame: pd.DataFrame, config: IncumbentConfig) -> tuple[str, ...]:
    config.validate()
    require_columns(frame, [config.target_column], context="incumbent training input")
    require_columns(frame, config.private_feature_columns, context="incumbent training input")

    protected = {config.target_column, config.id_column, config.time_column}
    private = set(config.private_feature_columns)
    candidates = [
        column
        for column in frame.columns
        if column not in protected
        and column not in private
        and pd.api.types.is_numeric_dtype(frame[column])
    ]
    ranked = sorted(candidates, key=lambda column: (-float(frame[column].notna().mean()), column))
    public_limit = config.max_features - len(config.private_feature_columns)
    selected_public = ranked[:public_limit]

    for column in config.private_feature_columns:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            raise SchemaError(f"private incumbent feature must be numeric: {column}")

    selected = tuple(selected_public) + tuple(sorted(config.private_feature_columns))
    if not selected:
        raise SchemaError("incumbent training input has no eligible numeric features")
    return selected


def _balanced_sample_weight(target: np.ndarray) -> np.ndarray:
    class_counts = np.bincount(target, minlength=2)
    if len(class_counts) != 2 or (class_counts == 0).any():
        raise SchemaError("incumbent training target must contain both classes")
    total = len(target)
    class_weight = total / (2.0 * class_counts)
    return class_weight[target].astype(np.float64)


def fit_incumbent(
    train: pd.DataFrame,
    config: IncumbentConfig | None = None,
) -> IncumbentModel:
    """Fit the frozen numeric HistGradientBoosting baseline on train rows only."""

    config = config or IncumbentConfig()
    features = _select_numeric_features(train, config)
    target = train[config.target_column].to_numpy(dtype=np.int8, copy=True)
    if not set(np.unique(target)).issubset({0, 1}):
        raise SchemaError("incumbent training target must be binary 0/1")

    estimator = HistGradientBoostingClassifier(
        learning_rate=config.learning_rate,
        max_iter=config.max_iter,
        max_leaf_nodes=config.max_leaf_nodes,
        min_samples_leaf=config.min_samples_leaf,
        l2_regularization=config.l2_regularization,
        early_stopping=False,
        random_state=config.random_state,
    )
    estimator.fit(
        _numeric_matrix(train, features),
        target,
        sample_weight=_balanced_sample_weight(target),
    )
    return IncumbentModel(
        estimator=estimator,
        feature_columns=features,
        private_feature_columns=tuple(sorted(config.private_feature_columns)),
        config=config,
    )


def choose_decline_threshold(scores: np.ndarray, *, target_decline_rate: float = 0.05) -> float:
    """Freeze a score threshold from calibration scores and an operational decline rate."""

    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise SchemaError("calibration scores must be a non-empty finite one-dimensional array")
    if not 0 < target_decline_rate < 1:
        raise SchemaError("target_decline_rate must be in (0, 1)")
    return float(np.quantile(values, 1.0 - target_decline_rate, method="higher"))


def evaluate_incumbent(
    target: np.ndarray,
    scores: np.ndarray,
    *,
    threshold: float,
) -> BaselineMetrics:
    """Calculate held-out baseline metrics without changing the frozen threshold."""

    y_true = np.asarray(target, dtype=np.int8)
    probabilities = np.asarray(scores, dtype=np.float64)
    if y_true.shape != probabilities.shape or y_true.ndim != 1:
        raise SchemaError("target and scores must be aligned one-dimensional arrays")
    if not set(np.unique(y_true)).issubset({0, 1}) or len(np.unique(y_true)) < 2:
        raise SchemaError("baseline metrics require both binary target classes")
    if not np.isfinite(probabilities).all():
        raise SchemaError("baseline scores must be finite")

    declined = probabilities >= float(threshold)
    return BaselineMetrics(
        average_precision=float(average_precision_score(y_true, probabilities)),
        roc_auc=float(roc_auc_score(y_true, probabilities)),
        precision=float(precision_score(y_true, declined, zero_division=0)),
        recall=float(recall_score(y_true, declined, zero_division=0)),
        decline_rate=float(declined.mean()),
        threshold=float(threshold),
    )
