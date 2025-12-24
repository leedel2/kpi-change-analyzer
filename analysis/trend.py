import numpy as np
import pandas as pd


def detect_change_context(full_df, current, previous):
    """
    Detects level and trend changes between two periods (previous vs current)
    using effect-size-based scores instead of p-values.

    Assumes:
    - full_df has a time column (any name) as first column and 'metric_value' column.
    - current and previous are subsets of full_df for two periods.
    """

    # ---- 0. Basic validation ----
    if current.empty or previous.empty:
        raise ValueError("One of the comparison periods has no data")

    # Ensure sorted by time (assume first column is time-like)
    time_col = full_df.columns[0]
    full_df = full_df.sort_values(by=time_col)
    current = current.sort_values(by=time_col)
    previous = previous.sort_values(by=time_col)

    # Extract numeric series
    full_series = full_df["metric_value"].astype(float)
    current_series = current["metric_value"].astype(float)
    previous_series = previous["metric_value"].astype(float)

    # ---- 1. Level (mean) comparison ----
    current_mean = float(current_series.mean())
    previous_mean = float(previous_series.mean())
    level_delta = current_mean - previous_mean

    rel_change_pct = None
    if previous_mean != 0:
        rel_change_pct = float((level_delta / previous_mean) * 100)

    # ---- 2. Simple trend slopes (effect sizes, not p-values) ----
    def fit_slope(series: pd.Series) -> float:
        # If too short, return 0 slope
        if len(series) < 2:
            return 0.0
        x = np.arange(len(series))
        # Least-squares slope
        slope = np.polyfit(x, series.values, 1)[0]
        return float(slope)

    previous_slope = fit_slope(previous_series)
    current_slope = fit_slope(current_series)
    slope_delta = current_slope - previous_slope

    # ---- 3. Overall trend alignment (same idea as before) ----
    diffs = full_series.diff().dropna()
    overall_delta_sign = np.sign(level_delta) if level_delta != 0 else 0
    if overall_delta_sign == 0:
        trend_alignment = 0.5
    else:
        trend_alignment = float((np.sign(diffs) == overall_delta_sign).mean())

    # ---- 4. Volatility estimation ----
    # Window size scaled with series length, clamped between 8 and 20
    window_size = min(max(8, len(full_series) // 10), 20)
    if len(full_series) >= window_size:
        rolling_std = full_series.rolling(window_size).std().dropna()
        avg_volatility = float(rolling_std.mean()) if not rolling_std.empty else 0.0
    else:
        avg_volatility = float(full_series.std()) if len(full_series) > 1 else 0.0

    # Avoid division by zero
    eps = 1e-8
    effective_volatility = avg_volatility if avg_volatility > 0 else eps

    # ---- 5. Effect-size-based scores ----
    # Level score: how big is the mean change relative to typical noise?
    level_score = abs(level_delta) / effective_volatility

    # Approximate "per-step" noise for trend comparison
    # If you think of slope as "change per time step", then typical
    # per-step variation is about avg_volatility.
    slope_score = abs(slope_delta) / (effective_volatility + eps)

    # Direction flip flag
    slope_direction_change = np.sign(current_slope) != np.sign(previous_slope)

    # ---- 6. Map scores to qualitative labels ----
    def score_to_label(score: float) -> str:
        # You can tune these thresholds globally or per-metric:
        # 0–0.5: no material change
        # 0.5–1: minor
        # 1–2: moderate
        # >2: strong
        if score < 0.5:
            return "none"
        elif score < 1.0:
            return "minor"
        elif score < 2.0:
            return "moderate"
        else:
            return "strong"

    level_change_label = score_to_label(level_score)
    trend_change_label = score_to_label(slope_score)

    # ---- 7. Volatility flag & trustworthiness ----
    # High volatility if noise itself is large relative to the mean
    mean_abs_level = np.mean(np.abs(full_series)) if len(full_series) > 0 else 0.0
    high_volatility = bool(
        mean_abs_level > 0 and avg_volatility > 0.5 * mean_abs_level
    )

    # Trustworthiness:
    # - some level change (not "none")
    # - or some trend change (not "none")
    # - alignment reasonably high
    # - and not extremely volatile
    trustworthy = bool(
        (level_change_label != "none" or trend_change_label != "none")
        and trend_alignment > 0.6
        and not high_volatility
    )

    # ---- 8. Final flags ----
    # Simplified boolean: is there any meaningful change?
    any_change_detected = bool(
        level_change_label in ("minor", "moderate", "strong")
        or trend_change_label in ("minor", "moderate", "strong")
        or slope_direction_change
    )

    return {
        # Level comparison
        "current_value": round(current_mean, 4),
        "previous_value": round(previous_mean, 4),
        "absolute_change": round(level_delta, 4),
        "relative_change_pct": round(rel_change_pct, 2) if rel_change_pct is not None else None,

        # Trend comparison (effect sizes)
        "previous_trend_slope": round(previous_slope, 6),
        "current_trend_slope": round(current_slope, 6),
        "slope_delta": round(slope_delta, 6),

        # Scores and labels
        "level_score": round(level_score, 3),
        "trend_score": round(slope_score, 3),
        "level_change_label": level_change_label,   # "none" / "minor" / "moderate" / "strong"
        "trend_change_label": trend_change_label,   # same categories
        "slope_direction_changed": slope_direction_change,

        # Alignment & volatility
        "trend_consistency": round(trend_alignment, 2),
        "avg_volatility": round(avg_volatility, 4),
        "high_volatility": high_volatility,

        # Overall assessment
        "any_change_detected": any_change_detected,
        "trustworthy": trustworthy,
    }
