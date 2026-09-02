"""Randomized verification policies with explicit non-zero inclusion propensities."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

import numpy as np
import pandas as pd

from blindspot.contracts import DEFAULT_SEED, IntegrityError, SchemaError
from blindspot.product.contracts import PLAN_COLUMNS, VerificationPlan, validate_decline_pool

PolicyName = Literal["uniform", "margin_weighted"]


def _margin_priorities(decline_pool: pd.DataFrame, *, exploration_floor: float) -> np.ndarray:
    if not 0 < exploration_floor <= 1:
        raise SchemaError("exploration_floor must be in (0, 1]")
    scores = decline_pool["risk_score"].to_numpy(dtype=np.float64)
    thresholds = decline_pool["decline_threshold"].to_numpy(dtype=np.float64)
    margins = np.maximum(scores - thresholds, 0.0)
    positive = margins[margins > 0]
    scale = max(float(np.median(positive)) if len(positive) else 0.0, 1e-6)
    near_boundary = np.exp(-margins / scale)
    return exploration_floor + (1.0 - exploration_floor) * near_boundary


def propensities_from_weights(weights: np.ndarray, *, expected_budget: float) -> np.ndarray:
    """Water-fill positive weights into probabilities that sum to the expected budget."""

    values = np.asarray(weights, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0:
        raise SchemaError("verification weights must be a non-empty one-dimensional array")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise SchemaError("verification weights must be finite and strictly positive")

    budget = float(expected_budget)
    if not np.isfinite(budget) or not 0 < budget <= len(values):
        raise SchemaError("expected_budget must be finite and in (0, population_size]")
    if np.isclose(budget, len(values), rtol=0, atol=1e-12):
        return np.ones(len(values), dtype=np.float64)

    probabilities = np.zeros(len(values), dtype=np.float64)
    active = np.ones(len(values), dtype=bool)
    remaining_budget = budget

    while active.any():
        active_indices = np.flatnonzero(active)
        scale = remaining_budget / float(values[active].sum())
        candidates = scale * values[active]
        saturated = candidates >= 1.0
        if not saturated.any():
            probabilities[active] = candidates
            break
        saturated_indices = active_indices[saturated]
        probabilities[saturated_indices] = 1.0
        active[saturated_indices] = False
        remaining_budget -= len(saturated_indices)
        if remaining_budget <= 0:
            raise IntegrityError("water-filling exhausted support before assigning all rows")

    if (
        not np.isfinite(probabilities).all()
        or (probabilities <= 0).any()
        or (probabilities > 1).any()
        or not np.isclose(probabilities.sum(), budget, rtol=1e-10, atol=1e-10)
    ):
        raise IntegrityError("computed propensities violate the verification contract")
    return probabilities


def compute_plan_commitment(
    ledger: pd.DataFrame,
    *,
    policy: str,
    expected_budget: float,
    seed: int,
) -> str:
    """Hash a canonical full-population verification ledger."""

    canonical = ledger.loc[:, PLAN_COLUMNS].sort_values("row_id", kind="mergesort")
    rows = [
        {
            "row_id": str(row.row_id),
            "propensity": format(float(row.propensity), ".17g"),
            "priority": format(float(row.priority), ".17g"),
            "selected": bool(row.selected),
            "policy": str(row.policy),
            "expected_budget": format(float(row.expected_budget), ".17g"),
            "seed": int(row.seed),
        }
        for row in canonical.itertuples(index=False)
    ]
    payload = {
        "schema": "blindspot-verification-plan-v1",
        "policy": str(policy),
        "expected_budget": format(float(expected_budget), ".17g"),
        "seed": int(seed),
        "rows": rows,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_verification_plan(
    decline_pool: pd.DataFrame,
    *,
    policy: PolicyName = "margin_weighted",
    expected_budget: float,
    seed: int = DEFAULT_SEED,
    exploration_floor: float = 0.10,
    private_feature_columns: tuple[str, ...] = (),
) -> VerificationPlan:
    """Create and commit a label-blind Bernoulli verification plan."""

    validate_decline_pool(decline_pool, private_feature_columns=private_feature_columns)
    ordered = decline_pool.sort_values("row_id", kind="mergesort").reset_index(drop=True)

    if policy == "uniform":
        priorities = np.ones(len(ordered), dtype=np.float64)
    elif policy == "margin_weighted":
        priorities = _margin_priorities(ordered, exploration_floor=exploration_floor)
    else:
        raise SchemaError(f"unsupported verification policy: {policy}")

    propensities = propensities_from_weights(priorities, expected_budget=expected_budget)
    generator = np.random.Generator(np.random.PCG64(int(seed)))
    selected = generator.random(len(ordered)) < propensities

    ledger = pd.DataFrame(
        {
            "row_id": ordered["row_id"].astype(str).to_numpy(copy=True),
            "propensity": propensities,
            "priority": priorities,
            "selected": selected,
            "policy": np.full(len(ordered), policy, dtype=object),
            "expected_budget": np.full(len(ordered), float(expected_budget)),
            "seed": np.full(len(ordered), int(seed), dtype=np.int64),
        }
    )
    commitment = compute_plan_commitment(
        ledger,
        policy=policy,
        expected_budget=expected_budget,
        seed=seed,
    )
    return VerificationPlan(
        ledger=ledger,
        policy=policy,
        expected_budget=float(expected_budget),
        seed=int(seed),
        commitment=commitment,
    )
