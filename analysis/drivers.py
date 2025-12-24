import numpy as np
import pandas as pd

### detect continuous vs categorical dimensions
def is_continuous_series(s: pd.Series, max_categories: int = 20) -> bool:
    # numeric and many unique values → treat as continuous
    if not pd.api.types.is_numeric_dtype(s):
        return False
    return s.nunique(dropna=True) > max_categories


def bin_continuous_dimension(current: pd.DataFrame,
                             previous: pd.DataFrame,
                             dim: str,
                             n_bins: int = 10,
                             min_unique: int = 10):
    """
    Bin a continuous dimension into quantile bins (same edges for both periods).
    Returns new dataframes with a binned column <dim>_binned.
    """

    combined = pd.concat([current[[dim]], previous[[dim]]], axis=0)
    unique_vals = combined[dim].nunique(dropna=True)

    # If very few unique values, no need to bin
    if unique_vals < min_unique:
        # Just copy original column name to <dim>_binned
        current[f"{dim}_binned"] = current[dim]
        previous[f"{dim}_binned"] = previous[dim]
        return current, previous

    # Compute bin edges on combined data to be consistent
    try:
        quantiles = np.linspace(0, 1, n_bins + 1)
        bin_edges = combined[dim].quantile(quantiles).values
        # Ensure strictly increasing edges to avoid issues with duplicates
        bin_edges = np.unique(bin_edges)
        if len(bin_edges) <= 1:
            current[f"{dim}_binned"] = current[dim]
            previous[f"{dim}_binned"] = previous[dim]
            return current, previous

        labels = [f"{dim}_bin_{i}" for i in range(len(bin_edges) - 1)]

        current[f"{dim}_binned"] = pd.cut(
            current[dim], bins=bin_edges, labels=labels, include_lowest=True
        )
        previous[f"{dim}_binned"] = pd.cut(
            previous[dim], bins=bin_edges, labels=labels, include_lowest=True
        )

        return current, previous

    except Exception:
        # Fallback: no binning
        current[f"{dim}_binned"] = current[dim]
        previous[f"{dim}_binned"] = previous[dim]
        return current, previous


def calculate_drivers_effects(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    metric_col: str = "metric_value",
    dimensions: list | None = None,
    min_volume_share: float = 0.01,   # ignore categories with <1% of total volume (per period)
    min_abs_contrib_share: float = 0.01,  # ignore categories that explain <1% of total change
    eps: float = 1e-8
):
    """
    Calculate drivers of change for a target metric across given dimensions
    using contribution-based effects, normalization, volume filters, and
    effect-size scores.

    Parameters
    ----------
    current : pd.DataFrame
        Data for the current period. Must contain `metric_col` and dimensions.
    previous : pd.DataFrame
        Data for the previous period. Must contain `metric_col` and dimensions.
    metric_col : str
        Name of the metric column.
    dimensions : iterable of str
        Column names to treat as candidate driver dimensions.
        If `dimensions` is None, all columns except date/metric/non-dimension are treated as dimensions.
    min_volume_share : float
        Minimum share of volume (in either period) for a category to be considered.
    min_abs_contrib_share : float
        Minimum absolute share of total contribution change to keep a category.
    eps : float
        Small constant to avoid division by zero.

    Returns
    -------
    list of dict
        One dictionary per dimension with:
        - "dimension"
        - "drivers": list of category-level records with contribution, scores, labels
        - "top_positive": top positive drivers
        - "top_negative": top negative drivers
    """

    # ---- 0. Infer dimensions if not provided ----
    if dimensions is None:
        # Columns that are *not* dimensions
        non_dim_cols = {"date", metric_col, "metric_name"}
        # Keep only columns that exist in both current and previous
        common_cols = set(current.columns).intersection(previous.columns)
        dimensions = [
            col for col in common_cols
            if col not in non_dim_cols
        ]

    results = []

    # Total volumes and total contributions per period (for normalization)
    total_curr_volume = len(current)
    total_prev_volume = len(previous)

    total_curr_contrib = float(current[metric_col].sum()) if metric_col in current.columns else 0.0
    total_prev_contrib = float(previous[metric_col].sum()) if metric_col in previous.columns else 0.0
    total_contrib_delta = total_curr_contrib - total_prev_contrib

    for dim in dimensions:
        # Safety check (should be true by construction)
        if dim not in current.columns or dim not in previous.columns:
            continue

        # Skip dimensions that are effectively constant across both periods
        if current[dim].nunique(dropna=True) <= 1 and previous[dim].nunique(dropna=True) <= 1:
            continue

        series_full = pd.concat([current[dim], previous[dim]], ignore_index=True)

        # Skip constant dimensions
        if series_full.nunique(dropna=True) <= 1:
            continue

        if is_continuous_series(series_full):
            # apply binning first
            binned_current, binned_previous = bin_continuous_dimension(
                current, previous, dim
            )
            dim_for_groupby = f"{dim}_binned"
        else:
            binned_current, binned_previous = current, previous
            dim_for_groupby = dim


        # ---- 1. Aggregate volume & mean per category in each period ----
        curr_agg = (
            current.groupby(dim_for_groupby)[metric_col]
            .agg(volume_curr="sum", mean_curr="mean")
            .reset_index()
        )

        prev_agg = (
            previous.groupby(dim_for_groupby)[metric_col]
            .agg(volume_prev="sum", mean_prev="mean")
            .reset_index()
        )

        # ---- 2. Merge categories appearing in either period ----
        merged = pd.merge(curr_agg, prev_agg, on=dim, how="outer")
        merged[["volume_curr", "volume_prev"]] = merged[["volume_curr", "volume_prev"]].fillna(0)
        merged[["mean_curr", "mean_prev"]] = merged[["mean_curr", "mean_prev"]].fillna(0.0)

        # ---- 3. Compute contributions and deltas ----
        merged["contrib_curr"] = merged["volume_curr"] * merged["mean_curr"]
        merged["contrib_prev"] = merged["volume_prev"] * merged["mean_prev"]
        merged["contrib_delta"] = merged["contrib_curr"] - merged["contrib_prev"]

        # ---- 4. Volume filters: drop tiny-volume categories ----
        # Compute share of total volume in each period
        merged["volume_share_curr"] = merged["volume_curr"] / (total_curr_volume + eps)
        merged["volume_share_prev"] = merged["volume_prev"] / (total_prev_volume + eps)

        merged = merged[
            (merged["volume_share_curr"] >= min_volume_share)
            | (merged["volume_share_prev"] >= min_volume_share)
        ].copy()

        if merged.empty:
            results.append({
                "dimension": dim,
                "drivers": [],
                "top_positive": [],
                "top_negative": [],
            })
            continue

        # ---- 5. Normalize contribution delta to share of total change ----
        # If total_contrib_delta ~ 0, use absolute total contributions to avoid blow-ups
        denom = total_contrib_delta if abs(total_contrib_delta) > eps else (
            abs(total_curr_contrib) + abs(total_prev_contrib) + eps
        )

        merged["contrib_share_of_change"] = merged["contrib_delta"] / denom

        # Filter out categories that barely explain any of the change
        merged = merged[
            merged["contrib_share_of_change"].abs() >= min_abs_contrib_share
        ].copy()

        if merged.empty:
            results.append({
                "dimension": dim,
                "drivers": [],
                "top_positive": [],
                "top_negative": [],
            })
            continue

        # ---- 6. Effect-size style score for each category ----
        # Use "relative contribution change" as the score:
        # larger absolute share -> higher score.
        merged["effect_score"] = merged["contrib_share_of_change"].abs()

        # ---- 7. Map scores to labels ----
        def score_to_label(score: float) -> str:
            # Tunable thresholds; you can later adapt per-metric or per-client:
            # < 0.02  (~2% of change): minor
            # 0.02–0.1 (~2–10%): moderate
            # > 0.1   (>10%): strong
            if score < 0.02:
                return "minor"
            elif score < 0.1:
                return "moderate"
            else:
                return "strong"

        merged["change_label"] = merged["effect_score"].apply(score_to_label)

        # ---- 8. Build output records ----
        merged["direction"] = np.where(
            merged["contrib_delta"] >= 0, "positive", "negative"
        )

        # Sort by effect size, largest first
        merged_sorted = merged.sort_values("effect_score", ascending=False)

        records = merged_sorted.to_dict(orient="records")

        # Top positive & negative drivers
        top_positive = [
            r for r in records if r["contrib_delta"] > 0
        ][:3]
        top_negative = [
            r for r in records if r["contrib_delta"] < 0
        ][:3]

        # explained_change_pct = merged["contrib_share_of_change"] * 100

        results.append({
            "dimension": dim,
            "drivers": records,       # all kept categories for this dimension
            "top_positive": top_positive,
            "top_negative": top_negative,
            "num_drivers": len(records),
            # "explained_change_pct": explained_change_pct,
        })

    return results



# def calculate_drivers_contribution(current, previous, metric_col="metric_value"):
#     drivers = []

#     for dim in ["dimension_1", "dimension_2", "dimension_3"]:
#         if dim not in current.columns or dim not in previous.columns:
#             continue

#         # Aggregate volume and mean per category in each period
#         curr_agg = (
#             current.groupby(dim)[metric_col]
#             .agg(volume="count", mean="mean")
#             .reset_index()
#         )
#         prev_agg = (
#             previous.groupby(dim)[metric_col]
#             .agg(volume="count", mean="mean")
#             .reset_index()
#         )

#         # Merge, keeping all categories seen in either period
#         merged = pd.merge(curr_agg, prev_agg, on=dim, how="outer", suffixes=("_curr", "_prev"))
#         merged[["volume_curr", "volume_prev"]] = merged[["volume_curr", "volume_prev"]].fillna(0)
#         merged[["mean_curr", "mean_prev"]] = merged[["mean_curr", "mean_prev"]].fillna(0.0)

#         # Total contribution in each period
#         merged["contrib_curr"] = merged["volume_curr"] * merged["mean_curr"]
#         merged["contrib_prev"] = merged["volume_prev"] * merged["mean_prev"]
#         merged["contrib_delta"] = merged["contrib_curr"] - merged["contrib_prev"]

#         # Sort by contribution to overall change
#         top = merged.sort_values("contrib_delta")

#         drivers.append({
#             "dimension": dim,
#             "top_negative": top.head(3).to_dict(orient="records"),
#             "top_positive": top.tail(3).to_dict(orient="records")
#         })

#     return drivers
