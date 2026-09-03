"""Artifact-only UI: no training, sealed-file reads or oracle joins."""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from reliability_view import reliability_view

from blindspot.contracts import IntegrityError
from blindspot.dashboard_data import read_artifact

SCREENS = ("1. Blocked payments", "2. Check a sample", "3. Can we trust the result?")
POLICIES = {
    "uniform": "Equal chance for every payment",
    "margin_weighted": "More checks near the cutoff",
}
ROOT = Path(__file__).resolve().parents[1]


def percent(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.1%}"


def evidence_notice(case: dict, observed: bool) -> None:
    if not observed:
        st.info(
            "We have not shown any review results yet. Turn on Show review results to see "
            "the selected sample. The other payments stay unknown."
        )
    elif not case["estimate"]["stable"]:
        st.warning("Not enough evidence for a dependable estimate. Do not rely on this number yet.")
        with st.expander("Why is this result uncertain?"):
            for warning in case["estimate"]["warnings"]:
                st.write(warning)
    else:
        st.caption("An estimate from a sample, not an exact count. The 95% range is approximate.")


def overview(manifest: dict, case: dict, observed: bool, benchmark: dict | None) -> None:
    st.header("Were good payments blocked?")
    st.write(
        "The model blocked these payments. Its decision is visible. "
        "Whether each payment was actually legitimate is not."
    )
    total = manifest["declines"]
    count = case["realized"] if observed else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Blocked payments", f"{total:,}")
    c2.metric("Review results shown", f"{count:,}")
    c3.metric("Still unknown", f"{total - count:,}")
    evaluated = manifest["split"]["row_counts"]["evaluation"]
    st.caption(f"{evaluated:,} evaluated payments · {total / evaluated:.2%} declined")
    st.divider()
    evidence_notice(case, observed)
    estimate = case["estimate"]
    usable = observed and case["realized"] > 0
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("How many blocked payments were fraud?")
        st.caption("The share of blocked payments that were genuinely fraudulent.")
        st.metric(
            "Estimated fraud share",
            percent(estimate["block_precision"]) if usable else "Not established",
        )
        if observed:
            low, high = estimate["block_precision_ci"]
            st.write(f"Estimated range: **{low:.1%}–{high:.1%}**")
            if estimate["interval_method"] == "uninformative_fallback":
                st.caption("A 0–100% range means this sample tells us too little.")
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
                    x=alt.X(
                        "lower:Q",
                        title="Fraud share of blocked payments",
                        axis=alt.Axis(format="%"),
                    ),
                    x2="upper:Q",
                )
                point = base.mark_point(filled=True, size=130, color="#12344d").encode(x="point:Q")
                st.altair_chart((interval + point).properties(height=100), width="stretch")
        st.caption(
            "Blocking a payment does not prove it was fraud. "
            "The technical name for this share is block precision."
        )
    with right:
        st.subheader("How many good payments were blocked?")
        st.caption("These are called false declines: legitimate payments blocked by the model.")
        st.metric(
            "Estimated count",
            f"{estimate['false_decline_total']:,.1f}" if usable else "Not established",
        )
        if observed:
            low, high = estimate["false_decline_total_ci"]
            st.write(f"Estimated range: **{low:,.1f}–{high:,.1f} payments**")
            with st.expander("How the estimate works"):
                st.write(
                    "Some payments get picked more often. We account for each payment's "
                    "chance of being picked before estimating the whole group."
                )
                st.caption(
                    f"Effective sample size: {estimate['effective_sample_size']:.1f}. "
                    "Method: inverse-probability weighting; approximate 95% design interval."
                )
    if benchmark is not None:
        st.divider()
        st.subheader("Answer key · for this experiment only")
        st.caption(
            "Known historical labels let us check the experiment. "
            "A live audit would not have this full answer key."
        )
        c1, c2 = st.columns(2)
        c1.metric(
            "Actual fraud share in this experiment", percent(benchmark["oracle"]["block_precision"])
        )
        c2.metric("Actual good payments blocked", f"{benchmark['oracle']['false_declines']:,}")


def queue_view(root: Path, key: str, case: dict, observed: bool) -> None:
    st.header("Check a few. Learn about the whole group.")
    st.write(
        "Every blocked payment had a chance of being picked. "
        "We chose the review list before looking at the answers."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Planned reviews · on average", f"{case['expected_budget']:.2f}")
    c2.metric("Payments picked this time", f"{case['realized']:,}")
    c3.metric(
        "Good payments found in this sample",
        percent(case["discovery_precision"]) if observed else "Hidden",
    )
    st.caption(
        "This percentage describes the reviewed sample, not all blocked payments. "
        "The number picked varies because selection is random."
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
            "risk_score": "Model risk score",
            "priority": "Sampling weight",
            "propensity": "Chance of being picked",
        }
    )
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Chance of being picked": st.column_config.NumberColumn(
                format="%.4f", help="0.05 means a 5% chance. Used to correct the estimate."
            ),
            "Model risk score": st.column_config.NumberColumn(format="%.3f"),
            "Amount (CU)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    if display.empty:
        st.info("No payments in this view. An empty sample gives us no review evidence.")
    st.download_button(
        "Download this queue", display.to_csv(index=False), "verification-queue.csv", "text/csv"
    )
    with st.expander("Proof that the review list was fixed"):
        st.write(f"Pre-registered display seed: {case['seed']}")
        st.code(case["commitment"], language=None)
        st.caption("SHA-256 fingerprint detects changed bytes; not authenticated security.")


def economics(case: dict, observed: bool) -> None:
    with st.expander("What could this cost? · assumptions, not money saved"):
        st.caption(
            "CU means the dataset's currency units, not rupees. These are what-if calculations, "
            "not measured savings. No payment is approved here."
        )
        margin = st.slider("Assumed profit share on a good payment (%)", 0, 100, 10) / 100
        cost = st.number_input("Cost per review (CU)", min_value=0.0, value=1.0)
        loss = st.slider("Fraud loss if approved (%)", 0, 100, 100) / 100
        exposure = (
            st.slider("Reviews that would require approving the payment (%)", 0, 100, 100) / 100
        )
        c1, c2, c3 = st.columns(3)
        amount = case["false_decline_amount"]
        c1.metric(
            "Estimated profit at risk (CU)",
            f"{amount['point'] * margin:,.2f}" if observed and case["realized"] else "Unknown",
        )
        c2.metric("Estimated review cost (CU)", f"{case['realized'] * cost:,.2f}")
        c3.metric(
            "Possible fraud loss during reviews (CU)",
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
    st.header("Can we trust the result?")
    st.write(
        "Compare two ways of choosing reviews, then see what happens "
        "when answers are late or wrong."
    )
    if benchmark is None:
        st.info(
            "Turn on Show experiment answer key to compare the estimates with known answers. "
            "This checks our experiment; it is not information a live audit would have."
        )
    else:
        summary = pd.DataFrame(benchmark["summary"])
        summary["method"] = summary.policy.map(POLICIES)
        diagnostics = st.checkbox("Show larger test budgets above 5%", value=False)
        if not diagnostics:
            summary = summary.loc[summary.budget_rate <= 0.05]
        st.caption(
            f"Each setting was repeated {manifest['sweep_config']['repetitions']} times "
            "on the same group. "
            "Every run is included, even empty or unreliable samples."
        )
        metrics = {
            "rmse_pp": "How far estimates miss · lower is better",
            "ci_width_pp_mean": "How wide the answer range is",
            "coverage": "How often the range contains the answer",
            "stable_fraction": "How often the sample passes reliability checks",
            "discovery_recall_mean": "Share of all good blocked payments found",
        }
        metric = st.selectbox("Compare", list(metrics), format_func=metrics.get)
        st.caption(
            {
                "rmse_pp": (
                    "Measured in percentage points using RMSE, which gives larger mistakes "
                    "more weight. This checks estimates of the fraud share "
                    "among all blocked payments."
                ),
                "ci_width_pp_mean": (
                    "Average width in percentage points. Narrower is useful only if the method "
                    "also includes the answer often enough."
                ),
                "coverage": (
                    "Fraction of repeated runs whose range contains the known answer. "
                    "1 means 100%; even an unhelpful 0–100% range counts."
                ),
                "stable_fraction": (
                    "Fraction passing the sample checks. 1 means 100%; "
                    "passing is not a guarantee that an estimate is correct."
                ),
                "discovery_recall_mean": (
                    "Average fraction of all legitimate blocked payments found by the reviews. "
                    "1 means 100%. We can measure it only because "
                    "this experiment has an answer key."
                ),
            }[metric]
        )
        chart = (
            alt.Chart(summary)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "budget_rate:Q",
                    title="Share of blocked payments to review · on average",
                    axis=alt.Axis(format="%"),
                ),
                y=alt.Y(f"{metric}:Q", title=metrics[metric]),
                color=alt.Color(
                    "method:N", title="Review method", scale=alt.Scale(range=["#178586", "#d28b29"])
                ),
                tooltip=[
                    "method:N",
                    alt.Tooltip("budget_rate:Q", format=".2%"),
                    alt.Tooltip(f"{metric}:Q", format=".4f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, width="stretch")
        st.warning(
            "A range from 0% to 100% includes every possible answer—but tells us nothing useful. "
            "Check both the size of the range and how often it contains the answer."
        )
        current = summary.loc[summary.budget_rate == case["budget_rate"]]
        if current.empty:
            st.caption(
                "The selected budget is diagnostic. Enable diagnostic budgets to see it here."
            )
        else:
            st.subheader(f"When reviewing {case['budget_rate']:.2%} of blocked payments on average")
            st.dataframe(
                current[
                    [
                        "method",
                        "realized_mean",
                        "rmse_pp",
                        "ci_width_pp_mean",
                        "discovery_precision_mean",
                    ]
                ]
                .assign(discovery_precision_mean=lambda frame: frame.discovery_precision_mean * 100)
                .rename(
                    columns={
                        "method": "Review method",
                        "realized_mean": "Average reviews",
                        "rmse_pp": "Estimate error (pp)",
                        "ci_width_pp_mean": "Range width (pp)",
                        "discovery_precision_mean": "Good payments in sample (%)",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
        with st.expander("Technical details · full comparison and downloads"):
            st.dataframe(pd.DataFrame(benchmark["summary"]), hide_index=True, width="stretch")
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
    st.caption(
        "Find out whether good payments are being blocked. Help a risk team decide what to review."
    )
    real_bundle = ROOT / "artifacts/ieee-full-2026-09-03"
    default_bundle = (
        real_bundle
        if (real_bundle / "checksums.json").is_file()
        else (ROOT / "artifacts/synthetic-2026-09-02")
    )
    root = Path(os.environ.get("BLINDSPOT_RUN_DIR", str(default_bundle)))
    try:
        manifest = read_artifact(root, "manifest.json")
        public = read_artifact(root, "public.json")
    except (OSError, ValueError, IntegrityError) as error:
        st.error("A complete, integrity-checked experiment bundle is required.")
        st.code("blindspot-benchmark --source synthetic --output artifacts/synthetic-2026-09-02")
        st.caption(f"Run directory: {root}. {error}")
        return
    st.info(
        "Historical IEEE-CIS data · payment blocking is simulated, not live Razorpay traffic."
        if manifest["source"]["kind"] == "ieee-cis"
        else "Generated test data · these are not real customer payments."
    )
    st.sidebar.title("Explore BlindSpot")
    screen = st.sidebar.radio("Screen", SCREENS)
    st.sidebar.divider()
    policy = st.sidebar.selectbox("How to choose reviews", list(POLICIES), format_func=POLICIES.get)
    rates = manifest["sweep_config"]["budget_rates"]
    rate = st.sidebar.selectbox(
        "Share to review · on average",
        rates,
        index=rates.index(0.05) if 0.05 in rates else 0,
        format_func=lambda value: f"{value:.2%}" + (" · larger test" if value > 0.05 else ""),
    )
    key = f"{policy}:{rate:.8g}"
    case = public["cases"][key]
    st.sidebar.caption(
        f"About {case['expected_budget']:.1f} reviews planned. The actual count can vary."
    )
    observed = st.sidebar.toggle("Show review results", value=False)
    reveal_oracle = st.sidebar.toggle("Show experiment answer key", value=False)
    st.sidebar.caption(
        "For this demo only: these switches show or hide information; "
        "they are not security controls."
    )
    try:
        benchmark = read_artifact(root, "benchmark.json") if reveal_oracle else None
        if screen == SCREENS[0]:
            overview(manifest, case, observed, benchmark)
        elif screen == SCREENS[1]:
            queue_view(root, key, case, observed)
        else:
            budget_lab(manifest, case, observed, benchmark)
            reliability_view(root, case, observed, reveal_oracle)
    except (OSError, ValueError, IntegrityError) as error:
        st.error(f"Evidence could not be loaded: {error}")
    st.divider()
    with st.expander("How this was tested · data, methods and limits"):
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
