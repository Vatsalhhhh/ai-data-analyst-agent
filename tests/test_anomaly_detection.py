import pandas as pd

from core.analysis import detect_anomalies


def test_known_outlier_is_flagged_and_normal_points_are_not():
    dates = pd.date_range("2024-01-01", periods=12, freq="MS")
    values = [100, 102, 98, 101, 99, 103, 97, 100, 101, 99, 100, 400]  # last point is a clear outlier

    df = pd.DataFrame({"month": dates, "value": values})
    result = detect_anomalies(df, value_col="value", date_col="month")

    outlier_row = result[result["value"] == 400].iloc[0]
    assert outlier_row["is_anomaly"] == True  # noqa: E712

    normal_rows = result[result["value"] != 400]
    assert not normal_rows["is_anomaly"].any()


def test_flat_series_has_no_anomalies():
    dates = pd.date_range("2024-01-01", periods=6, freq="MS")
    values = [50, 50, 50, 50, 50, 50]

    df = pd.DataFrame({"month": dates, "value": values})
    result = detect_anomalies(df, value_col="value", date_col="month")

    assert not result["is_anomaly"].any()


def test_short_series_does_not_crash():
    dates = pd.date_range("2024-01-01", periods=2, freq="MS")
    values = [10, 500]

    df = pd.DataFrame({"month": dates, "value": values})
    result = detect_anomalies(df, value_col="value", date_col="month")

    # With fewer than 3 points, we don't attempt a z-score -- just confirm
    # it doesn't error and returns a sane shape.
    assert len(result) == 2
    assert "is_anomaly" in result.columns
