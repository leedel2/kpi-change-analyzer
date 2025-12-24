# app.py
import streamlit as st
import pandas as pd
import altair as alt
import numpy as np

from analysis.loader import prepare_dataframe, split_periods
from analysis.trend import detect_change_context
from analysis.drivers import calculate_drivers_effects
from analysis.json_builder import build_output_json
from analysis.driver_view import build_driver_summary, build_driver_expansion_text

from ai.driver_summary import summarize_drivers

st.set_page_config(
    page_title="KPI Change Analyzer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("KPI Change Analyzer")
st.caption("Upload your data, pick a KPI, and see what changed and why.")

# Sidebar: upload + settings
with st.sidebar:
    st.header("1. Upload & settings")
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
    example_toggle = st.checkbox("Use example data instead", value=False)

    granularity = st.selectbox("Time granularity", ["day", "week", "month"], index=1)
    use_ai = st.checkbox("Use AI narrative (stub only for now)", value=False)

    run_button = st.button("Run analysis")

# Main area
if example_toggle and uploaded_file is None:
    df_raw = pd.read_csv("exampleData/6_months_ecommerce_analytics_dataset.csv")
elif uploaded_file is not None:
    df_raw = pd.read_csv(uploaded_file)
else:
    df_raw = None

if df_raw is None:
    st.info("Upload a CSV file or toggle 'Use example data' to get started.")
    st.stop()

# Choose metric
st.subheader("Step 2: Choose metric")
candidate_metrics = [
    col for col in df_raw.columns
    if col.lower() not in ("date", "metric_name")
]
metric_name = st.selectbox("Metric to analyze", candidate_metrics)

if run_button:
    try:
        # Prepare & split data
        df = prepare_dataframe(df_raw.copy(), metric_name=metric_name)
        period_days = {"day": 1, "week": 7, "month": 30}[granularity]
        end_date = df["date"].max()
        current, previous = split_periods(df, end_date, period_days)

        # Analysis
        change_context = detect_change_context(df, current, previous)
        drivers = calculate_drivers_effects(current, previous, metric_col="metric_value")
        data_quality = {}  # or your assess_data_quality(df, current, previous)

        output_json = build_output_json(
            metric_name=metric_name,
            granularity=granularity,
            current=current,
            previous=previous,
            change_context=change_context,
            drivers=drivers,
            data_quality=data_quality,
        )

        # --- Layout: Summary top row ---
        st.subheader("Change summary")

        pc = output_json["period_comparison"]
        cs = output_json["change_strength"]
        ct = output_json["change_trust"]

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric(
                label=f"{metric_name} ({granularity})",
                value=f'{pc["current_value"]:.2f}',
                delta=f'{pc["absolute_change"]:.2f} ({pc["relative_change_pct"]:.2f}%)'
            )
        with col_b:
            st.metric(
                label="Level change",
                value=cs["level_change_label"].capitalize(),
                delta=f"Score: {cs['level_score']:.2f}"
            )
        with col_c:
            st.metric(
                label="Trend change",
                value=cs["trend_change_label"].capitalize(),
                delta=f"Score: {cs['trend_score']:.2f}"
            )

        st.write(pc["summary"])

        # --- Visual: time series chart ---

        # Build a unified DataFrame with a period label for plotting
        plot_df = df[["date", "metric_value"]].copy()
        plot_df["period"] = np.where(
            (plot_df["date"] >= current["date"].min()) & (plot_df["date"] <= current["date"].max()),
            "current",
            "previous",
        )

        st.subheader("KPI over time")

        # Build a unified DataFrame with a period label
        plot_df = df[["date", "metric_value"]].copy()

        prev_start = previous["date"].min()
        prev_end = previous["date"].max()
        curr_start = current["date"].min()
        curr_end = current["date"].max()

        # Mark which period each point belongs to (for tooltips/legend if needed)
        def label_period(d):
            if prev_start <= d <= prev_end:
                return "previous"
            elif curr_start <= d <= curr_end:
                return "current"
            else:
                return "outside"

        plot_df["period"] = plot_df["date"].apply(label_period)
        plot_df = plot_df.rename(columns={"metric_value": metric_name})

        # Base line chart
        line = (
            alt.Chart(plot_df)
            .mark_line(color="#1f77b4", strokeWidth=2)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y(f"{metric_name}:Q", title=metric_name),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip(f"{metric_name}:Q", title=metric_name, format=",.2f"),
                    alt.Tooltip("period:N", title="Period"),
                ],
            )
        )

        # Shaded bands for previous and current periods
        prev_band = (
            alt.Chart(pd.DataFrame({"start": [prev_start], "end": [prev_end]}))
            .mark_rect(color="#aec7e8", opacity=0.25)
            .encode(x="start:T", x2="end:T")
        )

        curr_band = (
            alt.Chart(pd.DataFrame({"start": [curr_start], "end": [curr_end]}))
            .mark_rect(color="#ffbb78", opacity=0.25)
            .encode(x="start:T", x2="end:T")
        )

        # Vertical rules for boundaries
        rules_df = pd.DataFrame(
            {
                "date": [prev_start, prev_end, curr_end],
                "label": [
                    "Previous starts",
                    "Previous ends / Current starts",
                    "Current ends",
                ],
            }
        )

        rules = (
            alt.Chart(rules_df)
            .mark_rule(color="gray", strokeDash=[4, 4])
            .encode(x="date:T")
        )

        rule_labels = (
            alt.Chart(rules_df)
            .mark_text(dy=-10, color="gray", fontSize=10, fontWeight="bold")
            .encode(
                x="date:T",
                y=alt.value(0),  # top of chart
                text="label:N",
            )
        )

        chart = (prev_band + curr_band + line + rules + rule_labels).properties(
            width="container", height=300
        )

        st.altair_chart(chart, use_container_width=True)
        st.caption(
            "Blue shaded region: previous period. Orange shaded region: current period. "
            "Dashed lines mark period boundaries."
        )

        # st.subheader("KPI over time")
        # chart_df = df[["date", "metric_value"]].rename(columns={"metric_value": metric_name})
        # st.line_chart(chart_df.set_index("date"))

        # --- Reliability & volatility ---
        st.subheader("Change reliability")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Trend consistency:**", ct["trend_consistency"])
            st.write("**High volatility:**", ct["high_volatility"])
            st.write("**Trustworthy signal:**", ct["trustworthy"])
        with col2:
            st.write(ct["reliability_summary"])
            st.write("Average volatility:", ct["avg_volatility"])

        # --- Drivers ---
        st.subheader("Top drivers of change")

        # --- Drivers: AI narrative + compact expansion ---
        st.subheader("Key drivers")

        drivers_section = output_json["drivers"]

        # (a) AI narrative summary
        driver_text = summarize_drivers(output_json)
        st.markdown("**AI summary of drivers**")
        st.write(driver_text)

        # (b) Compact numeric expansion (non-repetitive)
        summary_df = build_driver_summary(drivers_section, max_rows=8)
        expansion_text = build_driver_expansion_text(summary_df)

        st.markdown("**Details behind the summary**")
        st.write(expansion_text)

        if not summary_df.empty:
            st.table(summary_df[["dimension", "category", "impact_pct", "direction", "strength"]])
        else:
            st.write("No strong drivers were detected.")


        # drivers_section = output_json["drivers"]
        # by_dimension = drivers_section["by_dimension"]
        # top_pos_overall = drivers_section["top_positive_overall"]
        # top_neg_overall = drivers_section["top_negative_overall"]

        # # Overall drivers
        # col_pos, col_neg = st.columns(2)
        # with col_pos:
        #     st.markdown("**Top positive drivers (overall)**")
        #     if top_pos_overall:
        #         st.table(pd.DataFrame(top_pos_overall))
        #     else:
        #         st.write("No strong positive drivers detected.")
        # with col_neg:
        #     st.markdown("**Top negative drivers (overall)**")
        #     if top_neg_overall:
        #         st.table(pd.DataFrame(top_neg_overall))
        #     else:
        #         st.write("No strong negative drivers detected.")

        # # Drivers per dimension (collapsible)
        # st.subheader("Drivers by dimension")
        # for dim_info in by_dimension:
        #     dim_name = dim_info["dimension"]
        #     with st.expander(dim_name, expanded=False):
        #         col_d1, col_d2 = st.columns(2)
        #         with col_d1:
        #             st.caption("Top positive")
        #             if dim_info["top_positive"]:
        #                 st.table(pd.DataFrame(dim_info["top_positive"]))
        #             else:
        #                 st.write("None.")
        #         with col_d2:
        #             st.caption("Top negative")
        #             if dim_info["top_negative"]:
        #                 st.table(pd.DataFrame(dim_info["top_negative"]))
        #             else:
        #                 st.write("None.")



        # --- Data quality & next actions ---
        st.subheader("Data quality & recommended checks")
        if output_json.get("data_quality"):
            st.json(output_json["data_quality"])
        for item in output_json["recommended_checks"]:
            st.write("- ", item)

    except Exception as e:
        st.error(f"Error during analysis: {e}")
else:
    st.info("Click **Run analysis** after choosing a metric.")
