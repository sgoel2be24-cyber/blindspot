"""Post-selection evidence bounds. No oracle or missing-at-random assumption required."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from blindspot.contracts import IntegrityError, SchemaError, require_unique_non_null
from blindspot.evaluation.sealed import _validate_plan
from blindspot.product.contracts import VerificationPlan

EVIDENCE_COLUMNS = ("row_id", "status", "evidence_is_fraud")


@dataclass(frozen=True)
class EvidenceBatch:
    plan_commitment: str
    records: pd.DataFrame


@dataclass(frozen=True)
class EvidenceBounds:
    plan_commitment: str
    selected: int
    resolved: int
    pending: int
    confidence_level: float
    assumed_population_error_fraction: float
    block_precision_lower: float
    block_precision_upper: float
    sampling_radius: float
    completed_only_block_precision: float | None
    method: str = "bernstein_partial_identification"


def bernstein_radius(propensities: np.ndarray, *, confidence_level: float = 0.95) -> float:
    """Simultaneous one-sided endpoint radius; see EVIDENCE_RELIABILITY_CONTRACT.md."""

    pi = np.asarray(propensities, dtype=np.float64)
    if pi.ndim != 1 or not len(pi):
        raise SchemaError("a non-empty full-population propensity vector is required")
    if not np.isfinite(pi).all() or (pi <= 0).any() or (pi > 1).any():
        raise SchemaError("propensities must be finite and in (0, 1]")
    if not np.isfinite(confidence_level) or not 0 < confidence_level < 1:
        raise SchemaError("confidence_level must be in (0, 1)")
    non_census = pi[pi < 1]
    if not len(non_census):
        return 0.0
    with np.errstate(over="ignore", divide="ignore"):
        variance_bound = np.sum((1 - non_census) / non_census)
        maximum_increment = max(1.0, float(np.max((1 - non_census) / non_census)))
        log_tail = np.log(2.0 / (1 - confidence_level))
        linear = maximum_increment * log_tail / 3
        radius = (linear + np.sqrt(2 * variance_bound * log_tail + linear**2)) / len(pi)
    return float(radius) if np.isfinite(radius) else float("inf")


def bound_evidence(
    plan: VerificationPlan,
    batch: EvidenceBatch,
    *,
    assumed_population_error_fraction: float,
    confidence_level: float = 0.95,
) -> EvidenceBounds:
    """Bound true population fraud share from exactly the committed sample's evidence.

    The error fraction is an assumption about the ENTIRE declined population's
    potential resolved labels, not the observed sample's error rate. Selection must
    be independent Bernoulli, with potential evidence fixed independently of its draw.
    """

    epsilon = float(assumed_population_error_fraction)
    if not np.isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise SchemaError("assumed_population_error_fraction must be in [0, 1]")
    # Reuse the outcome-free ledger checks; only population IDs are passed, no truth.
    ledger = _validate_plan(plan, plan.ledger[["row_id"]])
    if ((ledger.propensity == 1) & ~ledger.selected).any():
        raise IntegrityError("certainty-inclusion rows must be selected")
    if batch.plan_commitment != plan.commitment:
        raise IntegrityError("evidence batch is not bound to this plan commitment")
    records = batch.records.copy(deep=True)
    if set(records.columns) != set(EVIDENCE_COLUMNS):
        raise SchemaError(f"evidence batch requires exactly {EVIDENCE_COLUMNS}")
    require_unique_non_null(records, "row_id", context="evidence batch")
    selected = ledger.loc[ledger.selected]
    if set(records.row_id) != set(selected.row_id):
        raise IntegrityError("evidence must contain exactly every selected ID, pending included")
    if not records.status.isin(["resolved", "pending"]).all():
        raise SchemaError("evidence status must be resolved or pending")
    resolved_mask = records.status.eq("resolved")
    if not records.loc[resolved_mask, "evidence_is_fraud"].isin([0, 1]).all():
        raise SchemaError("resolved evidence requires a binary fraud label")
    if records.loc[~resolved_mask, "evidence_is_fraud"].notna().any():
        raise SchemaError("pending evidence must not contain a label")
    aligned = selected[["row_id", "propensity"]].merge(
        records, on="row_id", validate="one_to_one", how="left"
    )
    radius = bernstein_radius(ledger.propensity.to_numpy(), confidence_level=confidence_level)
    resolved = aligned.status.eq("resolved").to_numpy()
    labels = aligned.evidence_is_fraud.fillna(0).to_numpy(dtype=float)
    weights = 1 / aligned.propensity.to_numpy(dtype=float)
    lower_endpoint = float(np.sum(weights * labels) / len(ledger))
    upper_endpoint = float(np.sum(weights * np.where(resolved, labels, 1)) / len(ledger))
    lower = float(np.clip(lower_endpoint - radius - epsilon, 0, 1))
    upper = float(np.clip(upper_endpoint + radius + epsilon, 0, 1))
    if not resolved.any():
        lower, upper = 0.0, 1.0
    denominator = float(weights[resolved].sum())
    naive = float(np.sum(weights * labels) / denominator) if denominator else None
    return EvidenceBounds(
        plan_commitment=plan.commitment,
        selected=len(selected),
        resolved=int(resolved.sum()),
        pending=int((~resolved).sum()),
        confidence_level=confidence_level,
        assumed_population_error_fraction=epsilon,
        block_precision_lower=lower,
        block_precision_upper=upper,
        sampling_radius=radius,
        completed_only_block_precision=naive,
    )


def audit_status(lower: float, upper: float, *, minimum_block_precision: float) -> str:
    """Advisory policy-audit status only; never an approve/decline instruction."""

    if not all(np.isfinite(v) for v in (lower, upper, minimum_block_precision)):
        raise SchemaError("audit bounds and target must be finite")
    if not 0 <= lower <= upper <= 1 or not 0 < minimum_block_precision < 1:
        raise SchemaError("invalid audit bounds or target")
    if upper < minimum_block_precision:
        return "below_target"
    if lower >= minimum_block_precision:
        return "at_or_above_target"
    return "insufficient_evidence"
