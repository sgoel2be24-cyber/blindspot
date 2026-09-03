from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from blindspot.benchmark import build_benchmark, file_sha256
from blindspot.contracts import IntegrityError
from blindspot.dashboard_data import read_artifact, read_reliability
from blindspot.evaluation.sweep import SweepConfig
from blindspot.experiment.pipeline import ExperimentConfig
from blindspot.model.incumbent import IncumbentConfig
from blindspot.reliability import SCENARIOS, build_reliability, simulate_potential_evidence


@pytest.fixture
def reliability_bundle(tmp_path, synthetic_transactions):
    source = tmp_path / "source"
    output = tmp_path / "reliability"
    build_benchmark(
        synthetic_transactions,
        output=source,
        source={"kind": "synthetic", "label": "Synthetic test fixture"},
        experiment_config=ExperimentConfig(
            incumbent=IncumbentConfig(max_iter=10, min_samples_leaf=8),
            target_decline_rate=0.3,
        ),
        sweep_config=SweepConfig(budget_rates=(0.05,), repetitions=2),
    )
    build_reliability(source, output, repetitions=2, rates=(0.05,))
    return source, output


def test_reliability_preserves_scenarios_seeds_commitments_and_replays(
    reliability_bundle, tmp_path
):
    source, output = reliability_bundle
    replay = tmp_path / "replay"
    build_reliability(source, replay, repetitions=2, rates=(0.05,))
    assert (output / "checksums.json").read_bytes() == (replay / "checksums.json").read_bytes()
    runs = pd.read_csv(output / "stress_runs.csv")
    assert len(runs) == 32
    assert runs.groupby(["policy", "seed"]).commitment.nunique().eq(1).all()
    assert set(runs.scenario) == {s.name for s in SCENARIOS}
    assert all(set(g.seed) == {1729, 1730} for _, g in runs.groupby(["scenario", "policy"]))
    unknown = runs.loc[runs.scenario == "delay_day_1"]
    assert unknown.lower.eq(0).all() and unknown.upper.eq(1).all()
    assert unknown.naive_completed_only_bp.isna().all()
    with pytest.raises(FileExistsError):
        build_reliability(source, output, repetitions=2, rates=(0.05,))
    (source / "sealed/truth.csv").unlink()
    artifact = read_reliability(output, source)
    assert "oracle_block_precision" not in artifact
    assert all("queue" not in case for case in artifact["cases"].values())
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["rows"] += 1
    (source / "manifest.json").write_text(json.dumps(manifest))
    hashes = json.loads((source / "checksums.json").read_text())
    hashes["manifest.json"] = file_sha256(source / "manifest.json")
    (source / "checksums.json").write_text(json.dumps(hashes))
    with pytest.raises(IntegrityError, match="different source"):
        read_reliability(output, source)
    (output / "reliability.json").write_text("{}")
    with pytest.raises(IntegrityError, match="hash mismatch"):
        read_artifact(output, "reliability.json")


def test_potential_evidence_is_order_invariant_and_fixed_before_selection():
    truth = pd.DataFrame({"row_id": [f"r{i:03}" for i in range(100)], "is_fraud": [0, 1] * 50})
    for scenario in SCENARIOS:
        first = simulate_potential_evidence(truth, scenario)
        shuffled = simulate_potential_evidence(truth.sample(frac=1, random_state=8), scenario)
        pd.testing.assert_frame_equal(first, shuffled)
    noisy = simulate_potential_evidence(truth, SCENARIOS[-2])
    assert (noisy.evidence_is_fraud.to_numpy() != truth.is_fraud.to_numpy()).sum() == 5


def test_dashboard_reliability_reveals_and_pending_state(reliability_bundle, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    source, output = reliability_bundle
    monkeypatch.setenv("BLINDSPOT_RUN_DIR", str(source))
    monkeypatch.setenv("BLINDSPOT_RELIABILITY_DIR", str(output))
    app = AppTest.from_file(
        str(Path(__file__).parents[2] / "apps/dashboard.py"), default_timeout=15
    ).run()
    assert not app.exception
    app.sidebar.radio[0].set_value("3. Can we trust the result?").run()
    assert not any(w.label == "Try an example" for w in app.selectbox)
    app.sidebar.toggle[0].set_value(True).run()
    assert not app.exception
    next(w for w in app.selectbox if w.label == "Try an example").set_value("delay_day_1").run()
    assert any(m.value == "0.0%–100.0%" for m in app.metric)
    assert any("Not enough evidence" in w.value for w in app.warning)
    assert any(m.label == "Still waiting · not ignored" for m in app.metric)
    assert not app.dataframe
    app.sidebar.toggle[1].set_value(True).run()
    assert not app.exception
    assert app.dataframe
    next(w for w in app.selectbox if w.label == "Try an example").set_value(
        "noise_unacknowledged"
    ).run()
    assert app.error
