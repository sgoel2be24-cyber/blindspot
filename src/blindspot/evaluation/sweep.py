"""Pre-specified, paired-seed policy comparison against a fixed sealed population."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd

from blindspot.contracts import SchemaError
from blindspot.evaluation.sealed import evaluate_plan
from blindspot.product.verification import create_verification_plan


@dataclass(frozen=True)
class SweepConfig:
    # Extra large budgets diagnose small fixture populations, not headline efficiency.
    budget_rates: tuple[float, ...] = (0.0025, 0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50)
    repetitions: int = 200
    seed_start: int = 1729
    exploration_floor: float = 0.10

    def validate(self) -> None:
        if self.repetitions < 2 or self.seed_start < 0:
            raise SchemaError("sweep requires at least two repetitions and a non-negative seed")
        if not self.budget_rates or len(set(self.budget_rates)) != len(self.budget_rates):
            raise SchemaError("budget rates must be non-empty and unique")
        if any(not np.isfinite(rate) or not 0 < rate <= 1 for rate in self.budget_rates):
            raise SchemaError("budget rates must be finite and in (0, 1]")


@dataclass
class SweepResult:
    runs: pd.DataFrame
    summary: pd.DataFrame
    comparison: pd.DataFrame
    displays: dict[str, dict]
    observations: dict[str, list[dict]]


def case_key(policy: str, budget_rate: float) -> str:
    return f"{policy}:{budget_rate:.8g}"


def _wilson(successes: int, total: int) -> tuple[float, float]:
    z = NormalDist().inv_cdf(0.975)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return float(centre - radius), float(centre + radius)


def run_budget_sweep(
    decline_pool: pd.DataFrame,
    sealed_truth: pd.DataFrame,
    config: SweepConfig | None = None,
    *,
    progress: Callable[[str], None] | None = None,
) -> SweepResult:
    """Keep all draws, including empty/unstable cases; never tune on oracle results."""

    config = config or SweepConfig()
    config.validate()
    rows: list[dict] = []
    displays: dict[str, dict] = {}
    observations: dict[str, list[dict]] = {}
    population_size = len(decline_pool)
    for rate in config.budget_rates:
        for policy in ("uniform", "margin_weighted"):
            # No minimum-one rounding: expected budget and rate retain exact meaning.
            budget = population_size * rate
            for seed in range(config.seed_start, config.seed_start + config.repetitions):
                plan = create_verification_plan(
                    decline_pool,
                    policy=policy,
                    expected_budget=budget,
                    seed=seed,
                    exploration_floor=config.exploration_floor,
                )
                report = evaluate_plan(plan, sealed_truth)
                estimate = report.estimate
                aligned = sealed_truth.set_index("row_id").loc[plan.ledger.row_id]
                z = 1 - aligned.is_fraud.to_numpy()
                pi = plan.ledger.propensity.to_numpy()
                exact_variance = float(np.sum(z * (1 - pi) / pi) / population_size**2)
                error_pp = 100 * (estimate.block_precision - report.oracle_block_precision)
                rows.append(
                    {
                        "budget_rate": rate,
                        "policy": policy,
                        "seed": seed,
                        "expected_budget": budget,
                        "realized": report.realized_verifications,
                        "estimate_bp": estimate.block_precision,
                        "error_pp": error_pp,
                        "ci_width_pp": 100
                        * (estimate.block_precision_ci[1] - estimate.block_precision_ci[0]),
                        "covered": report.ci_covers_oracle,
                        "stable": estimate.stable,
                        "interval_method": estimate.interval_method,
                        "effective_sample_size": estimate.effective_sample_size,
                        "discovery_precision": report.discovery_precision,
                        "discovery_recall": report.discovery_recall,
                        "theoretical_se_pp": 100 * np.sqrt(exact_variance),
                        "commitment": plan.commitment,
                    }
                )
                if seed == config.seed_start:
                    # Demo seed is pre-registered, not chosen for a good-looking result.
                    key = case_key(policy, rate)
                    queue = (
                        plan.ledger.loc[plan.ledger.selected]
                        .merge(decline_pool, on="row_id", validate="one_to_one")
                        .sort_values("priority", ascending=False)
                    )
                    displays[key] = {
                        "policy": policy,
                        "budget_rate": rate,
                        "seed": seed,
                        "expected_budget": budget,
                        "realized": report.realized_verifications,
                        "commitment": plan.commitment,
                        "estimate": asdict(estimate),
                        "false_decline_amount": asdict(report.false_decline_amount),
                        "discovery_precision": report.discovery_precision,
                        "selected_fraud_amount": report.selected_fraud_amount,
                        "queue": queue[
                            [
                                "row_id",
                                "transaction_id",
                                "transaction_amount",
                                "risk_score",
                                "priority",
                                "propensity",
                            ]
                        ].to_dict("records"),
                    }
                    observed = queue[["row_id"]].merge(
                        sealed_truth[["row_id", "is_fraud"]], on="row_id", validate="one_to_one"
                    )
                    observations[key] = observed.to_dict("records")
            if progress:
                progress(f"Completed {policy}, {rate:.2%}, {config.repetitions} seeds")

    runs = pd.DataFrame(rows)
    summaries: list[dict] = []
    for (rate, policy), group in runs.groupby(["budget_rate", "policy"], sort=True):
        lower, upper = _wilson(int(group.covered.sum()), len(group))
        stable = group.loc[group.stable]
        summaries.append(
            {
                "budget_rate": rate,
                "policy": policy,
                "repetitions": len(group),
                "expected_budget": float(group.expected_budget.iloc[0]),
                "realized_mean": float(group.realized.mean()),
                "bias_pp": float(group.error_pp.mean()),
                "bias_mc_se_pp": float(group.error_pp.std(ddof=1) / np.sqrt(len(group))),
                "rmse_pp": float(np.sqrt(np.mean(group.error_pp**2))),
                "mae_pp": float(group.error_pp.abs().mean()),
                "ci_width_pp_mean": float(group.ci_width_pp.mean()),
                "coverage": float(group.covered.mean()),
                "coverage_mc_lower": lower,
                "coverage_mc_upper": upper,
                "stable_fraction": float(group.stable.mean()),
                "stable_coverage": float(stable.covered.mean()) if len(stable) else None,
                "zero_sample_fraction": float((group.realized == 0).mean()),
                "fallback_fraction": float(
                    (group.interval_method == "uninformative_fallback").mean()
                ),
                "discovery_precision_mean": float(group.discovery_precision.mean())
                if group.discovery_precision.notna().any()
                else None,
                "discovery_precision_defined_draws": int(group.discovery_precision.notna().sum()),
                "discovery_recall_mean": float(group.discovery_recall.mean())
                if group.discovery_recall.notna().any()
                else None,
                "effective_sample_size_mean": float(group.effective_sample_size.mean()),
                "theoretical_se_pp": float(group.theoretical_se_pp.iloc[0]),
            }
        )
    summary = pd.DataFrame(summaries)
    comparisons = []
    for rate, group in runs.groupby("budget_rate", sort=True):
        paired = group.pivot(index="seed", columns="policy", values="error_pp")
        delta = paired.margin_weighted**2 - paired.uniform**2
        mean = float(delta.mean())
        se = float(delta.std(ddof=1) / np.sqrt(len(delta)))
        comparisons.append(
            {
                "budget_rate": rate,
                "paired_seeds": len(delta),
                "mse_delta_weighted_minus_uniform_pp2": mean,
                "mse_delta_mc_ci_lower": mean - 1.959964 * se,
                "mse_delta_mc_ci_upper": mean + 1.959964 * se,
            }
        )
    return SweepResult(runs, summary, pd.DataFrame(comparisons), displays, observations)
