"""Design-based Horvitz-Thompson and Hájek estimation."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from blindspot.contracts import SchemaError


@dataclass(frozen=True)
class HTTotalEstimate:
    point: float
    standard_error: float
    ci_lower: float | None
    ci_upper: float | None


@dataclass(frozen=True)
class HTBinaryEstimate:
    false_decline_total: float
    false_decline_share: float
    block_precision: float
    standard_error_share: float
    false_decline_ci: tuple[float, float]
    block_precision_ci: tuple[float, float]
    false_decline_total_ci: tuple[float, float]
    hajek_false_decline_share: float | None
    effective_sample_size: float
    realized_sample_size: int
    verified_legitimate: int
    stable: bool
    warnings: tuple[str, ...]
    interval_method: str


def _validate_design_inputs(
    values: np.ndarray, propensities: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    observed = np.asarray(values, dtype=np.float64)
    probabilities = np.asarray(propensities, dtype=np.float64)
    if observed.ndim != 1 or probabilities.ndim != 1 or observed.shape != probabilities.shape:
        raise SchemaError("observed values and propensities must be aligned 1D arrays")
    if not np.isfinite(observed).all():
        raise SchemaError("observed values must be finite")
    if (
        not np.isfinite(probabilities).all()
        or (probabilities <= 0).any()
        or (probabilities > 1).any()
    ):
        raise SchemaError("sampled propensities must be finite and in (0, 1]")
    return observed, probabilities


def _z_value(confidence_level: float) -> float:
    if not 0 < confidence_level < 1:
        raise SchemaError("confidence_level must be in (0, 1)")
    return float(NormalDist().inv_cdf(0.5 + confidence_level / 2.0))


def horvitz_thompson_total(
    observed_values: np.ndarray,
    propensities: np.ndarray,
    *,
    confidence_level: float = 0.95,
    lower_bound: float | None = 0.0,
    upper_bound: float | None = None,
) -> HTTotalEstimate:
    """Estimate a finite-population total from independently sampled units."""

    values, probabilities = _validate_design_inputs(observed_values, propensities)
    _z_value(confidence_level)
    if not len(values):
        return HTTotalEstimate(0.0, 0.0, lower_bound, upper_bound)
    point = float(np.sum(values / probabilities)) if len(values) else 0.0
    variance = (
        float(np.sum((1.0 - probabilities) * np.square(values) / np.square(probabilities)))
        if len(values)
        else 0.0
    )
    standard_error = float(np.sqrt(max(variance, 0.0)))
    radius = _z_value(confidence_level) * standard_error
    lower = point - radius
    upper = point + radius
    if lower_bound is not None:
        lower = max(float(lower_bound), lower)
        upper = max(float(lower_bound), upper)
    if upper_bound is not None:
        lower = min(float(upper_bound), lower)
        upper = min(float(upper_bound), upper)
    return HTTotalEstimate(
        point=point,
        standard_error=standard_error,
        ci_lower=float(lower),
        ci_upper=float(upper),
    )


def estimate_false_decline_share(
    observed_is_fraud: np.ndarray,
    propensities: np.ndarray,
    *,
    population_size: int,
    confidence_level: float = 0.95,
) -> HTBinaryEstimate:
    """Estimate false-decline share and block precision in the declined population."""

    outcomes, probabilities = _validate_design_inputs(observed_is_fraud, propensities)
    if population_size <= 0:
        raise SchemaError("population_size must be positive")
    if len(outcomes) > population_size:
        raise SchemaError("sample size cannot exceed population size")
    if not set(np.unique(outcomes)).issubset({0.0, 1.0}):
        raise SchemaError("observed fraud outcomes must be binary 0/1")

    legitimate = 1.0 - outcomes
    total = horvitz_thompson_total(
        legitimate,
        probabilities,
        confidence_level=confidence_level,
        lower_bound=0.0,
        upper_bound=float(population_size),
    )
    # Do not clip the point estimate: clipping would remove the Horvitz-Thompson
    # estimator's design-unbiasedness. Boundary excursions are instead flagged.
    share = float(total.point / population_size)
    share_se = total.standard_error / population_size
    z_value = _z_value(confidence_level)
    share_lower = float(np.clip(share - z_value * share_se, 0.0, 1.0))
    share_upper = float(np.clip(share + z_value * share_se, 0.0, 1.0))

    inverse_weights = 1.0 / probabilities if len(probabilities) else np.array([])
    effective_sample_size = (
        float(np.square(inverse_weights.sum()) / np.square(inverse_weights).sum())
        if len(inverse_weights)
        else 0.0
    )
    hajek_denominator = float(inverse_weights.sum()) if len(inverse_weights) else 0.0
    hajek = (
        float(np.sum(legitimate / probabilities) / hajek_denominator)
        if hajek_denominator > 0
        else None
    )

    verified_legitimate = int(legitimate.sum())
    census = len(outcomes) == population_size and bool(np.all(probabilities == 1.0))
    degenerate = len(outcomes) == 0 or verified_legitimate in {0, len(outcomes)}
    interval_method = "census" if census else "normal_design"
    total_interval = (total.ci_lower, total.ci_upper)
    if degenerate and not census:
        share_lower, share_upper = 0.0, 1.0
        total_interval = (0.0, float(population_size))
        interval_method = "uninformative_fallback"
    warnings: list[str] = []
    if len(outcomes) < 30:
        warnings.append("fewer than 30 realized verifications")
    if effective_sample_size < 30:
        warnings.append("inverse-probability effective sample size is below 30")
    if len(outcomes) == 0 or verified_legitimate in {0, len(outcomes)}:
        warnings.append("verified sample does not contain both outcome classes")
    if not 0.0 <= share <= 1.0:
        warnings.append("Horvitz-Thompson point estimate is outside the parameter bounds")
    if census:
        warnings = []

    return HTBinaryEstimate(
        false_decline_total=total.point,
        false_decline_share=share,
        block_precision=1.0 - share,
        standard_error_share=share_se,
        false_decline_ci=(share_lower, share_upper),
        block_precision_ci=(1.0 - share_upper, 1.0 - share_lower),
        false_decline_total_ci=total_interval,
        hajek_false_decline_share=hajek,
        effective_sample_size=effective_sample_size,
        realized_sample_size=len(outcomes),
        verified_legitimate=verified_legitimate,
        stable=not warnings,
        warnings=tuple(warnings),
        interval_method=interval_method,
    )
