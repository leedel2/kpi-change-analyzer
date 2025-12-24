def assess_data_quality(full_df, current, previous):
    warnings = []

    if current.empty or previous.empty:
        warnings.append("One of the comparison periods has no data")

    missing_days = full_df["date"].nunique()
    expected_days = (full_df["date"].max() - full_df["date"].min()).days + 1

    completeness = round(missing_days / expected_days, 2)

    return {
        "completeness_score_avg": completeness,
        "warnings": warnings,
        "anomalies_detected": len(warnings) > 0
    }

