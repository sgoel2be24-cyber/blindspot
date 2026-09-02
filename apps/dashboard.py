"""Artifact-only UI: no training, sealed-file reads or oracle joins."""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from blindspot.contracts import IntegrityError
from blindspot.dashboard_data import read_artifact

SCREENS = ("Blind Region Overview", "Verification Queue", "Budget Lab")
POLICIES = {"uniform": "Uniform random", "margin_weighted": "BlindSpot · margin-weighted"}
ROOT = Path(__file__).resolve().parents[1]


def percent(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.1%}"


def evidence_notice(case: dict, observed: bool) -> None:
    if not observed:
        st.info(
            "Outcomes are hidden. Reveal verified-sample evidence in the sidebar to inspect "
            "only the committed sample. Unselected outcomes remain hidden."
        )
    elif not case["estimate"]["stable"]:
        st.warning(
            "Insufficient evidence for a dependable estimate: "
            + "; ".join(case["estimate"]["warnings"])
            + "."
        )
    else:
        st.caption("Sample-based estimate · approximate 95% design interval · not a guarantee")


def overview(manifest: dict, case: dict, observed: bool, benchmark: dict | None) -> None:
    st.header("What happened inside the blind region?")
    st.write(
        "The model blocked these payments. Its decision is visible. "
        "Whether each payment was actually legitimate is not."
    )
    total = manifest["declines"]
    count = case["realized"] if observed else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Declined payments", f"{total:,}")
    c2.metric("Verified outcomes revealed", f"{count:,}")
    c3.metric("Still unobserved", f"{total - count:,}")
    evaluated = manifest["split"]["row_counts"]["evaluation"]
    st.caption(f"{evaluated:,} evaluated payments · {total / evaluated:.2%} declined")
    st.divider()
    evidence_notice(case, observed)
    estimate = case["estimate"]
    usable = observed and case["realized"] > 0
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Block precision")
        st.caption("The share of declined payments that were genuinely fraudulent.")
        st.metric(
            "Corrected estimate",
            percent(estimate["block_precision"]) if usable else "Not established",
        )
        if observed:
            low, high = estimate["block_precision_ci"]
            st.write(f"Interval: **{low:.1%}–{high:.1%}**")
            if estimate["interval_method"] == "uninformative_fallback":
                st.caption("Full-range fallback: this sample cannot support a useful interval.")
            if usable:
                data = pd.DataFrame(
                    [
                        {
                            "measure": "Estimate",
                            "point": estimate["block_precision"],
                            "lower": low,
                            "upper": high,
                        }
                    ]
                )
                base = alt.Chart(data).encode(y=alt.Y("measure:N", title=None))
                interval = base.mark_rule(strokeWidth=5, color="#157c80").encode(
                    x=alt.X("lower:Q", title="Block precision", axis=alt.Axis(format="%")),
                    x2="upper:Q",
                )
                point = base.mark_point(filled=True, size=130, color="#12344d").encode(x="point:Q")
                st.altair_chart((interval + point).properties(height=100), width="stretch")
        else:
            st.write("A decline is a decision—not proof of fraud.")
        st.caption(
            "Naive policy assumption: 100% of declines are fraud. "
            "This is an illustrative assumption, not a measured result or industry claim."
        )
    with right:
        st.subheader("False declines")
        st.caption("Legitimate payments that the incumbent model blocked.")
        st.metric(
            "Estimated count",
            f"{estimate['false_decline_total']:,.1f}" if usable else "Not established",
        )
        if observed:
            low, high = estimate["false_decline_total_ci"]
            st.write(f"Interval: **{low:,.1f}–{high:,.1f} payments**")
            st.caption(
                f"Effective sample size: {estimate['effective_sample_size']:.1f}. "
                "Unequal selection probabilities are corrected with inverse-probability weights."
            )
    if benchmark is not None:
        st.divider()
        st.subheader("Offline answer key")
        st.caption("Evaluator-only aggregate truth. Not available to a live verifier.")
        c1, c2 = st.columns(2)
        c1.metric("True block precision", percent(benchmark["oracle"]["block_precision"]))
        c2.metric("True false declines", f"{benchmark['oracle']['false_declines']:,}")


def queue_view(root: Path, key: str, case: dict, observed: bool) -> None:
    st.header("A randomized queue. A traceable decision.")
    st.write(
        "Every declined payment had a non-zero chance of verification. "
        "The queue was fixed before outcomes were revealed."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Expected verifications", f"{case['expected_budget']:.2f}")
    c2.metric("Realized queue", f"{case['realized']:,}")
    c3.metric("Discovery precision", percent(case["discovery_precision"]) if observed else "Hidden")
    st.caption(
        "Discovery precision is the legitimate share of this sample—not population block "
        "precision. Realized spend fluctuates around its expectation."
    )
    evidence_notice(case, observed)
    if observed:
        low, high = case["estimate"]["block_precision_ci"]
        st.caption(
            f"Before evidence: full 0–100% range. After this sample: {low:.1%}–{high:.1%}. "
            "Evidence is revealed as one batch, not a live stream."
        )
    columns = [
        "row_id",
        "transaction_id",
        "transaction_amount",
        "risk_score",
        "priority",
        "propensity",
    ]
    table = pd.DataFrame(case["queue"], columns=columns)
    if observed:
        labels = pd.DataFrame(
            read_artifact(root, "observations.json")["cases"][key], columns=["row_id", "is_fraud"]
        )
        table = table.merge(labels, on="row_id", validate="one_to_one", how="left")
        table["Evidence"] = table.pop("is_fraud").map({0: "Legitimate · false decline", 1: "Fraud"})
    else:
        table["Evidence"] = "Not revealed"
    query = st.text_input("Find a transaction", placeholder="Transaction ID")
    if query:
        table = table.loc[table.transaction_id.astype(str).str.contains(query, regex=False)]
    display = table.drop(columns="row_id").rename(
        columns={
            "transaction_id": "Transaction",
            "transaction_amount": "Amount (CU)",
            "risk_score": "Incumbent risk score",
            "priority": "Sampling weight",
            "propensity": "Selection probability",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Selection probability": st.column_config.NumberColumn(format="%.4f"),
            "Incumbent risk score": st.column_config.NumberColumn(format="%.3f"),
            "Amount (CU)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    if display.empty:
        st.info(
            "No cases in this view. An empty randomized sample is a valid outcome, not success."
        )
    st.download_button(
        "Download this queue", display.to_csv(index=False), "verification-queue.csv", "text/csv"
    )
    with st.expander("Selection receipt"):
        st.write(f"Pre-registered display seed: {case['seed']}")
        st.code(case["commitment"], language=None)
        st.caption("SHA-256 fingerprint detects changed bytes; not authenticated security.")


def economics(case: dict, observed: bool) -> None:
    with st.expander("Economics · assumptions, not realized savings"):
        st.caption("CU means generic currency units, not INR. No payment is approved by this demo.")
        margin = st.slider("Merchant contribution margin (%)", 0, 100, 10) / 100
        cost = st.number_input("Verification cost per case (CU)", min_value=0.0, value=1.0)
        loss = st.slider("Fraud loss if approved (%)", 0, 100, 100) / 100
        exposure = st.slider("Verification requiring approval (%)", 0, 100, 100) / 100
        c1, c2, c3 = st.columns(3)
        amount = case["false_decline_amount"]
        c1.metric(
            "Estimated margin at risk (CU)",
            f"{amount['point'] * margin:,.2f}" if observed and case["realized"] else "Unknown",
        )
        c2.metric("Modeled queue cost (CU)", f"{case['realized'] * cost:,.2f}")
        c3.metric(
            "Modeled fraud exposure (CU)",
            f"{case['selected_fraud_amount'] * loss * exposure:,.2f}" if observed else "Unknown",
        )
        if observed:
            st.caption(
                f"False-decline amount interval: {amount['ci_lower']:,.2f}–"
                f"{amount['ci_upper']:,.2f} CU. Margin at risk is not recovered revenue."
            )
            if not case["estimate"]["stable"]:
                st.warning(
                    "The sample estimate is unstable; economic point estimates are also unreliable."
                )


def budget_lab(manifest: dict, case: dict, observed: bool, benchmark: dict | None) -> None:
    st.header("What does more evidence buy?")
    st.write("Compare uniform and margin-weighted sampling at the same expected budget.")
    if benchmark is None:
        st.info(
            "Reveal the offline benchmark in the sidebar to inspect error, coverage and "
            "recall. These require an answer key that a live product does not have."
        )
    else:
        summary = pd.DataFrame(benchmark["summary"])
        diagnostics = st.checkbox("Include diagnostic budgets above 5%", value=False)
        if not diagnostics:
            summary = summary.loc[summary.budget_rate <= 0.05]
        st.caption(
            f"{manifest['sweep_config']['repetitions']} consecutive seeds per setting · "
            "one frozen population · all empty and unstable draws included · lower RMSE is better"
        )
        metrics = {
            "rmse_pp": "Estimation error · RMSE (percentage points)",
            "ci_width_pp_mean": "Mean interval width (percentage points)",
            "coverage": "Interval coverage (including full-range fallbacks)",
            "stable_fraction": "Fraction passing stability checks",
            "discovery_recall_mean": "Discovery recall · offline only",
        }
        metric = st.selectbox("Compare", list(metrics), format_func=metrics.get)
        chart = (
            alt.Chart(summary)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "budget_rate:Q", title="Expected budget / declines", axis=alt.Axis(format="%")
                ),
                y=alt.Y(f"{metric}:Q", title=metrics[metric]),
                color=alt.Color(
                    "policy:N", title="Policy", scale=alt.Scale(range=["#178586", "#d28b29"])
                ),
                tooltip=[
                    "policy:N",
                    alt.Tooltip("budget_rate:Q", format=".2%"),
                    alt.Tooltip(f"{metric}:Q", format=".4f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, width="stretch")
        st.warning(
            "Coverage alone can mislead: a full-range interval always covers the truth but "
            "learns nothing. Read it alongside interval width, fallback rate and stability."
        )
        current = summary.loc[summary.budget_rate == case["budget_rate"]]
        if current.empty:
            st.caption(
                "The selected budget is diagnostic. Enable diagnostic budgets to see it here."
            )
        else:
            st.subheader(f"At {case['budget_rate']:.2%} expected budget")
            st.dataframe(
                current[
                    [
                        "policy",
                        "expected_budget",
                        "realized_mean",
                        "rmse_pp",
                        "theoretical_se_pp",
                        "coverage",
                        "coverage_mc_lower",
                        "coverage_mc_upper",
                        "stable_fraction",
                        "fallback_fraction",
                        "discovery_precision_mean",
                        "discovery_recall_mean",
                    ]
                ],
                hide_index=True,
                width="stretch",
            )
        with st.expander("Paired comparison and all results"):
            st.caption(
                "Squared-error difference: weighted minus uniform. Negative favors weighted; "
                "an interval crossing zero is inconclusive. These Monte Carlo intervals are "
                "approximate and conditional on this one population."
            )
            st.dataframe(
                pd.DataFrame(benchmark["paired_comparison"]), hide_index=True, width="stretch"
            )
            st.download_button(
                "Download all summary results",
                pd.DataFrame(benchmark["summary"]).to_csv(index=False),
                "benchmark-summary.csv",
                "text/csv",
            )
    economics(case, observed)


def main() -> None:
    st.set_page_config(page_title="BlindSpot · Risk verification", page_icon="◉", layout="wide")
    st.markdown(
        """<style>
    .stApp {background: #f7f9fb; color: #18354b;}
    [data-testid="stSidebar"] {background: #eef3f6;}
    [data-testid="stMetric"] {background: white; border: 1px solid #dce6ed;
      padding: 18px; border-radius: 12px;}
    h1, h2, h3 {letter-spacing: -0.025em;}
    .block-container {padding-top: 2.2rem; max-width: 1400px;}
    </style>""",
        unsafe_allow_html=True,
    )
    st.title("◉ BlindSpot")
    st.caption("AI RISK MANAGER  /  VERIFICATION, NOT AUTOMATED APPROVAL")
    root = Path(os.environ.get("BLINDSPOT_RUN_DIR", str(ROOT / "artifacts/synthetic-2026-09-02")))
    try:
        manifest = read_artifact(root, "manifest.json")
        public = read_artifact(root, "public.json")
    except (OSError, ValueError, IntegrityError) as error:
        st.error("A complete, integrity-checked experiment bundle is required.")
        st.code("blindspot-benchmark --source synthetic --output artifacts/synthetic-2026-09-02")
        st.caption(f"Run directory: {root}. {error}")
        return
    st.info(manifest["source"]["label"])
    st.sidebar.title("Experiment console")
    screen = st.sidebar.radio("Screen", SCREENS)
    st.sidebar.divider()
    policy = st.sidebar.selectbox("Verification policy", list(POLICIES), format_func=POLICIES.get)
    rates = manifest["sweep_config"]["budget_rates"]
    rate = st.sidebar.selectbox(
        "Expected verification budget",
        rates,
        index=rates.index(0.05) if 0.05 in rates else 0,
        format_func=lambda value: f"{value:.2%}" + (" · diagnostic" if value > 0.05 else ""),
    )
    key = f"{policy}:{rate:.8g}"
    case = public["cases"][key]
    st.sidebar.caption(f"{case['expected_budget']:.2f} expected cases · seed {case['seed']}")
    observed = st.sidebar.toggle("Reveal verified-sample evidence", value=False)
    reveal_oracle = st.sidebar.toggle("Reveal offline benchmark", value=False)
    st.sidebar.caption("Reveal controls the display only; it is not an access-control system.")
    try:
        benchmark = read_artifact(root, "benchmark.json") if reveal_oracle else None
        if screen == SCREENS[0]:
            overview(manifest, case, observed, benchmark)
        elif screen == SCREENS[1]:
            queue_view(root, key, case, observed)
        else:
            budget_lab(manifest, case, observed, benchmark)
    except (OSError, ValueError, IntegrityError) as error:
        st.error(f"Evidence could not be loaded: {error}")
    st.divider()
    with st.expander("Run provenance & limitations"):
        st.write(f"Run {manifest['run_id']} · {manifest['rows']:,} input rows")
        st.json(
            {
                "source": manifest["source"],
                "split": manifest["split"],
                "incumbent_calibration": manifest["calibration_metrics"],
                "versions": manifest["versions"],
                "sweep": manifest["sweep_config"],
            }
        )
        for limitation in manifest["limitations"]:
            st.caption(limitation)


if __name__ == "__main__":
    main()
