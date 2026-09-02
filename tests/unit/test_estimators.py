from __future__ import annotations

import itertools

import numpy as np
import pytest

from blindspot.evaluation.estimators import (
    estimate_false_decline_share,
    horvitz_thompson_total,
)


def test_empty_verification_does_not_claim_perfect_block_precision():
    estimate = estimate_false_decline_share(np.array([]), np.array([]), population_size=100)
    assert estimate.block_precision_ci == (0.0, 1.0)
    assert estimate.false_decline_total_ci == (0.0, 100.0)
    assert not estimate.stable


def test_full_census_recovers_exact_block_precision():
    is_fraud = np.array([1, 0, 1, 0, 0], dtype=np.int8)
    estimate = estimate_false_decline_share(
        is_fraud,
        np.ones(5),
        population_size=5,
    )

    assert estimate.false_decline_total == 3
    assert estimate.false_decline_share == 0.6
    assert estimate.block_precision == 0.4
    assert estimate.standard_error_share == 0
    assert estimate.block_precision_ci == (0.4, 0.4)
    assert estimate.stable
    assert estimate.interval_method == "census"


@pytest.mark.parametrize("outcome", [0, 1])
def test_single_class_requires_full_range_except_for_census(outcome):
    outcomes = np.full(40, outcome)
    sample = estimate_false_decline_share(outcomes, np.full(40, 0.5), population_size=80)
    assert sample.block_precision_ci == (0, 1)
    assert not sample.stable
    census = estimate_false_decline_share(outcomes, np.ones(40), population_size=40)
    assert census.block_precision_ci == (float(outcome), float(outcome))
    assert census.stable


def test_ht_total_uses_inverse_propensity_and_design_variance():
    estimate = horvitz_thompson_total(
        np.array([1.0, 3.0]),
        np.array([0.5, 0.25]),
    )

    assert estimate.point == 14.0
    expected_variance = (0.5 * 1.0 / 0.5**2) + (0.75 * 9.0 / 0.25**2)
    assert np.isclose(estimate.standard_error**2, expected_variance)


def test_ht_total_is_design_unbiased_by_exact_bernoulli_enumeration():
    values = np.array([1.0, 0.0, 1.0])
    propensities = np.array([0.2, 0.5, 0.8])
    expected_estimate = 0.0

    for selected_bits in itertools.product([False, True], repeat=len(values)):
        selected = np.array(selected_bits)
        design_probability = float(np.prod(np.where(selected, propensities, 1.0 - propensities)))
        estimate = horvitz_thompson_total(
            values[selected],
            propensities[selected],
        )
        expected_estimate += design_probability * estimate.point

    assert np.isclose(expected_estimate, values.sum())
