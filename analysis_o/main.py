from fastapi import FastAPI, UploadFile, Form
from fastapi import HTTPException
import traceback
import sys
import pandas as pd
from datetime import datetime

from app.analysis.validation import validate_schema
from app.analysis.loader import prepare_dataframe, split_periods
from app.analysis.change_detection import detect_change_context
from app.analysis.drivers import calculate_drivers_effects
from app.analysis.data_quality import assess_data_quality
from app.analysis.json_builder import build_output_json
from app.ai.report_generator import generate_markdown_report

app = FastAPI(title="KPI Change Analyzer")


@app.post("/analyze")
async def analyze(
    file: UploadFile,
    metric_name: str = Form(...),
    granularity: str = Form("week"),
    use_ai: bool = Form(False)
):
    try:
        df = pd.read_csv(file.file)
        validate_schema(df)

        df = prepare_dataframe(df, metric_name)

        period_days = {"day": 1, "week": 7, "month": 30}[granularity]
        end_date = df["date"].max()

        current, previous = split_periods(df, end_date, period_days)

        change_context = detect_change_context(df, current, previous)
        drivers = calculate_drivers_effects(current, previous)
        data_quality = assess_data_quality(df, current, previous)

        output_json = build_output_json(
            metric_name=metric_name,
            granularity=granularity,
            current=current,
            previous=previous,
            change_context=change_context,
            drivers=drivers,
            data_quality=data_quality
        )

        report = generate_markdown_report(output_json, use_ai)

        return {
            "json": output_json,
            "report": report
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # raise HTTPException(status_code=500, detail=f"Internal error: {e}")
        ### Capture traceback as a string (for logging / debugging)
        tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))

        # Print to container logs (appears in `docker run` terminal)
        print("Unexpected error in /analyze:", tb_str, file=sys.stderr)

        # Return a more informative message in the HTTP response
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}"
        )

