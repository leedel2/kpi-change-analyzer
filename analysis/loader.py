import pandas as pd

def prepare_dataframe(df, metric_name):
    df["date"] = pd.to_datetime(df["date"])

    # LONG format
    if {"metric_name", "metric_value"}.issubset(df.columns):
        df = df[df["metric_name"] == metric_name]

    # WIDE format
    else:
        if metric_name not in df.columns:
            raise ValueError(f"Metric '{metric_name}' not found in CSV columns")
        
        # Keep all columns, but standardize the metric column name
        df = df.rename(columns={metric_name: "metric_value"})

    if df.empty:
        raise ValueError(f"No data found for metric '{metric_name}'")

    return df.sort_values("date")



### before accepting long untidy fomat too

# def prepare_dataframe(df, metric_name):
#     df["date"] = pd.to_datetime(df["date"])
#     df = df[df["metric_name"] == metric_name]
#     return df.sort_values("date")

def split_periods(df, end_date, period_days):
    current_start = end_date - pd.Timedelta(days=period_days - 1)
    prev_end = current_start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=period_days - 1)

    current = df[(df["date"] >= current_start) & (df["date"] <= end_date)]
    previous = df[(df["date"] >= prev_start) & (df["date"] <= prev_end)]

    return current, previous




# def split_periods(df, end_date, period_days):
#     df = df.sort_values("date")

#     current_start = end_date - pd.Timedelta(days=period_days - 1)
#     prev_end = current_start - pd.Timedelta(days=1)
#     prev_start = prev_end - pd.Timedelta(days=period_days - 1)

#     current = df[(df["date"] >= current_start) & (df["date"] <= end_date)]
#     previous = df[(df["date"] >= prev_start) & (df["date"] <= prev_end)]

#     return current, previous

