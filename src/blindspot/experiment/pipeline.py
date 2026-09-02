"""Small trusted orchestration layer for a reproducible offline experiment."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from blindspot.data.split import TemporalSplit, TemporalSplitConfig, temporal_split
from blindspot.economics import EconomicConfig, EconomicSummary, summarize_economics
from blindspot.evaluation.sealed import EvaluationReport, evaluate_plan
from blindspot.experiment.censoring import (
    CensoredArtifacts,
    CensoringConfig,
    create_censored_artifacts,
)
from blindspot.model.incumbent import (
    BaselineMetrics,
    IncumbentConfig,
    IncumbentModel,
    choose_decline_threshold,
    evaluate_incumbent,
    fit_incumbent,
)
from blindspot.product.contracts import VerificationPlan
from blindspot.product.verification import PolicyName, create_verification_plan


@dataclass(frozen=True)
class ExperimentConfig:
    split: TemporalSplitConfig = field(default_factory=TemporalSplitConfig)
    incumbent: IncumbentConfig = field(default_factory=IncumbentConfig)
    censoring: CensoringConfig = field(default_factory=CensoringConfig)
    economics: EconomicConfig = field(default_factory=EconomicConfig)
    target_decline_rate: float = 0.05
    policy: PolicyName = "margin_weighted"
    expected_budget_rate: float = 0.005
    sampling_seed: int = 1730
    exploration_floor: float = 0.10


@dataclass(frozen=True)
class ExperimentResult:
    split: TemporalSplit
    incumbent: IncumbentModel
    calibration_metrics: BaselineMetrics
    artifacts: CensoredArtifacts
    verification_plan: VerificationPlan
    evaluation: EvaluationReport
    economics: EconomicSummary


def run_experiment(
    frame: pd.DataFrame,
    config: ExperimentConfig | None = None,
) -> ExperimentResult:
    """Run the frozen train-to-sealed-evaluation path without external services."""

    config = config or ExperimentConfig()
    missing_private_firewall = set(config.incumbent.private_feature_columns).difference(
        config.censoring.private_feature_columns
    )
    if missing_private_firewall:
        raise ValueError(
            "censoring config must declare every incumbent-private feature: "
            f"{sorted(missing_private_firewall)}"
        )
    if not 0 < config.expected_budget_rate <= 1:
        raise ValueError("expected_budget_rate must be in (0, 1]")

    split = temporal_split(frame, config.split)
    incumbent = fit_incumbent(split.train, config.incumbent)
    calibration_scores = incumbent.predict_fraud_probability(split.calibration)
    threshold = choose_decline_threshold(
        calibration_scores,
        target_decline_rate=config.target_decline_rate,
    )
    calibration_metrics = evaluate_incumbent(
        split.calibration[config.incumbent.target_column].to_numpy(),
        calibration_scores,
        threshold=threshold,
    )

    evaluation_scores = incumbent.predict_fraud_probability(split.evaluation)
    artifacts = create_censored_artifacts(
        split.evaluation,
        evaluation_scores,
        threshold=threshold,
        config=config.censoring,
    )
    expected_budget = config.expected_budget_rate * len(artifacts.product_declines)
    plan = create_verification_plan(
        artifacts.product_declines,
        policy=config.policy,
        expected_budget=expected_budget,
        seed=config.sampling_seed,
        exploration_floor=config.exploration_floor,
        private_feature_columns=config.censoring.private_feature_columns,
    )
    evaluation = evaluate_plan(plan, artifacts.sealed_truth)
    economics = summarize_economics(evaluation, config.economics)
    return ExperimentResult(
        split=split,
        incumbent=incumbent,
        calibration_metrics=calibration_metrics,
        artifacts=artifacts,
        verification_plan=plan,
        evaluation=evaluation,
        economics=economics,
    )
