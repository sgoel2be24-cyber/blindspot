"""Sealed, offline-only evaluation surface."""

from blindspot.evaluation.estimators import HTBinaryEstimate, HTTotalEstimate
from blindspot.evaluation.sealed import EvaluationReport, evaluate_plan

__all__ = ["EvaluationReport", "HTBinaryEstimate", "HTTotalEstimate", "evaluate_plan"]
