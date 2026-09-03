from __future__ import annotations

import pandas as pd
import pytest

from blindspot.audit import ingest_evidence, prepare_audit
from blindspot.contracts import IntegrityError


def test_label_free_prepare_ingest_and_immutable_receipt(tmp_path):
    pool = pd.DataFrame(
        {
            "row_id": [f"r{i}" for i in range(60)],
            "transaction_id": range(60),
            "transaction_dt": range(60),
            "transaction_amount": 10,
            "risk_score": 0.8,
            "decline_threshold": 0.5,
        }
    )
    pool_path, plan = tmp_path / "pool.csv", tmp_path / "plan"
    pool.to_csv(pool_path, index=False)
    metadata = prepare_audit(pool_path, plan, policy="margin_weighted", budget_rate=1 / 3)
    assert metadata["selected_count"] > 0
    pending = plan / "evidence-template.csv"
    receipt = ingest_evidence(
        plan, pending, tmp_path / "pending.json", assumed_population_error_fraction=0
    )
    assert receipt["bounds"]["block_precision_lower"] == 0
    assert receipt["bounds"]["block_precision_upper"] == 1
    assert receipt["advisory_status"] == "insufficient_evidence"
    evidence = pd.read_csv(pending).assign(status="resolved", evidence_is_fraud=0)
    evidence_path = tmp_path / "review.csv"
    evidence.to_csv(evidence_path, index=False)
    ingest_evidence(
        plan, evidence_path, tmp_path / "review.json", assumed_population_error_fraction=0.05
    )
    with pytest.raises(FileExistsError):
        ingest_evidence(
            plan, evidence_path, tmp_path / "review.json", assumed_population_error_fraction=0.05
        )
    evidence.iloc[:1].to_csv(evidence_path, index=False)
    with pytest.raises(IntegrityError, match="exactly"):
        ingest_evidence(
            plan, evidence_path, tmp_path / "invalid.json", assumed_population_error_fraction=0
        )
    with pytest.raises(FileExistsError):
        prepare_audit(pool_path, plan)
