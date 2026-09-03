from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from blindspot.contracts import IntegrityError, SchemaError
from blindspot.evaluation.evidence import (
    EvidenceBatch,
    audit_status,
    bernstein_radius,
    bound_evidence,
)
from blindspot.product.contracts import VerificationPlan
from blindspot.product.verification import compute_plan_commitment


def plan_and_batch(pi, selected, labels):
    pi = np.asarray(pi, dtype=float)
    ledger = pd.DataFrame(
        {
            "row_id": [f"r{i}" for i in range(len(pi))],
            "propensity": pi,
            "priority": 1.0,
            "selected": np.asarray(selected, dtype=bool),
            "policy": "uniform",
            "expected_budget": pi.sum(),
            "seed": 1,
        }
    )
    commitment = compute_plan_commitment(ledger, policy="uniform", expected_budget=pi.sum(), seed=1)
    plan = VerificationPlan(ledger, "uniform", float(pi.sum()), 1, commitment)
    values = np.asarray(labels, dtype=float)[selected]
    records = pd.DataFrame(
        {
            "row_id": ledger.loc[ledger.selected, "row_id"].to_numpy(),
            "status": np.where(np.isnan(values), "pending", "resolved"),
            "evidence_is_fraud": values,
        }
    )
    return plan, EvidenceBatch(commitment, records)


def test_census_missingness_error_budget_and_abstention():
    plan, batch = plan_and_batch([1] * 4, [True] * 4, [1, 0, np.nan, np.nan])
    bounds = bound_evidence(plan, batch, assumed_population_error_fraction=0)
    assert (bounds.block_precision_lower, bounds.block_precision_upper) == (0.25, 0.75)
    assert bounds.sampling_radius == 0
    assert bounds.pending == bounds.resolved == 2
    assert audit_status(0.25, 0.75, minimum_block_precision=0.5) == "insufficient_evidence"
    wider = bound_evidence(plan, batch, assumed_population_error_fraction=0.25)
    assert (wider.block_precision_lower, wider.block_precision_upper) == (0, 1)
    complete_plan, complete = plan_and_batch([1] * 4, [True] * 4, [1, 0, 0, 0])
    exact = bound_evidence(complete_plan, complete, assumed_population_error_fraction=0)
    assert exact.block_precision_lower == exact.block_precision_upper == 0.25


@pytest.mark.parametrize("selected", [[False] * 4, [True] * 4])
def test_empty_or_pending_evidence_never_claims_certainty(selected):
    plan, batch = plan_and_batch([0.5] * 4, selected, [np.nan] * 4)
    result = bound_evidence(plan, batch, assumed_population_error_fraction=0)
    assert (result.block_precision_lower, result.block_precision_upper) == (0, 1)
    assert result.completed_only_block_precision is None


def test_evidence_packet_integrity_and_pending_labels():
    plan, batch = plan_and_batch([0.5] * 4, [True, True, False, False], [1, 0, 1, 0])
    with pytest.raises(IntegrityError, match="commitment"):
        bound_evidence(
            plan, EvidenceBatch("wrong", batch.records), assumed_population_error_fraction=0
        )
    for changed in (batch.records.iloc[:1], batch.records.assign(row_id=["r0", "r3"])):
        with pytest.raises(IntegrityError, match="exactly"):
            bound_evidence(
                plan, EvidenceBatch(plan.commitment, changed), assumed_population_error_fraction=0
            )
    for changed in (
        pd.concat([batch.records, batch.records.iloc[:1]]),
        batch.records.assign(status="pending"),
        batch.records.assign(status="invented"),
        batch.records.assign(evidence_is_fraud=2),
        batch.records.assign(secret_truth=1),
    ):
        with pytest.raises((SchemaError, IntegrityError)):
            bound_evidence(
                plan, EvidenceBatch(plan.commitment, changed), assumed_population_error_fraction=0
            )
    plan.ledger.loc[0, "propensity"] = 0.6
    with pytest.raises(IntegrityError):
        bound_evidence(plan, batch, assumed_population_error_fraction=0)


def test_removing_evidence_and_increasing_error_assumption_only_widen():
    plan, batch = plan_and_batch([0.8] * 100, [True] * 80 + [False] * 20, [0, 1] * 50)
    before = bound_evidence(plan, batch, assumed_population_error_fraction=0)
    removed = batch.records.copy()
    removed.loc[:19, ["status", "evidence_is_fraud"]] = ["pending", np.nan]
    after = bound_evidence(
        plan, EvidenceBatch(plan.commitment, removed), assumed_population_error_fraction=0.1
    )
    assert after.block_precision_lower <= before.block_precision_lower
    assert after.block_precision_upper >= before.block_precision_upper
    shuffled = EvidenceBatch(plan.commitment, batch.records.sample(frac=1, random_state=3))
    assert before == bound_evidence(plan, shuffled, assumed_population_error_fraction=0)


@pytest.mark.parametrize("epsilon", [0, 0.125])
def test_exact_enumeration_coverage_under_arbitrary_missingness_and_bounded_errors(epsilon):
    pi = np.array([1, 0.95, 0.8, 0.95, 0.9, 0.95, 0.9, 1])
    truth = np.array([1, 1, 0, 0, 1, 0, 0, 0])
    labels = np.array([1, np.nan, 0, 0, 1, 0, np.nan, 0])
    if epsilon:
        labels[0] = 0  # One wrong potential resolved label among all eight rows.
    coverage = total = 0.0
    for bits in itertools.product([False, True], repeat=len(pi)):
        selected = np.asarray(bits)
        probability = float(np.prod(np.where(selected, pi, 1 - pi)))
        if not probability:
            continue
        plan, batch = plan_and_batch(pi, selected, labels)
        result = bound_evidence(plan, batch, assumed_population_error_fraction=epsilon)
        total += probability
        coverage += probability * (
            result.block_precision_lower <= truth.mean() <= result.block_precision_upper
        )
    assert total == pytest.approx(1)
    assert coverage >= 0.95 - 1e-12


def test_radius_and_explicit_assumptions_validation():
    assert bernstein_radius(np.ones(10)) == 0
    assert bernstein_radius(np.full(1000, 0.5)) < bernstein_radius(np.full(1000, 0.05))
    assert bernstein_radius(np.full(1000, 0.1), confidence_level=0.99) > bernstein_radius(
        np.full(1000, 0.1)
    )
    for pi in ([], [0], [1.1], [np.nan]):
        with pytest.raises(SchemaError):
            bernstein_radius(pi)
    plan, batch = plan_and_batch([1], [True], [1])
    for epsilon in (-1, 1.1, np.nan):
        with pytest.raises(SchemaError):
            bound_evidence(plan, batch, assumed_population_error_fraction=epsilon)
    assert audit_status(0.1, 0.2, minimum_block_precision=0.5) == "below_target"
    assert audit_status(0.7, 0.9, minimum_block_precision=0.5) == "at_or_above_target"
