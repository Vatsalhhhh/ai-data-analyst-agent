import pytest

from core.pipeline import run_pipeline
from tests.db_helpers import DB_AVAILABLE

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres is not reachable")


def test_trend_question_includes_a_forecast():
    result = run_pipeline("Show sales trend")

    assert result["forecast"] is not None
    assert len(result["forecast"]) == 3
    for point in result["forecast"]:
        assert point["is_forecast"] is True

    assert "projected" in result["insight"].lower()


def test_non_time_series_question_has_no_forecast():
    result = run_pipeline("Show sales by region")

    assert result["forecast"] is None
