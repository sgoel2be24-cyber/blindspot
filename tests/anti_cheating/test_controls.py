from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from blindspot.contracts import IntegrityError, SchemaError
from blindspot.data.split import temporal_split
from blindspot.evaluation.sealed import evaluate_plan
from blindspot.experiment.censoring import CensoringConfig, create_censored_artifacts
from blindspot.model.incumbent import (
    IncumbentConfig,
    choose_decline_threshold,
    fit_incumbent,
)
from blindspot.product.contracts import VerificationPlan, validate_decline_pool
from blindspot.product.verification import create_verification_plan


def _build_boundary_fixture(frame):
    split = temporal_split(frame)
    private = ("incumbent_private_signal",)
    config = IncumbentConfig(
        max_features=6,
        max_iter=30,
        min_samples_leaf=8,
        private_feature_columns=private,
    )
    model = fit_incumbent(split.train, config)
    calibration_scores = model.predict_fraud_probability(split.calibration)
    threshold = choose_decline_threshold(calibration_scores, target_decline_rate=0.30)
    evaluation_scores = model.predict_fraud_probability(split.evaluation)
    artifacts = create_censored_artifacts(
        split.evaluation,
        evaluation_scores,
        threshold=threshold,
        config=CensoringConfig(private_feature_columns=private),
    )
    plan = create_verification_plan(
        artifacts.product_declines,
        expected_budget=max(1.0, len(artifacts.product_declines) * 0.60),
        seed=51,
        private_feature_columns=private,
    )
    return split, model, calibration_scores, artifacts, plan


def test_ac01_temporal_isolation_is_disjoint_strict_and_shuffle_safe(synthetic_transactions):
    first = temporal_split(synthetic_transactions)
    replay = temporal_split(synthetic_transactions.sample(frac=1, random_state=22))

    assert set(first.train.TransactionID) == set(replay.train.TransactionID)
    assert set(first.calibration.TransactionID) == set(replay.calibration.TransactionID)
    assert set(first.evaluation.TransactionID) == set(replay.evaluation.TransactionID)
    assert first.train.TransactionDT.max() < first.calibration.TransactionDT.min()
    assert first.calibration.TransactionDT.max() < first.evaluation.TransactionDT.min()


def test_ac02_target_and_private_feature_firewall(synthetic_transactions):
    _, model, _, artifacts, _ = _build_boundary_fixture(synthetic_transactions)
    assert {"isFraud", "TransactionID", "TransactionDT"}.isdisjoint(model.feature_columns)
    validate_decline_pool(
        artifacts.product_declines,
        private_feature_columns=("incumbent_private_signal",),
    )

    leaked = artifacts.product_declines.assign(isFraud=0)
    with pytest.raises(SchemaError, match="forbidden fields"):
        validate_decline_pool(leaked)
    private_leak = artifacts.product_declines.assign(incumbent_private_signal=0.2)
    with pytest.raises(SchemaError, match="forbidden fields"):
        validate_decline_pool(
            private_leak,
            private_feature_columns=("incumbent_private_signal",),
        )


def test_ac03_product_imports_cannot_cross_the_sealed_boundary():
    product_dir = Path(__file__).parents[2] / "src" / "blindspot" / "product"
    forbidden_prefixes = ("blindspot.evaluation", "blindspot.experiment")
    violations = []

    for path in sorted(product_dir.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            else:
                continue
            for imported in imports:
                if imported.startswith(forbidden_prefixes):
                    violations.append(f"{path.name}: {imported}")

    assert violations == []


def test_ac04_selection_is_invariant_to_oracle_label_permutation(synthetic_transactions):
    _, _, _, artifacts, plan = _build_boundary_fixture(synthetic_transactions)
    permuted_truth = artifacts.sealed_truth.copy()
    permuted_truth["is_fraud"] = np.roll(permuted_truth["is_fraud"].to_numpy(), 1)

    replay = create_verification_plan(
        artifacts.product_declines,
        expected_budget=plan.expected_budget,
        seed=plan.seed,
        private_feature_columns=("incumbent_private_signal",),
    )

    assert replay.commitment == plan.commitment
    assert not permuted_truth["is_fraud"].equals(artifacts.sealed_truth["is_fraud"])


def test_ac05_evaluator_rejects_tampered_duplicate_and_unknown_ledgers(synthetic_transactions):
    _, _, _, artifacts, plan = _build_boundary_fixture(synthetic_transactions)
    assert evaluate_plan(plan, artifacts.sealed_truth).population_size == len(plan.ledger)

    changed = plan.ledger.copy()
    changed.loc[0, "propensity"] *= 0.9
    tampered = VerificationPlan(
        ledger=changed,
        policy=plan.policy,
        expected_budget=plan.expected_budget,
        seed=plan.seed,
        commitment=plan.commitment,
    )
    with pytest.raises(IntegrityError):
        evaluate_plan(tampered, artifacts.sealed_truth)

    duplicate = plan.ledger.copy()
    duplicate.loc[1, "row_id"] = duplicate.loc[0, "row_id"]
    duplicated_plan = VerificationPlan(
        ledger=duplicate,
        policy=plan.policy,
        expected_budget=plan.expected_budget,
        seed=plan.seed,
        commitment=plan.commitment,
    )
    with pytest.raises(SchemaError, match="must be unique"):
        evaluate_plan(duplicated_plan, artifacts.sealed_truth)

    unknown = plan.ledger.copy()
    unknown.loc[0, "row_id"] = "unknown-row"
    unknown_plan = VerificationPlan(
        ledger=unknown,
        policy=plan.policy,
        expected_budget=plan.expected_budget,
        seed=plan.seed,
        commitment=plan.commitment,
    )
    with pytest.raises(IntegrityError, match="do not exactly match"):
        evaluate_plan(unknown_plan, artifacts.sealed_truth)


def test_ac06_full_replay_is_deterministic_and_seed_changes_only_draw(synthetic_transactions):
    first = _build_boundary_fixture(synthetic_transactions)
    second = _build_boundary_fixture(synthetic_transactions.sample(frac=1, random_state=7))
    _, _, first_scores, first_artifacts, first_plan = first
    _, _, second_scores, second_artifacts, second_plan = second

    assert np.allclose(first_scores, second_scores, rtol=0, atol=1e-12)
    pd.testing.assert_frame_equal(
        first_artifacts.product_declines, second_artifacts.product_declines
    )
    assert first_plan.commitment == second_plan.commitment

    changed_seed = create_verification_plan(
        first_artifacts.product_declines,
        expected_budget=first_plan.expected_budget,
        seed=first_plan.seed + 1,
        private_feature_columns=("incumbent_private_signal",),
    )
    assert np.allclose(first_plan.ledger["propensity"], changed_seed.ledger["propensity"])
    assert not first_plan.ledger["selected"].equals(changed_seed.ledger["selected"])
