"""
Time-series analysis helpers: anomaly detection and trend forecasting.

Both functions operate on a plain pandas DataFrame with a date column and
a numeric value column, which is what every SQL template/LLM query in this
project produces after grouping by month/quarter.
"""

import numpy as np
import pandas as pd


def detect_anomalies(df: pd.DataFrame, value_col: str, date_col: str, z_threshold: float = 2.0) -> pd.DataFrame:
    """
    Flags anomalous points in a time series using a z-score on the value
    column. Returns a copy of df sorted by date_col with two extra columns:
      - zscore: the z-score of each point relative to the series mean/std
      - is_anomaly: True if abs(zscore) > z_threshold

    Falls back gracefully on tiny/degenerate series (std == 0, or fewer
    than 3 points) by marking nothing as anomalous, since a z-score isn't
    meaningful there.
    """
    result = df.copy()
    result[date_col] = pd.to_datetime(result[date_col])
    result = result.sort_values(date_col).reset_index(drop=True)

    values = result[value_col].astype(float)

    if len(values) < 3 or values.std(ddof=0) == 0:
        result["zscore"] = 0.0
        result["is_anomaly"] = False
        return result

    mean = values.mean()
    std = values.std(ddof=0)
    result["zscore"] = (values - mean) / std
    result["is_anomaly"] = result["zscore"].abs() > z_threshold

    return result


def forecast_trend(df: pd.DataFrame, value_col: str, date_col: str, periods: int = 3) -> pd.DataFrame:
    """
    Projects the next `periods` values forward using a simple linear
    regression (numpy.polyfit, degree 1) over the existing time series.
    This is a deliberately simple, robust approach for a demo: it captures
    direction and rough magnitude without pulling in a heavier forecasting
    library.

    Returns a DataFrame with columns [date_col, value_col, "is_forecast"]
    containing the original points (is_forecast=False) followed by the
    projected points (is_forecast=True). The projected dates continue the
    same cadence as the input series (inferred from the median gap between
    consecutive dates).
    """
    history = df.copy()
    history[date_col] = pd.to_datetime(history[date_col])
    history = history.sort_values(date_col).reset_index(drop=True)
    history["is_forecast"] = False

    if len(history) < 2:
        return history[[date_col, value_col, "is_forecast"]]

    x = np.arange(len(history))
    y = history[value_col].astype(float).values

    slope, intercept = np.polyfit(x, y, 1)

    # Infer the cadence of the series (e.g. ~30 days for monthly, ~91 for
    # quarterly) from the median gap between consecutive timestamps.
    deltas = history[date_col].diff().dropna()
    median_gap = deltas.median() if len(deltas) > 0 else pd.Timedelta(days=30)

    future_rows = []
    last_date = history[date_col].iloc[-1]
    for i in range(1, periods + 1):
        future_x = len(history) - 1 + i
        projected_value = slope * future_x + intercept
        future_date = last_date + median_gap * i
        future_rows.append({date_col: future_date, value_col: projected_value, "is_forecast": True})

    forecast_df = pd.DataFrame(future_rows)
    combined = pd.concat(
        [history[[date_col, value_col, "is_forecast"]], forecast_df], ignore_index=True
    )
    return combined


def trend_direction(df: pd.DataFrame, value_col: str) -> str:
    """Returns 'increasing', 'decreasing', or 'flat' based on the sign and
    magnitude of a linear fit's slope relative to the series mean."""
    values = df[value_col].astype(float).values
    if len(values) < 2:
        return "flat"
    x = np.arange(len(values))
    slope, _ = np.polyfit(x, values, 1)
    mean = values.mean() if values.mean() != 0 else 1.0
    relative_slope = slope / abs(mean)
    if relative_slope > 0.02:
        return "increasing"
    elif relative_slope < -0.02:
        return "decreasing"
    return "flat"
