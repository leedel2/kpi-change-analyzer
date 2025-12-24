# KPI Change Analyzer

## What this does
Upload a CSV containing KPI data and receive a structured explanation of why a KPI changed between two periods.


An interactive web app that helps you understand what changed in your KPIs and why.
Upload your own CSV, pick a KPI, and the app will:
Compare the current period vs the previous period
Detect level and trend changes
Identify top drivers (segments that pushed the KPI up or down)
Present results in a clean visual dashboard and a short textual summary

A live demo is available at:

https://YOUR-APP-NAME.streamlit.app
(Replace with the actual URL of your deployed Streamlit app.)

## Features
1. Metric and period comparison
Select any numeric column as the KPI (e.g. revenue_total, orders_total, signups).

Choose time granularity: day, week, or month.

### The app compares:
Current period: last N days/weeks/months.
Previous period: the same length immediately before.

### It computes:
Current vs previous mean value.
Absolute and relative (% ) change.
Direction: up, down, or flat.

2. Change strength and trend
Effect‑size based scores instead of brittle p‑values:

level_score: how big the change in average is compared to normal variation.
trend_score: how much the metric’s slope changed compared to noise.

Labels each change as: none, minor, moderate, or strong.

Estimates trend alignment and volatility and outputs:

A trustworthy flag.

A short reliability summary.

3. Driver analysis (segments that explain the change)
Treats every non‑date, non‑metric column as a potential dimension (e.g. channel, country, device).

For each category/bucket in each dimension, computes its contribution to the total KPI change (not just its own average).

### Filters out:
Constant dimensions.
Very low‑volume segments.
Produces a compact view of key drivers:
dimension (e.g. country).
category (e.g. country = US).
impact_pct (approximate share of total change, +/−).
direction (up / down).
strength (minor / moderate / strong).

4. Human‑readable summaries
### A simple summary that explains:
How the KPI changed.
Whether the change is minor/moderate/strong and reliable.
A driver summary that lists the main segments and their contribution to the change, in plain language.
These summaries work without any external AI keys (they are computed from the driver data itself).

Note: The code also supports optional integration with a free LLM API for more natural language, but this is configured only by the app owner. Regular users do not need any tokens or keys.

5. Visual dashboard
### KPI over time line chart with:
One line for the KPI.
Shaded bands showing previous and current periods.
Dashed vertical lines and labels marking:
When the previous period starts.
When the previous ends / current starts.
When the current ends.
Top‑row KPI cards showing:
Current value and delta.
Level and trend change labels and scores.
Compact driver table instead of raw technical fields.

# Data format

## Required columns
Date - A column named date. Values must be parseable as dates (e.g. 2024‑01‑31).
Metric columns
One or more numeric columns to use as KPIs (e.g. revenue_total, orders_total, signups).

## Supported shapes
### Wide format
One row per date, multiple metric columns.
text
date, revenue_total, orders_total, country, channel
2024-01-01, 10000, 250, US, organic
2024-01-02, 12000, 280, US, paid
In the app, you pick revenue_total or any other metric column from a dropdown.

### Long format
Uses columns metric_name and metric_value.
text
date, metric_name, metric_value, country, channel
2024-01-01, revenue_total, 10000, US, organic
2024-01-01, orders_total, 250, US, organic
The app filters rows where metric_name == <your selection> and uses metric_value as the KPI.

### Dimensions (drivers)
Any column that is not date, metric_name, or metric_value can act as a dimension:
Examples: country, device, channel, segment, etc.

## How to use the app (as a user)
Open the public URL (e.g. https://kpi-change-analyzer.streamlit.app).

Upload a CSV file (or use the example data if provided).

Choose:

A metric to analyze.

The time granularity (day, week, month).

Click Run analysis.

Read:

The KPI change summary (how much it moved, and how strongly).

The time‑series chart with highlighted current/previous periods.

The driver summary and compact driver table showing which segments had the biggest impact.

No installation, tokens, or coding are required for users.

Running locally (for developers)
If you want to clone and run the app locally:

bash
git clone https://github.com/<your-username>/kpi-change-analyzer.git
cd kpi-change-analyzer

python3 -m venv .venv
source .venv/bin/activate

.venv/bin/python3 -m pip install --upgrade pip
.venv/bin/python3 -m pip install -r requirements.txt

.venv/bin/streamlit run app.py
Then open the URL shown in the terminal (usually http://localhost:8501).

Deployment (for the app owner)
To deploy on Streamlit Community Cloud:

Push this repo to GitHub.

Go to https://streamlit.io → Community Cloud → New app.

Select:

GitHub repo.

Branch (e.g. main).

Main file: app.py.

Click Deploy.

Streamlit will give you a public URL you can share in your portfolio.
