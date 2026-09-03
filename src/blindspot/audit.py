"""Local prepare/ingest workflow for actual review evidence; never reads oracle truth."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from blindspot.benchmark import _write_json, file_sha256
from blindspot.contracts import IntegrityError, SchemaError
from blindspot.evaluation.evidence import EvidenceBatch, audit_status, bound_evidence
from blindspot.product.contracts import VerificationPlan
from blindspot.product.verification import create_verification_plan


def prepare_audit(
    pool_path: Path,
    output: Path,
    *,
    policy: str = "uniform",
    budget_rate: float = 0.05,
    seed: int = 1729,
) -> dict:
    if not np.isfinite(budget_rate) or not 0 < budget_rate <= 1:
        raise SchemaError("budget_rate must be in (0, 1]")
    pool = pd.read_csv(pool_path)
    plan = create_verification_plan(
        pool, policy=policy, expected_budget=len(pool) * budget_rate, seed=seed
    )
    output.mkdir(parents=True, exist_ok=False)
    plan.ledger.to_csv(output / "plan.csv", index=False)
    template = plan.ledger.loc[plan.ledger.selected, ["row_id"]].assign(
        status="pending",
        evidence_is_fraud=np.nan,
    )
    template.to_csv(output / "evidence-template.csv", index=False)
    metadata = {
        "policy": policy,
        "seed": seed,
        "expected_budget": plan.expected_budget,
        "commitment": plan.commitment,
        "pool_sha256": file_sha256(pool_path),
        "plan_sha256": file_sha256(output / "plan.csv"),
        "selected_count": plan.selected_count,
        "scope": "Prepared from label-free declines. No oracle outcome was read.",
    }
    _write_json(output / "plan.json", metadata)
    return metadata


def ingest_evidence(
    plan_directory: Path,
    evidence_path: Path,
    output: Path,
    *,
    assumed_population_error_fraction: float,
    minimum_block_precision: float = 0.5,
) -> dict:
    metadata = json.loads((plan_directory / "plan.json").read_text())
    plan_file = plan_directory / "plan.csv"
    if file_sha256(plan_file) != metadata["plan_sha256"]:
        raise IntegrityError("prepared plan file hash mismatch")
    # round_trip is needed so serialized binary floats preserve the original commitment.
    ledger = pd.read_csv(plan_file, float_precision="round_trip")
    plan = VerificationPlan(
        ledger,
        metadata["policy"],
        metadata["expected_budget"],
        metadata["seed"],
        metadata["commitment"],
    )
    evidence = pd.read_csv(evidence_path)
    bounds = bound_evidence(
        plan,
        EvidenceBatch(plan.commitment, evidence),
        assumed_population_error_fraction=assumed_population_error_fraction,
    )
    status = audit_status(
        bounds.block_precision_lower,
        bounds.block_precision_upper,
        minimum_block_precision=minimum_block_precision,
    )
    receipt = {
        "scope": "Actual supplied review batch; labels are evidence, not guaranteed truth.",
        "evidence_sha256": file_sha256(evidence_path),
        "pool_sha256": metadata["pool_sha256"],
        "bounds": asdict(bounds),
        "audit_target": minimum_block_precision,
        "advisory_status": status,
        "assumptions": [
            "Independent Bernoulli selection; potential evidence independent of the realized draw.",
            "The error allowance bounds wrong resolved potential labels "
            "across the WHOLE decline population.",
            "The error allowance is supplied by the operator, "
            "not estimated or verified by this tool.",
            "Pointwise coverage only. Unknown error allowance should be set to 1 (uninformative).",
            "No payment decision or recovery action is performed; "
            "receipt is for human policy review.",
        ],
    }
    _write_json(output, receipt)  # Exclusive creation; never overwrite an audit record.
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Commit a queue from a label-free decline CSV")
    prepare.add_argument("--pool", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--policy", choices=("uniform", "margin_weighted"), default="uniform")
    prepare.add_argument("--budget-rate", type=float, default=0.05)
    prepare.add_argument("--seed", type=int, default=1729)
    ingest = commands.add_parser("ingest", help="Validate a review CSV and write an audit receipt")
    ingest.add_argument("--plan", type=Path, required=True)
    ingest.add_argument("--evidence", type=Path, required=True)
    ingest.add_argument("--output", type=Path, required=True)
    ingest.add_argument("--max-population-label-error", type=float, required=True)
    ingest.add_argument("--minimum-block-precision", type=float, default=0.5)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_audit(
                args.pool,
                args.output,
                policy=args.policy,
                budget_rate=args.budget_rate,
                seed=args.seed,
            )
        else:
            result = ingest_evidence(
                args.plan,
                args.evidence,
                args.output,
                assumed_population_error_fraction=args.max_population_label_error,
                minimum_block_precision=args.minimum_block_precision,
            )
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Audit stopped: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
