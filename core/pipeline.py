"""
Ties together SQL generation, execution, analysis, charting, and insight
generation into a single pipeline used by both the API and any ad-hoc
scripts/tests.
"""

import pandas as pd

from core.analysis import detect_anomalies, forecast_trend
from core.charts import generate_chart
from core.db import run_query
from core.insights import generate_insight
from core.sql_generator import generate_sql

MIN_POINTS_FOR_FORECAST = 4


def _pick_columns(df: pd.DataFrame):
    """
    Heuristic column picker: the first datetime-like or text column becomes
    the label/date column, the first numeric column becomes the value
    column. Works across all the fallback templates and any reasonable
    LLM-generated query that aliases columns sensibly.
    """
    label_col = None
    value_col = None

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and value_col is None:
            value_col = col
        elif not pd.api.types.is_numeric_dtype(df[col]) and label_col is None:
            label_col = col

    # Fallbacks if the heuristic didn't find one of each.
    if label_col is None and len(df.columns) > 0:
        label_col = df.columns[0]
    if value_col is None and len(df.columns) > 1:
        value_col = df.columns[1]
    elif value_col is None:
        value_col = df.columns[0]

    return label_col, value_col


def run_pipeline(question: str) -> dict:
    """
    Runs the full ask pipeline: NL question -> SQL -> execute -> analyze ->
    chart -> insight. Returns a dict matching the API response contract.
    """
    sql = generate_sql(question)
    df = run_query(sql)

    label_col, value_col = _pick_columns(df)

    is_time_series = False
    if not df.empty and label_col is not None:
        try:
            pd.to_datetime(df[label_col])
            is_time_series = True
        except (ValueError, TypeError):
            is_time_series = False

    anomaly_df = None
    if is_time_series and len(df) >= 3:
        anomaly_df = detect_anomalies(df, value_col, label_col)

    forecast_df = None
    if is_time_series and len(df) >= MIN_POINTS_FOR_FORECAST:
        forecast_df = forecast_trend(df, value_col, label_col, periods=3)

    chart_path = None
    if not df.empty:
        chart_type = "line" if is_time_series else "bar"
        chart_path = generate_chart(
            df, question, value_col, label_col, chart_type,
            forecast_df=forecast_df if chart_type == "line" else None,
        )

    insight_text, suggested_action = generate_insight(
        question, df, value_col, label_col if is_time_series else None, anomaly_df, forecast_df
    )

    forecast_points = None
    if forecast_df is not None:
        future_only = forecast_df[forecast_df["is_forecast"]]
        forecast_points = future_only.to_dict(orient="records")

    return {
        "sql": sql,
        "results": df.to_dict(orient="records"),
        "chart_path": chart_path,
        "forecast": forecast_points,
        "insight": insight_text,
        "suggested_action": suggested_action,
    }
