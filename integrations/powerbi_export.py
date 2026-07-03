"""
Exports the Postgres data as a clean star schema of CSVs suitable for
import into Power BI (or any BI tool that prefers fact/dim tables over a
normalized OLTP schema).

Run standalone:
    python integrations/powerbi_export.py

Writes to exports/powerbi/:
    dim_date.csv
    dim_region.csv
    dim_department.csv
    dim_employee.csv
    dim_product.csv
    fact_sales.csv
    fact_attrition.csv
"""

import os
import sys

# Allow running as `python integrations/powerbi_export.py` directly, without
# the package installed or PYTHONPATH set.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from core.db import get_readonly_connection

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports", "powerbi")


def _read_table(conn, query: str) -> pd.DataFrame:
    # psycopg2 connections work fine with read_sql; pandas just warns that
    # it's only tested against SQLAlchemy engines. Safe to ignore here.
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.read_sql(query, conn)


def build_dim_date(min_date, max_date) -> pd.DataFrame:
    dates = pd.date_range(start=min_date, end=max_date, freq="D")
    return pd.DataFrame(
        {
            "date_key": dates.strftime("%Y%m%d").astype(int),
            "date": dates,
            "year": dates.year,
            "quarter": dates.quarter,
            "month": dates.month,
            "month_name": dates.strftime("%B"),
            "day": dates.day,
            "day_of_week": dates.strftime("%A"),
            "is_weekend": dates.dayofweek >= 5,
        }
    )


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    conn = get_readonly_connection()

    regions = _read_table(conn, "SELECT * FROM regions;")
    departments = _read_table(conn, "SELECT * FROM departments;")
    employees = _read_table(conn, "SELECT * FROM employees;")
    products = _read_table(conn, "SELECT * FROM products;")
    sales_orders = _read_table(conn, "SELECT * FROM sales_orders;")
    attrition_events = _read_table(conn, "SELECT * FROM attrition_events;")

    conn.close()

    # Dimension tables -- renamed/id-keyed the way Power BI star schemas expect.
    dim_region = regions.rename(columns={"id": "region_key"})
    dim_department = departments.rename(columns={"id": "department_key"})
    dim_product = products.rename(columns={"id": "product_key"})
    dim_employee = employees.rename(columns={"id": "employee_key"})[
        ["employee_key", "name", "department_id", "hire_date", "termination_date", "salary", "job_title", "region_id"]
    ]

    all_dates = pd.concat([sales_orders["order_date"], attrition_events["event_date"]]).dropna()
    min_date, max_date = all_dates.min(), all_dates.max()
    dim_date = build_dim_date(min_date, max_date)

    # Fact tables.
    fact_sales = sales_orders.rename(
        columns={"id": "sales_key", "product_id": "product_key", "region_id": "region_key"}
    ).copy()
    fact_sales["date_key"] = pd.to_datetime(fact_sales["order_date"]).dt.strftime("%Y%m%d").astype(int)

    fact_attrition = attrition_events.rename(
        columns={"id": "attrition_key", "employee_id": "employee_key"}
    ).copy()
    fact_attrition["date_key"] = pd.to_datetime(fact_attrition["event_date"]).dt.strftime("%Y%m%d").astype(int)

    outputs = {
        "dim_date.csv": dim_date,
        "dim_region.csv": dim_region,
        "dim_department.csv": dim_department,
        "dim_employee.csv": dim_employee,
        "dim_product.csv": dim_product,
        "fact_sales.csv": fact_sales,
        "fact_attrition.csv": fact_attrition,
    }

    print("Power BI export:")
    for filename, df in outputs.items():
        path = os.path.join(EXPORT_DIR, filename)
        df.to_csv(path, index=False)
        print(f"  {filename:<22} {len(df):>8} rows -> {path}")


if __name__ == "__main__":
    main()
