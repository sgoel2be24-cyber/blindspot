"""Offline evaluator that alone joins a committed plan to oracle outcomes."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from blindspot.contracts import (
    IntegrityError,
    SchemaError,
    require_columns,
    require_unique_non_null,
)
from blindspot.evaluation.estimators import (
    HTBinaryEstimate,
    HTTotalEstimate,
    estimate_false_decline_share,
    horvitz_thompson_total,
)
from blindspot.product.contracts import PLAN_COLUMNS, VerificationPlan
from blindspot.product.verification import compute_plan_commitment


@dataclass(frozen=True)
class EvaluationReport:
    plan_commitment: str
    policy: str
    expected_budget: float
    population_size: int
    realized_verifications: int
    estimate: HTBinaryEstimate
    false_decline_amount: HTTotalEstimate
    discovery_precision: float | None
    discovery_recall: float | None
    oracle_false_declines: int
    oracle_false_decline_share: float
    oracle_block_precision: float
    oracle_false_decline_amount: float
    absolute_block_precision_error_pp: float
    ci_covers_oracle: bool
    selected_fraud_amount: float


def _validate_plan(plan: VerificationPlan, truth: pd.DataFrame) -> pd.DataFrame:
    ledger = plan.ledger.copy(deep=True)
    require_columns(ledger, PLAN_COLUMNS, context="verification plan")
    require_unique_non_null(ledger, "row_id", context="verification plan")
    require_unique_non_null(truth, "row_id", context="sealed truth")

    if set(ledger["row_id"]) != set(truth["row_id"]):
        raise IntegrityError("verification plan row IDs do not exactly match the sealed population")
    if len(ledger) == 0:
        raise IntegrityError("verification plan cannot be empty")

    propensities = ledger["propensity"].to_numpy(dtype=np.float64)
    if not np.isfinite(propensities).all() or (propensities <= 0).any() or (propensities > 1).any():
        raise IntegrityError("verification plan propensities must be finite and in (0, 1]")
    if not np.isclose(propensities.sum(), plan.expected_budget, rtol=1e-10, atol=1e-10):
        raise IntegrityError("verification plan propensities do not sum to expected_budget")

    selected_values = ledger["selected"]
    if not pd.api.types.is_bool_dtype(selected_values):
        raise IntegrityError("verification plan selected column must be boolean")
    if set(ledger["policy"].astype(str)) != {plan.policy}:
        raise IntegrityError("verification plan policy metadata is inconsistent")
    if set(ledger["seed"].astype(int)) != {plan.seed}:
        raise IntegrityError("verification plan seed metadata is inconsistent")
    if not np.allclose(
        ledger["expected_budget"].to_numpy(dtype=np.float64),
        plan.expected_budget,
        rtol=0,
        atol=1e-12,
    ):
        raise IntegrityError("verification plan budget metadata is inconsistent")

    recomputed = compute_plan_commitment(
        ledger,
        policy=plan.policy,
        expected_budget=plan.expected_budget,
        seed=plan.seed,
    )
    if recomputed != plan.commitment:
        raise IntegrityError("verification plan commitment does not match its ledger")
    return ledger


def evaluate_plan(
    plan: VerificationPlan,
    sealed_truth: pd.DataFrame,
    *,
    confidence_level: float = 0.95,
) -> EvaluationReport:
    """Reveal selected outcomes and compute aggregate offline evaluation metrics."""

    require_columns(
        sealed_truth,
        ["row_id", "is_fraud", "transaction_amount"],
        context="sealed truth",
    )
    truth = sealed_truth.loc[:, ["row_id", "is_fraud", "transaction_amount"]].copy()
    outcomes = set(truth["is_fraud"].dropna().unique().tolist())
    if truth["is_fraud"].isna().any() or not outcomes.issubset({0, 1}):
        raise SchemaError("sealed truth.is_fraud must contain only binary 0/1 values")
    amounts = pd.to_numeric(truth["transaction_amount"], errors="coerce").to_numpy(dtype=np.float64)
    if not np.isfinite(amounts).all() or (amounts < 0).any():
        raise SchemaError("sealed truth.transaction_amount must be finite and non-negative")

    ledger = _validate_plan(plan, truth)
    selected_ledger = ledger.loc[ledger["selected"]].copy()
    observed = selected_ledger.merge(
        truth,
        on="row_id",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    selected_outcomes = observed["is_fraud"].to_numpy(dtype=np.int8)
    selected_propensities = observed["propensity"].to_numpy(dtype=np.float64)

    estimate = estimate_false_decline_share(
        selected_outcomes,
        selected_propensities,
        population_size=len(truth),
        confidence_level=confidence_level,
    )
    selected_legitimate_amount = (1.0 - selected_outcomes) * observed[
        "transaction_amount"
    ].to_numpy(dtype=np.float64)
    amount_estimate = horvitz_thompson_total(
        selected_legitimate_amount,
        selected_propensities,
        confidence_level=confidence_level,
        lower_bound=0.0,
        upper_bound=float(amounts.sum()),
    )
    if estimate.interval_method == "uninformative_fallback":
        # All-decline transaction volume is observable without knowing outcomes.
        amount_estimate = replace(amount_estimate, ci_lower=0.0, ci_upper=float(amounts.sum()))

    oracle_legitimate = 1 - truth["is_fraud"].to_numpy(dtype=np.int8)
    oracle_false_declines = int(oracle_legitimate.sum())
    oracle_share = oracle_false_declines / len(truth)
    selected_legitimate = int((1 - selected_outcomes).sum())
    realized = len(observed)
    discovery_precision = selected_legitimate / realized if realized else None
    discovery_recall = (
        selected_legitimate / oracle_false_declines if oracle_false_declines else None
    )
    oracle_amount = float(np.sum(oracle_legitimate * amounts))
    selected_fraud_amount = float(
        np.sum(selected_outcomes * observed["transaction_amount"].to_numpy(dtype=np.float64))
    )

    block_lower, block_upper = estimate.block_precision_ci
    oracle_block_precision = 1.0 - oracle_share
    return EvaluationReport(
        plan_commitment=plan.commitment,
        policy=plan.policy,
        expected_budget=plan.expected_budget,
        population_size=len(truth),
        realized_verifications=realized,
        estimate=estimate,
        false_decline_amount=amount_estimate,
        discovery_precision=discovery_precision,
        discovery_recall=discovery_recall,
        oracle_false_declines=oracle_false_declines,
        oracle_false_decline_share=oracle_share,
        oracle_block_precision=oracle_block_precision,
        oracle_false_decline_amount=oracle_amount,
        absolute_block_precision_error_pp=abs(estimate.block_precision - oracle_block_precision)
        * 100.0,
        ci_covers_oracle=block_lower <= oracle_block_precision <= block_upper,
        selected_fraud_amount=selected_fraud_amount,
    )
