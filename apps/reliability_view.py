"""Aggregate-only evidence reliability view inside the existing Budget Lab."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from blindspot.dashboard_data import read_artifact, read_reliability


def reliability_view(source_root: Path, case: dict, observed: bool, oracle_revealed: bool) -> None:
    st.divider()
    st.subheader("What if review answers are late or wrong?")
    st.caption(
        "Simulated examples, not a live review feed. "
        "We change the available answers, not the original model."
    )
    directory = Path(os.environ.get("BLINDSPOT_RELIABILITY_DIR", str(source_root) + "-reliability"))
    if not directory.exists():
        st.info("Build the optional reliability bundle to inspect pending and incorrect evidence.")
        st.code(
            f"python -m blindspot.reliability --source-bundle '{source_root}' "
            f"--output '{directory}'"
        )
        return
    if not observed:
        st.info("Turn on Show review results to try these examples.")
        return
    artifact = read_reliability(directory, source_root)
    scenarios = artifact["design"]["scenarios"]
    labels = {
        "perfect": "All answers arrive and are correct",
        "missing_30": "30% of answers are missing at random",
        "missing_selective": "Fraud answers are more likely to be missing",
        "delay_day_1": "Late answers: day 1",
        "delay_day_7": "Late answers: day 7",
        "delay_day_30": "Late answers: day 30",
        "noise_5": "5% of answers are wrong, and we allow for it",
        "noise_unacknowledged": "5% are wrong, but we wrongly assume none are",
    }
    names = {item["name"]: labels.get(item["name"], item["label"]) for item in scenarios}
    scenario_name = st.selectbox("Try an example", list(names), format_func=names.get)
    key = f"{scenario_name}:{case['policy']}:{case['budget_rate']:.8g}"
    if key not in artifact["cases"]:
        st.info(
            "Reliability tests cover the five primary budgets up to 5%, not diagnostic budgets."
        )
        return
    display = artifact["cases"][key]
    bounds, scenario = display["bounds"], display["scenario"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Reviews requested", bounds["selected"])
    c2.metric("Answers received", bounds["resolved"])
    c3.metric("Still waiting · not ignored", bounds["pending"])
    lower, upper = bounds["block_precision_lower"], bounds["block_precision_upper"]
    st.metric("Fraud share of all blocked payments · supported range", f"{lower:.1%}–{upper:.1%}")
    st.caption(
        "This 95% range allows for missing answers under the assumptions below. "
        "A wide range means we still know little. It is not a guarantee."
    )
    epsilon = bounds["assumed_population_error_fraction"]
    st.write(
        f"**Assumption: at most {epsilon:.0%} of all blocked payments would have a wrong "
        "completed review answer.**"
    )
    st.caption(
        "This assumption must be checked independently. It covers the whole group, "
        "including payments not picked for review."
    )
    target = st.slider("Target fraud share among blocked payments (%)", 1, 99, 50) / 100
    st.caption(
        "An example target for comparing the blocking rule, not a recommended operating target."
    )
    if not scenario["assumptions_valid"]:
        status = "The assumption is wrong — do not trust this range"
        st.error(
            "We deliberately ignored known wrong answers in this example. "
            "Do not trust this range: its stated confidence no longer applies."
        )
    elif upper < target:
        status = "Below target — ask the risk team to review the blocking rule"
        st.warning(status)
    elif lower >= target:
        status = "Meets the target — if these assumptions hold"
        st.success(status)
    else:
        status = "Not enough evidence — keep reviewing before reaching a conclusion"
        st.warning(status)
    st.caption("A person decides what to do next. BlindSpot does not approve or block payments.")
    naive = bounds["completed_only_block_precision"]
    st.write(
        "**If we ignore the missing answers, the fraud estimate is:** "
        + ("unavailable" if naive is None else f"{naive:.1%}")
    )
    st.caption(
        "That shortcut can mislead us. It describes available answers after adjusting for "
        "selection, but does not account for why other answers are missing."
    )
    with st.expander("Technical details · assumptions behind the range"):
        st.write(
            "Bernstein partial-identification bounds with known Bernoulli selection probabilities "
            "and a whole-population label-error allowance. Potential evidence must be fixed "
            "independently of the random review selection. Availability may depend on truth, "
            "but not on which queue was drawn."
        )
        st.write(
            "These are pointwise 95% bounds for each fixed snapshot, not simultaneous or "
            "anytime-valid bounds. They are separate from the original approximate normal interval."
        )
    receipt = {
        "source_run_id": artifact["design"]["source_run_id"],
        "reliability_run_id": artifact["run_id"],
        "scenario": scenario,
        "policy": display["policy"],
        "budget_rate": display["budget_rate"],
        "display_seed": display["seed"],
        "bounds": bounds,
        "audit_target": target,
        "advisory_status": status,
        "limitations": artifact["limitations"],
    }
    st.download_button(
        "Download review summary",
        json.dumps(receipt, indent=2),
        "blindspot-audit-receipt.json",
        "application/json",
    )
    if oracle_revealed:
        offline = read_artifact(directory, "reliability_benchmark.json")
        st.caption(
            f"Experiment answer key: {offline['oracle_block_precision']:.2%} "
            "of blocked payments were fraud."
        )
        summary = pd.DataFrame(offline["summary"])
        selected = summary.loc[
            (summary.scenario == scenario_name) & (summary.budget_rate == case["budget_rate"])
        ]
        with st.expander(
            f"Technical details · all {artifact['design']['repetitions']} repeated tests per method"
        ):
            st.dataframe(
                selected[
                    [
                        "policy",
                        "resolved_mean",
                        "pending_mean",
                        "mean_width_pp",
                        "coverage",
                        "naive_rmse_pp",
                        "abstention_fraction",
                        "incorrect_decision_fraction",
                    ]
                ],
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Repeated-draw audit-status rates above use the registered 50% target, "
                "not the slider. "
                "Wide ranges can cover truth while offering little precision."
            )
    else:
        st.info("The experiment answer key stays hidden until you turn it on in the sidebar.")
