REQUIRED_BASE_COLUMNS = {"date"}
OPTIONAL_DIMENSIONS = {"dimension_1", "dimension_2", "dimension_3"}

def validate_schema(df):
    cols = set(df.columns)

    if "date" not in cols:
        raise ValueError("CSV must contain a 'date' column")

    # Either long OR wide is allowed
    has_long_format = {"metric_name", "metric_value"}.issubset(cols)
    has_wide_format = len(cols - {"date"} - OPTIONAL_DIMENSIONS) > 0

    if not (has_long_format or has_wide_format):
        raise ValueError(
            "CSV must be either:\n"
            "- long format: date, metric_name, metric_value\n"
            "- wide format: date + one or more metric columns"
        )


### before accepring long untidy format too

# REQUIRED_COLUMNS = {"date", "metric_name", "metric_value"}
# OPTIONAL_DIMENSIONS = {"dimension_1", "dimension_2", "dimension_3"}

# def validate_schema(df):
#     cols = set(df.columns)

#     missing = REQUIRED_COLUMNS - cols
#     if missing:
#         raise ValueError(f"Missing required columns: {missing}")

#     dimensions = cols.intersection(OPTIONAL_DIMENSIONS)
#     if len(dimensions) > 3:
#         raise ValueError("Maximum of 3 dimensions allowed")

# # def validate_schema(df):
# #     cols = set(df.columns)

# #     if not REQUIRED_COLUMNS.issubset(cols):
# #         missing = REQUIRED_COLUMNS - cols
# #         raise ValueError(f"Missing required columns: {missing}")

# #     dimensions = cols.intersection(OPTIONAL_DIMENSIONS)
# #     if len(dimensions) > 3:
# #         raise ValueError("Maximum of 3 dimensions allowed")

# #     return True

