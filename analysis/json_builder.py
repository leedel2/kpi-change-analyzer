from datetime import datetime


def to_python(obj):
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def build_output_json(
    metric_name,
    granularity,
    current,
    previous,
    change_context,
    drivers,
    data_quality
):
    """
    Build a structured JSON response describing:
    - What changed in the metric
    - How strong the change is
    - How reliable it looks
    - Which dimensions/categories are the main drivers
    """

    # 1. Basic period comparison
    current_value = to_python(change_context["current_value"])
    previous_value = to_python(change_context["previous_value"])
    absolute_change = to_python(change_context["absolute_change"])
    relative_change_pct = to_python(change_context["relative_change_pct"])

    direction = "up" if absolute_change > 0 else ("down" if absolute_change < 0 else "flat")

    # 2. Change strength / labels from effect-based logic
    level_change_label = change_context["level_change_label"]        # "none" / "minor" / "moderate" / "strong"
    trend_change_label = change_context["trend_change_label"]        # same categories
    any_change_detected = bool(change_context.get("any_change_detected", False))

    # 3. Trustworthiness and context
    trend_consistency = to_python(change_context["trend_consistency"])
    high_volatility = bool(change_context["high_volatility"])
    trustworthy = bool(change_context["trustworthy"])

    previous_trend_slope = to_python(change_context["previous_trend_slope"])
    current_trend_slope = to_python(change_context["current_trend_slope"])
    slope_delta = to_python(change_context["slope_delta"])
    slope_direction_changed = bool(change_context["slope_direction_changed"])

    level_score = to_python(change_context["level_score"])
    trend_score = to_python(change_context["trend_score"])

    # 4. Summarize drivers at a high level
    # `drivers` is already a list per dimension from calculate_drivers_effects
    # We add a compact summary: top dimension and top categories overall.
    dimension_summaries = []
    global_top_positive = []
    global_top_negative = []

    for dim_info in drivers:
        dim_name = dim_info.get("dimension")
        # dim_drivers = dim_info.get("drivers", [])
        num_drivers = dim_info.get("num_drivers", len(dim_info.get("drivers", [])))
        top_pos = dim_info.get("top_positive", [])
        top_neg = dim_info.get("top_negative", [])
        explained_change_pct = dim_info.get("explained_change_pct", [])

        # Build a brief summary per dimension
        dimension_summaries.append({
            "dimension": dim_name,
            # "num_drivers": len(dim_drivers),
            "num_drivers": num_drivers,
            "top_positive": top_pos,
            "top_negative": top_neg,
            # "explained_change_pct": explained_change_pct
        })

        # Collect for global top lists
        global_top_positive.extend([
            {**d, "dimension": dim_name} for d in top_pos
        ])
        global_top_negative.extend([
            {**d, "dimension": dim_name} for d in top_neg
        ])
        # explained_change_pct.extend([
        #     {**d, "dimension": dim_name} for d in explained_change_pct
        # ])

    # Sort global lists by effect_score if present, then by absolute contrib_share_of_change
    def driver_sort_key(d):
        # fallback gracefully if keys are missing
        score = d.get("effect_score", abs(d.get("contrib_share_of_change", 0.0)))
        return float(score)

    global_top_positive = sorted(global_top_positive, key=driver_sort_key, reverse=True)[:5]
    global_top_negative = sorted(global_top_negative, key=driver_sort_key, reverse=True)[:5]

    # 5. Suggested interpretation / narrative-friendly fields
    if not any_change_detected:
        change_summary = "No meaningful change detected in this period."
    else:
        parts = []
        if level_change_label != "none":
            parts.append(f"a {level_change_label} level change ({direction})")
        if trend_change_label != "none":
            parts.append(f"a {trend_change_label} trend change")
        if not parts:
            parts.append("a detectable but weak change")

        change_summary = " and ".join(parts) + " in the target metric."

    reliability_summary = (
        "The detected change appears reliable given the historical pattern."
        if trustworthy and not high_volatility
        else "The detected change may be influenced by volatility or inconsistent trends."
    )

    return {
        "meta": {
            "company": "Example Co",
            "industry": "SaaS",
            "metric_analyzed": metric_name,
            "time_granularity": granularity,
            "comparison_type": f"{granularity}_over_{granularity}",
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
        "period_comparison": {
            "current_value": current_value,
            "previous_value": previous_value,
            "absolute_change": absolute_change,
            "relative_change_pct": relative_change_pct,
            "direction": direction,
            "summary": change_summary,
        },
        "change_strength": {
            "level_score": level_score,
            "trend_score": trend_score,
            "level_change_label": level_change_label,
            "trend_change_label": trend_change_label,
            "slope_direction_changed": slope_direction_changed,
            "trend_slopes": {
                "previous_trend_slope": previous_trend_slope,
                "current_trend_slope": current_trend_slope,
                "slope_delta": slope_delta,
            },
        },
        "change_trust": {
            "trend_consistency": trend_consistency,
            "avg_volatility": to_python(change_context["avg_volatility"]),
            "high_volatility": high_volatility,
            "trustworthy": trustworthy,
            "reliability_summary": reliability_summary,
        },
        "drivers": {
            "by_dimension": dimension_summaries,
            "top_positive_overall": global_top_positive,
            "top_negative_overall": global_top_negative,
            # "explained_change_pct": explained_change_pct,
        },
        "data_quality": data_quality,
        "recommended_checks": [
            "Review recent product, pricing, or campaign changes around the comparison period.",
            "Check whether traffic/source mix shifted for top driver segments.",
            "Validate tracking and data pipeline integrity for the affected dimensions.",
        ],
    }
