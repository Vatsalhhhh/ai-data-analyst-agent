import os

import pytest

from core.db import run_query
from core.sql_generator import generate_sql_fallback, validate_sql_safety
from tests.db_helpers import DB_AVAILABLE

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="Postgres is not reachable")


@pytest.mark.parametrize(
    "question",
    [
        "Show hiring trends",
        "Why did attrition increase?",
        "Show sales by region",
        "Show sales trend",
        "What is the average salary by department?",
    ],
)
def test_fallback_template_executes_against_real_db(question):
    sql = generate_sql_fallback(question)
    validate_sql_safety(sql)  # should not raise

    df = run_query(sql)

    assert df is not None
    assert len(df.columns) >= 2
    assert len(df) > 0


def test_attrition_query_reflects_injected_spike():
    """The dataset generator deliberately injects an attrition spike in
    2024 Q3. Confirm the fallback query surfaces it as the clear maximum."""
    sql = generate_sql_fallback("Why did attrition increase this quarter?")
    df = run_query(sql)

    df["quarter"] = df["quarter"].astype(str)
    max_row = df.loc[df["termination_count"].idxmax()]

    assert "2024-07-01" in max_row["quarter"]
    assert max_row["termination_count"] > df["termination_count"].mean() * 2


def test_sales_by_region_reflects_injected_dip():
    """The dataset generator deliberately shrinks West region sales in
    2024 Q2/Q3. Confirm West region total revenue is the lowest overall."""
    sql = generate_sql_fallback("Show sales by region")
    df = run_query(sql)

    min_region = df.loc[df["total_revenue"].astype(float).idxmin(), "region"]
    assert min_region == "West"
