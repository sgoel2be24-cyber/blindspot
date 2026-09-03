"""Registered evidence stress tests on an existing frozen benchmark; never retrains."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from blindspot.benchmark import _write_json, file_sha256
from blindspot.contracts import IntegrityError, SchemaError
from blindspot.dashboard_data import read_artifact
from blindspot.evaluation.evidence import EvidenceBatch, audit_status, bound_evidence
from blindspot.evaluation.sealed import evaluate_plan
from blindspot.product.verification import create_verification_plan


@dataclass(frozen=True)
class EvidenceScenario:
    name: str
    label: str
    mechanism: str = "perfect"
    cutoff_day: int = 30
    assumed_error_fraction: float = 0.0
    assumptions_valid: bool = True


SCENARIOS = (
    EvidenceScenario("perfect", "Immediate, perfect evidence"),
    EvidenceScenario("missing_30", "30% randomly missing", "missing_random"),
    EvidenceScenario("missing_selective", "Missingness depends on truth", "missing_selective"),
    EvidenceScenario("delay_day_1", "Delayed evidence · day 1", "delay", 1),
    EvidenceScenario("delay_day_7", "Delayed evidence · day 7", "delay", 7),
    EvidenceScenario("delay_day_30", "Delayed evidence · day 30", "delay", 30),
    EvidenceScenario("noise_5", "5% wrong labels · error allowance 5%", "noise", 30, 0.05),
    EvidenceScenario(
        "noise_unacknowledged", "5% wrong labels · wrongly assumed perfect", "noise", 30, 0, False
    ),
)


def simulate_potential_evidence(
    truth: pd.DataFrame, scenario: EvidenceScenario, *, seed: int = 90203
) -> pd.DataFrame:
    """Fixed potential evidence for ALL rows, generated without a selection plan.

    Trusted simulation only. Real adapters must provide actual evidence instead.
    """

    ordered = truth.sort_values("row_id").reset_index(drop=True)
    if ordered.row_id.isna().any() or not ordered.row_id.is_unique:
        raise SchemaError("potential evidence requires unique non-null row IDs")
    if not ordered.is_fraud.isin([0, 1]).all():
        raise SchemaError("simulation requires binary oracle outcomes")
    rng = np.random.default_rng(seed)
    outcomes = ordered.is_fraud.to_numpy(dtype=float)
    pending = np.zeros(len(ordered), dtype=bool)
    if scenario.mechanism == "missing_random":
        pending = rng.random(len(ordered)) < 0.30
    elif scenario.mechanism == "missing_selective":
        pending = rng.random(len(ordered)) < np.where(outcomes == 1, 0.60, 0.10)
    elif scenario.mechanism == "delay":
        pending = np.where(outcomes == 1, 14, 2) > scenario.cutoff_day
    elif scenario.mechanism == "noise":
        flipped = rng.permutation(len(ordered))[: int(np.floor(0.05 * len(ordered)))]
        outcomes[flipped] = 1 - outcomes[flipped]
    elif scenario.mechanism != "perfect":
        raise SchemaError("unknown evidence scenario mechanism")
    outcomes[pending] = np.nan
    return pd.DataFrame(
        {
            "row_id": ordered.row_id,
            "status": np.where(pending, "pending", "resolved"),
            "evidence_is_fraud": outcomes,
        }
    )


def build_reliability(
    source_bundle: str | Path,
    output: str | Path,
    *,
    repetitions: int = 200,
    rates: tuple[float, ...] = (0.0025, 0.005, 0.01, 0.02, 0.05),
    progress=None,
) -> dict:
    """Preserve all fixed scenarios/draws, and export only aggregates for the UI."""

    if repetitions < 2 or not rates or len(set(rates)) != len(rates):
        raise SchemaError("at least two draws and unique nonempty rates are required")
    if any(not np.isfinite(rate) or not 0 < rate <= 1 for rate in rates):
        raise SchemaError("rates must be in (0, 1]")
    source_root = Path(source_bundle).resolve()
    manifest = read_artifact(source_root, "manifest.json")
    original = read_artifact(source_root, "benchmark.json")
    pool = pd.read_csv(source_root / "product/declines.csv").sort_values("row_id")
    truth = pd.read_csv(source_root / "sealed/truth.csv").sort_values("row_id")
    source_hashes = {
        name: file_sha256(source_root / name)
        for name in ("manifest.json", "benchmark.json", "product/declines.csv", "sealed/truth.csv")
    }
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    design = {
        "schema_version": 1,
        "source_run_id": manifest["run_id"],
        "source_hashes": source_hashes,
        "source_label": manifest["source"]["label"],
        "scope": "Post-benchmark simulation, not production evidence or a new unseen test set.",
        "scenarios": [asdict(scenario) for scenario in SCENARIOS],
        "rates": rates,
        "policies": ["uniform", "margin_weighted"],
        "repetitions": repetitions,
        "seed_start": 1729,
        "evidence_seed": 90203,
        "confidence_level": 0.95,
        "audit_threshold": 0.5,
        "exploration_floor": manifest["sweep_config"]["exploration_floor"],
        "method": "bernstein_partial_identification",
    }
    _write_json(root / "registered_reliability.json", design)
    potentials = {
        s.name: simulate_potential_evidence(truth, s).set_index("row_id") for s in SCENARIOS
    }
    oracle = float(truth.is_fraud.mean())
    if (
        not np.isclose(oracle, original["oracle"]["block_precision"])
        or len(pool) != manifest["declines"]
    ):
        raise IntegrityError("source population disagrees with the original benchmark")
    rows, displays = [], {}
    for rate in rates:
        for policy in design["policies"]:
            for seed in range(1729, 1729 + repetitions):
                plan = create_verification_plan(
                    pool,
                    policy=policy,
                    expected_budget=rate * len(pool),
                    seed=seed,
                    exploration_floor=design["exploration_floor"],
                )
                # Validate source truth against the complete committed population.
                if seed == 1729:
                    evaluate_plan(plan, truth)
                selected_ids = plan.ledger.loc[plan.ledger.selected, "row_id"]
                for scenario in SCENARIOS:
                    records = potentials[scenario.name].loc[selected_ids].reset_index()
                    bounds = bound_evidence(
                        plan,
                        EvidenceBatch(plan.commitment, records),
                        assumed_population_error_fraction=scenario.assumed_error_fraction,
                    )
                    lower, upper = bounds.block_precision_lower, bounds.block_precision_upper
                    status = audit_status(
                        lower, upper, minimum_block_precision=design["audit_threshold"]
                    )
                    incorrect_decision = (status == "below_target" and oracle >= 0.5) or (
                        status == "at_or_above_target" and oracle < 0.5
                    )
                    naive = bounds.completed_only_block_precision
                    row = {
                        "scenario": scenario.name,
                        "policy": policy,
                        "budget_rate": rate,
                        "seed": seed,
                        "commitment": plan.commitment,
                        "selected": bounds.selected,
                        "resolved": bounds.resolved,
                        "pending": bounds.pending,
                        "lower": lower,
                        "upper": upper,
                        "width_pp": 100 * (upper - lower),
                        "covered": lower <= oracle <= upper,
                        "naive_completed_only_bp": naive,
                        "naive_error_pp": None if naive is None else 100 * (naive - oracle),
                        "status": status,
                        "incorrect_decision": incorrect_decision,
                        "assumptions_valid": scenario.assumptions_valid,
                    }
                    rows.append(row)
                    if seed == 1729:
                        displays[f"{scenario.name}:{policy}:{rate:.8g}"] = {
                            "scenario": asdict(scenario),
                            "policy": policy,
                            "budget_rate": rate,
                            "seed": seed,
                            "bounds": asdict(bounds),
                        }
            if progress:
                progress(
                    f"Evidence stress: {policy}, {rate:.2%}, all 8 scenarios × {repetitions} seeds"
                )
    runs = pd.DataFrame(rows)
    summary = []
    for (scenario, policy, rate), group in runs.groupby(
        ["scenario", "policy", "budget_rate"], sort=True
    ):
        naive = group.naive_error_pp.dropna()
        summary.append(
            {
                "scenario": scenario,
                "policy": policy,
                "budget_rate": rate,
                "draws": len(group),
                "selected_mean": float(group.selected.mean()),
                "resolved_mean": float(group.resolved.mean()),
                "pending_mean": float(group.pending.mean()),
                "mean_width_pp": float(group.width_pp.mean()),
                "coverage": float(group.covered.mean()),
                "naive_defined_draws": len(naive),
                "naive_bias_pp": float(naive.mean()) if len(naive) else None,
                "naive_rmse_pp": float(np.sqrt(np.mean(naive**2))) if len(naive) else None,
                "abstention_fraction": float(group.status.eq("insufficient_evidence").mean()),
                "incorrect_decision_fraction": float(group.incorrect_decision.mean()),
                "assumptions_valid": bool(group.assumptions_valid.iloc[0]),
            }
        )
    public = {
        "design": design,
        "run_id": file_sha256(root / "registered_reliability.json")[:16],
        "cases": displays,
        "limitations": [
            "Simulated evidence, not disputes, analyst reviews or a production integration.",
            "Bounds are pointwise, conditional on fixed potential evidence "
            "and independent Bernoulli selection.",
            "The whole-population label-error allowance is an assumption, "
            "not estimated from this sample.",
            "Conservative wide ranges and abstention are retained; "
            "coverage alone is not usefulness.",
            "The original HT/normal benchmark is unchanged; no model or sampling-policy tuning.",
        ],
    }
    _write_json(root / "reliability.json", public)
    _write_json(
        root / "reliability_benchmark.json", {"oracle_block_precision": oracle, "summary": summary}
    )
    runs.to_csv(root / "stress_runs.csv", index=False)
    pd.DataFrame(summary).to_csv(root / "stress_summary.csv", index=False)
    files = (
        "registered_reliability.json",
        "reliability.json",
        "reliability_benchmark.json",
        "stress_runs.csv",
        "stress_summary.csv",
    )
    _write_json(root / "checksums.json", {name: file_sha256(root / name) for name in files})
    if any(file_sha256(source_root / name) != digest for name, digest in source_hashes.items()):
        raise IntegrityError("source artifacts changed during the reliability run")
    return {"run_id": public["run_id"], "trials": len(runs), "source_run_id": manifest["run_id"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--repetitions", type=int, default=200, help="Use 200 for the full registered stress run"
    )
    args = parser.parse_args()
    try:
        result = build_reliability(
            args.source_bundle,
            args.output,
            repetitions=args.repetitions,
            progress=lambda s: print(s, flush=True),
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"Reliability run stopped: {error}\n")
    print(
        f"Reliability run {result['run_id']}: {result['trials']} trials "
        f"ready at {args.output.resolve()}"
    )


if __name__ == "__main__":
    main()
