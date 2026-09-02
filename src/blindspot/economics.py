"""Transparent demo-only economics for a verification program."""

from __future__ import annotations

from dataclasses import dataclass

from blindspot.contracts import SchemaError
from blindspot.evaluation.sealed import EvaluationReport


@dataclass(frozen=True)
class EconomicConfig:
    merchant_margin_rate: float = 0.10
    verification_cost_per_case: float = 1.0
    fraud_loss_given_approval: float = 1.0
    approval_exposure_share: float = 1.0

    def validate(self) -> None:
        if not 0 <= self.merchant_margin_rate <= 1:
            raise SchemaError("merchant_margin_rate must be in [0, 1]")
        if self.verification_cost_per_case < 0:
            raise SchemaError("verification_cost_per_case must be non-negative")
        if not 0 <= self.fraud_loss_given_approval <= 1:
            raise SchemaError("fraud_loss_given_approval must be in [0, 1]")
        if not 0 <= self.approval_exposure_share <= 1:
            raise SchemaError("approval_exposure_share must be in [0, 1]")


@dataclass(frozen=True)
class EconomicSummary:
    currency_unit: str
    estimated_false_decline_amount: float
    estimated_margin_at_risk: float
    verification_program_cost: float
    realized_fraud_exposure: float


def summarize_economics(
    report: EvaluationReport,
    config: EconomicConfig | None = None,
) -> EconomicSummary:
    """Keep merchant loss, program cost, and experiment exposure separate."""

    config = config or EconomicConfig()
    config.validate()
    return EconomicSummary(
        currency_unit="CU",
        estimated_false_decline_amount=report.false_decline_amount.point,
        estimated_margin_at_risk=(report.false_decline_amount.point * config.merchant_margin_rate),
        verification_program_cost=(
            report.realized_verifications * config.verification_cost_per_case
        ),
        realized_fraud_exposure=(
            report.selected_fraud_amount
            * config.fraud_loss_given_approval
            * config.approval_exposure_share
        ),
    )
