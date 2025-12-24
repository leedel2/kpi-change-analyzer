# ai/driver_summary.py
import json
import streamlit as st
from openai import OpenAI
import pandas as pd

# --- Non-AI fallback summarizer (always works, no network) ---
def summarize_drivers_no_ai(output_json: dict) -> str:
    drivers = output_json["drivers"]
    pos = drivers.get("top_positive_overall", [])
    neg = drivers.get("top_negative_overall", [])

    pos_df = pd.DataFrame(pos)
    neg_df = pd.DataFrame(neg)

    lines = []

    if not pos_df.empty:
        for _, row in pos_df.head(3).iterrows():
            dim = row.get("dimension", "unknown dimension")
            cat_cols = [
                c for c in row.index
                if c not in ("dimension", "effect_score", "contrib_share_of_change", "direction")
            ]
            cat_val = row[cat_cols[0]] if cat_cols else "unknown"
            share = row.get("contrib_share_of_change", row.get("effect_score", 0)) * 100
            lines.append(
                f"- {dim} = {cat_val}: increased the KPI by about {share:.1f}% of the total change."
            )

    if not neg_df.empty:
        for _, row in neg_df.head(3).iterrows():
            dim = row.get("dimension", "unknown dimension")
            cat_cols = [
                c for c in row.index
                if c not in ("dimension", "effect_score", "contrib_share_of_change", "direction")
            ]
            cat_val = row[cat_cols[0]] if cat_cols else "unknown"
            share = row.get("contrib_share_of_change", row.get("effect_score", 0)) * 100
            lines.append(
                f"- {dim} = {cat_val}: decreased the KPI by about {abs(share):.1f}% of the total change."
            )

    if not lines:
        return "No strong drivers were detected for this change."

    return "Key drivers:\n" + "\n".join(lines)


# --- AI-backed summarizer using Hugging Face Inference (free tier) ---
def summarize_drivers(output_json: dict) -> str:
    # If no HF token configured, fall back to non-AI summarizer
    if "HF_TOKEN" not in st.secrets:
        return summarize_drivers_no_ai(output_json)

    # Initialize OpenAI client for Hugging Face router
    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=st.secrets["HF_TOKEN"],
    )

    metric = output_json["meta"]["metric_analyzed"]
    granularity = output_json["meta"]["time_granularity"]
    pc = output_json["period_comparison"]
    drivers = output_json["drivers"]

    prompt = f"""
You are a data analyst. Write a short, clear explanation of what drove the change in the KPI.

KPI: {metric} (granularity: {granularity})
Current value: {pc['current_value']}
Previous value: {pc['previous_value']}
Absolute change: {pc['absolute_change']}
Relative change (%): {pc['relative_change_pct']}
Summary: {pc['summary']}

Drivers JSON:
{json.dumps(drivers, indent=2)}

Instructions:
- Give 3–5 bullet points.
- For each bullet, name the dimension and category/bucket.
- Say whether it increased or decreased the KPI and roughly how much (using contrib_share_of_change or effect_score).
- Use plain language, no code or JSON.
- Keep it under 150 words.
"""

    try:
        # Use a free gpt-oss model via HF router
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b:cerebras",
            messages=[
                {
                    "role": "system",
                    "content": "You explain analytics results to business users in simple language.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Don’t break the app; log and fall back
        st.error(f"Driver AI summary error: {type(e).__name__}: {e}")
        return summarize_drivers_no_ai(output_json)
