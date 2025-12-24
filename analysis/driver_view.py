# analysis/driver_view.py
import pandas as pd


def build_driver_summary(drivers_section: dict, max_rows: int = 10) -> pd.DataFrame:
    """
    Turn the verbose drivers JSON into a compact summary table.

    Columns:
      - dimension
      - category (dimension value/bucket)
      - impact_pct (share of total change, +/-)
      - direction ("up" / "down")
      - strength ("minor" / "moderate" / "strong")
    """

    pos = drivers_section.get("top_positive_overall", [])
    neg = drivers_section.get("top_negative_overall", [])

    rows = []

    def extract_category(row: dict) -> str:
        # Use the first non-meta field as the category label
        meta_cols = {
            "dimension", "effect_score", "contrib_share_of_change", "direction",
            "volume_curr", "volume_prev", "mean_curr", "mean_prev",
            "contrib_curr", "contrib_prev", "contrib_delta",
            "change_label",
        }
        for key, value in row.items():
            if key not in meta_cols:
                return f"{key} = {value}"
        return "N/A"

    # Positive contributors
    for row in pos:
        dim = row.get("dimension", "N/A")
        impact = row.get("contrib_share_of_change", row.get("effect_score", 0.0)) * 100
        rows.append({
            "dimension": dim,
            "category": extract_category(row),
            "impact_pct": round(impact, 1),
            "direction": "up",
            "strength": row.get("change_label", "unknown"),
        })

    # Negative contributors
    for row in neg:
        dim = row.get("dimension", "N/A")
        impact = row.get("contrib_share_of_change", row.get("effect_score", 0.0)) * 100
        rows.append({
            "dimension": dim,
            "category": extract_category(row),
            "impact_pct": round(impact, 1),
            "direction": "down",
            "strength": row.get("change_label", "unknown"),
        })

    if not rows:
        return pd.DataFrame(columns=["dimension", "category", "impact_pct", "direction", "strength"])

    df = pd.DataFrame(rows)
    # Sort strongest first by absolute impact
    df["abs_impact"] = df["impact_pct"].abs()
    df = df.sort_values("abs_impact", ascending=False).drop(columns=["abs_impact"])
    return df.head(max_rows)


def build_driver_expansion_text(summary_df: pd.DataFrame) -> str:
    """
    Build a short, non-repetitive expansion of the AI summary,
    focusing on concrete numbers and categories.
    """

    if summary_df.empty:
        return "No individual segments stand out as major drivers in the data."

    lines = []

    # 1–2 strongest positive and negative segments (if present)
    pos = summary_df[summary_df["direction"] == "up"].head(2)
    neg = summary_df[summary_df["direction"] == "down"].head(2)

    if not pos.empty:
        lines.append("The largest positive contributions come from:")
        for _, row in pos.iterrows():
            lines.append(
                f"- {row['dimension']} / {row['category']} "
                f"(~{row['impact_pct']:.1f}% of the total change, {row['strength']})."
            )

    if not neg.empty:
        lines.append("The largest negative contributions come from:")
        for _, row in neg.iterrows():
            lines.append(
                f"- {row['dimension']} / {row['category']} "
                f"(~{row['impact_pct']:.1f}% of the total change, {row['strength']})."
            )

    if len(lines) == 0:
        return "The change is driven by several small segments rather than a few dominant ones."

    return "\n".join(lines)
