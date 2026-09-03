from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from blindspot.benchmark import build_benchmark
from blindspot.contracts import IntegrityError
from blindspot.dashboard_data import read_artifact
from blindspot.evaluation.sweep import SweepConfig, run_budget_sweep
from blindspot.experiment.pipeline import ExperimentConfig
from blindspot.model.incumbent import IncumbentConfig


@pytest.fixture
def small_pool():
    size = 40
    pool = pd.DataFrame(
        {
            "row_id": [f"row-{i:03}" for i in range(size)],
            "transaction_id": np.arange(size),
            "transaction_dt": np.arange(size),
            "transaction_amount": np.full(size, 10.0),
            "risk_score": np.linspace(0.51, 0.99, size),
            "decline_threshold": 0.5,
        }
    )
    truth = pool[["row_id", "transaction_amount"]].assign(is_fraud=np.arange(size) % 3 == 0)
    return pool, truth


def test_sweep_preserves_all_seeds_empty_draws_and_exact_budgets(small_pool):
    pool, truth = small_pool
    config = SweepConfig(budget_rates=(0.00001, 1.0), repetitions=4)
    result = run_budget_sweep(pool, truth, config)
    assert len(result.runs) == 16
    assert result.summary.repetitions.eq(4).all()
    tiny = result.runs.loc[result.runs.budget_rate == 0.00001]
    assert np.allclose(tiny.expected_budget, 0.0004)
    assert tiny.realized.eq(0).all()
    assert tiny.interval_method.eq("uninformative_fallback").all()
    for case in result.displays.values():
        if case["budget_rate"] == 0.00001:
            assert case["false_decline_amount"]["ci_upper"] == 400
    census = result.runs.loc[result.runs.budget_rate == 1]
    assert census.stable.all()
    assert np.allclose(census.error_pp, 0)
    assert census.theoretical_se_pp.eq(0).all()


def test_sweep_replays_under_shuffle_and_does_not_select_using_truth(small_pool):
    pool, truth = small_pool
    config = SweepConfig(budget_rates=(0.25,), repetitions=4)
    first = run_budget_sweep(pool, truth, config)
    replay = run_budget_sweep(pool.sample(frac=1, random_state=9), truth, config)
    pd.testing.assert_frame_equal(first.runs, replay.runs)
    changed = run_budget_sweep(pool, truth.assign(is_fraud=1 - truth.is_fraud.astype(int)), config)
    assert first.runs.commitment.equals(changed.runs.commitment)
    assert not first.runs.estimate_bp.equals(changed.runs.estimate_bp)
    for key, case in first.displays.items():
        assert {r["row_id"] for r in first.observations[key]} == {
            r["row_id"] for r in case["queue"]
        }
        assert all("is_fraud" not in row for row in case["queue"])


@pytest.fixture
def bundle(tmp_path, synthetic_transactions):
    output = tmp_path / "bundle"
    build_benchmark(
        synthetic_transactions,
        output=output,
        source={"kind": "synthetic", "label": "Synthetic test fixture"},
        experiment_config=ExperimentConfig(
            incumbent=IncumbentConfig(max_iter=10, min_samples_leaf=8),
            target_decline_rate=0.3,
        ),
        sweep_config=SweepConfig(budget_rates=(0.00001, 0.5), repetitions=2),
    )
    return output


def test_bundle_verifies_integrity_and_does_not_require_sealed_files(bundle):
    # Simulate deploying only approved dashboard exports, without any oracle file.
    (bundle / "sealed" / "truth.csv").unlink()
    public = read_artifact(bundle, "public.json")
    assert "oracle" not in public
    for forbidden in ("sealed/truth.csv", "../truth.csv", "runs.csv"):
        with pytest.raises(IntegrityError):
            read_artifact(bundle, forbidden)
    (bundle / "public.json").write_text('{"cases": {}}')
    with pytest.raises(IntegrityError, match="hash mismatch"):
        read_artifact(bundle, "public.json")


def test_bundle_refuses_overwrite(bundle, synthetic_transactions):
    with pytest.raises(FileExistsError):
        build_benchmark(synthetic_transactions, output=bundle, source={"kind": "synthetic"})


def test_dashboard_cannot_import_evaluator_or_experiment():
    root = Path(__file__).parents[2]
    paths = [*sorted((root / "apps").glob("*.py")), root / "src/blindspot/dashboard_data.py"]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("blindspot.evaluation", "blindspot.experiment")
                )
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(("blindspot.evaluation", "blindspot.experiment"))
                    for alias in node.names
                )


def test_dashboard_all_screens_controls_and_empty_sample(bundle, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("BLINDSPOT_RUN_DIR", str(bundle))
    app = AppTest.from_file(
        str(Path(__file__).parents[2] / "apps/dashboard.py"), default_timeout=15
    ).run()
    assert not app.exception
    assert any(m.value == "Not established" for m in app.metric)
    app.sidebar.toggle[0].set_value(True).run()
    assert not app.exception
    assert app.warning
    assert app.sidebar.radio[0].options == [
        "1. Blocked payments",
        "2. Check a sample",
        "3. Can we trust the result?",
    ]
    assert [toggle.label for toggle in app.sidebar.toggle] == [
        "Show review results",
        "Show experiment answer key",
    ]
    app.sidebar.radio[0].set_value("2. Check a sample").run()
    assert not app.exception
    assert app.dataframe[0].value.empty
    app.sidebar.selectbox[1].select(0.5).run()
    assert not app.exception
    assert set(app.dataframe[0].value.Evidence) <= {"Fraud", "Legitimate · false decline"}
    app.text_input[0].set_value("NONEXISTENT-ID").run()
    assert app.dataframe[0].value.empty
    app.sidebar.radio[0].set_value("3. Can we trust the result?").run()
    assert not app.exception
    assert not app.dataframe
    app.sidebar.toggle[1].set_value(True).run()
    assert not app.exception
    app.checkbox[0].set_value(True).run()
    assert not app.exception
    app.slider[0].set_value(20).run()
    assert not app.exception
