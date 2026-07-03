"""
Generates a synthetic company dataset (sales + HR + operations) as CSVs.

The data spans roughly three years and is built with a fixed random seed so
runs are reproducible. A few real, deliberate patterns are baked into the
generation logic itself (not just labeled after the fact) so that the
downstream analysis code has genuine signal to detect:

  - An attrition spike in Q3 of the second year, caused by an actual burst
    of termination events in that quarter.
  - A sales dip in the "West" region for two consecutive quarters, caused by
    actually shrinking order volume and revenue for that region/period.
  - Seasonality: Q4 (holiday quarter) gets a genuine bump in order volume
    across all regions.

Run standalone:

    python data/generate_dataset.py

Output lands in data/csv/.
"""

import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "csv")

START_DATE = date(2023, 1, 1)
END_DATE = date(2025, 12, 31)

# Quarter used for the injected attrition spike (year, quarter)
ATTRITION_SPIKE_YEAR = 2024
ATTRITION_SPIKE_QUARTER = 3

# Region + quarters used for the injected sales dip
SALES_DIP_REGION_NAME = "West"
SALES_DIP_PERIODS = [(2024, 2), (2024, 3)]  # (year, quarter) pairs


def daterange_quarter(year, quarter):
    """Return (start_date, end_date) for a calendar quarter."""
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    if start_month + 3 > 12:
        end = date(year, 12, 31)
    else:
        end_month = start_month + 3
        end = date(year, end_month, 1) - timedelta(days=1)
    return start, end


def quarter_of(d):
    return (d.year, (d.month - 1) // 3 + 1)


def random_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def build_regions():
    rows = [
        {"id": 1, "name": "North", "country": "USA"},
        {"id": 2, "name": "South", "country": "USA"},
        {"id": 3, "name": "East", "country": "USA"},
        {"id": 4, "name": "West", "country": "USA"},
        {"id": 5, "name": "EMEA", "country": "Germany"},
        {"id": 6, "name": "APAC", "country": "Singapore"},
    ]
    return pd.DataFrame(rows)


def build_departments(regions_df):
    dept_names = [
        ("Sales", "CC-100"),
        ("Engineering", "CC-200"),
        ("Customer Support", "CC-300"),
        ("Marketing", "CC-400"),
        ("Operations", "CC-500"),
        ("Finance", "CC-600"),
        ("Human Resources", "CC-700"),
    ]
    rows = []
    for i, (name, cc) in enumerate(dept_names, start=1):
        region_id = int(regions_df.sample(1, random_state=SEED + i)["id"].iloc[0])
        rows.append({"id": i, "name": name, "cost_center": cc, "region_id": region_id})
    return pd.DataFrame(rows)


def build_employees(departments_df, regions_df, n=420):
    job_titles_by_dept = {
        "Sales": ["Account Executive", "Sales Manager", "SDR"],
        "Engineering": ["Software Engineer", "Senior Engineer", "Engineering Manager", "QA Engineer"],
        "Customer Support": ["Support Specialist", "Support Team Lead"],
        "Marketing": ["Marketing Specialist", "Content Strategist", "Marketing Manager"],
        "Operations": ["Operations Analyst", "Operations Manager"],
        "Finance": ["Financial Analyst", "Accountant", "Finance Manager"],
        "Human Resources": ["HR Generalist", "Recruiter", "HR Manager"],
    }
    salary_bands = {
        "Account Executive": (55000, 90000),
        "Sales Manager": (85000, 130000),
        "SDR": (45000, 65000),
        "Software Engineer": (90000, 140000),
        "Senior Engineer": (130000, 175000),
        "Engineering Manager": (150000, 190000),
        "QA Engineer": (75000, 105000),
        "Support Specialist": (42000, 60000),
        "Support Team Lead": (60000, 80000),
        "Marketing Specialist": (55000, 75000),
        "Content Strategist": (60000, 85000),
        "Marketing Manager": (90000, 125000),
        "Operations Analyst": (60000, 85000),
        "Operations Manager": (95000, 130000),
        "Financial Analyst": (65000, 95000),
        "Accountant": (60000, 85000),
        "Finance Manager": (100000, 140000),
        "HR Generalist": (55000, 75000),
        "Recruiter": (55000, 80000),
        "HR Manager": (90000, 120000),
    }

    rows = []
    for i in range(1, n + 1):
        dept = departments_df.sample(1, random_state=SEED * i % (2**31)).iloc[0]
        job_title = random.choice(job_titles_by_dept[dept["name"]])
        lo, hi = salary_bands[job_title]
        salary = round(random.uniform(lo, hi), 2)
        region_id = int(dept["region_id"])

        hire_date = random_date(START_DATE, END_DATE - timedelta(days=30))

        # Base termination probability; the attrition spike logic below
        # overrides this for a chunk of employees to actually create a
        # concentrated burst of terminations in the target quarter.
        termination_date = None
        if random.random() < 0.22:
            earliest_term = hire_date + timedelta(days=60)
            if earliest_term < END_DATE:
                termination_date = random_date(earliest_term, END_DATE)

        rows.append(
            {
                "id": i,
                "name": fake.name(),
                "department_id": int(dept["id"]),
                "hire_date": hire_date,
                "termination_date": termination_date,
                "salary": salary,
                "job_title": job_title,
                "region_id": region_id,
            }
        )

    df = pd.DataFrame(rows)

    # --- Inject a real attrition spike ---
    # Force a batch of additional employees (on top of the natural rate above)
    # to terminate specifically within the target quarter, simulating a
    # genuine event (e.g. a reduction-in-force or a wave of resignations).
    spike_start, spike_end = daterange_quarter(ATTRITION_SPIKE_YEAR, ATTRITION_SPIKE_QUARTER)
    eligible = df[
        (df["termination_date"].isna()) & (df["hire_date"] < spike_start - timedelta(days=60))
    ]
    spike_headcount = min(int(n * 0.14), len(eligible))
    spike_ids = eligible.sample(n=spike_headcount, random_state=SEED).index
    for idx in spike_ids:
        df.at[idx, "termination_date"] = random_date(spike_start, spike_end)

    return df


def build_attrition_events(employees_df):
    reasons = [
        "voluntary_resignation",
        "involuntary_termination",
        "retirement",
        "restructuring",
        "relocation",
    ]
    spike_start, spike_end = daterange_quarter(ATTRITION_SPIKE_YEAR, ATTRITION_SPIKE_QUARTER)

    rows = []
    eid = 1
    for _, emp in employees_df.iterrows():
        if pd.isna(emp["termination_date"]):
            continue
        term_date = emp["termination_date"]
        if isinstance(term_date, str):
            term_date = date.fromisoformat(term_date)

        if spike_start <= term_date <= spike_end:
            # Terminations during the spike skew toward restructuring /
            # involuntary, consistent with a genuine RIF-driven spike.
            reason = np.random.choice(
                reasons, p=[0.20, 0.30, 0.05, 0.40, 0.05]
            )
        else:
            reason = np.random.choice(
                reasons, p=[0.55, 0.15, 0.10, 0.05, 0.15]
            )

        rows.append(
            {
                "id": eid,
                "employee_id": int(emp["id"]),
                "event_date": term_date,
                "reason": reason,
            }
        )
        eid += 1

    return pd.DataFrame(rows)


def build_hiring_requisitions(departments_df, n=260):
    rows = []
    for i in range(1, n + 1):
        dept = departments_df.sample(1, random_state=(SEED + i) % (2**31)).iloc[0]
        opened = random_date(START_DATE, END_DATE - timedelta(days=10))
        # Roughly 75% of requisitions get filled within 20-90 days; the rest
        # stay open (nullable filled_date), which is realistic.
        filled_date = None
        status = "open"
        if random.random() < 0.75:
            fill_days = random.randint(20, 90)
            candidate_fill = opened + timedelta(days=fill_days)
            if candidate_fill <= END_DATE:
                filled_date = candidate_fill
                status = "filled"
        if filled_date is None and (END_DATE - opened).days > 120:
            # Old open reqs that never got filled are marked cancelled some
            # of the time, for realism.
            if random.random() < 0.3:
                status = "cancelled"

        rows.append(
            {
                "id": i,
                "department_id": int(dept["id"]),
                "opened_date": opened,
                "filled_date": filled_date,
                "role_title": fake.job(),
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def build_products(n=40):
    categories = ["Hardware", "Software", "Services", "Accessories"]
    rows = []
    for i in range(1, n + 1):
        category = random.choice(categories)
        base_price = {
            "Hardware": (150, 1200),
            "Software": (50, 600),
            "Services": (200, 2000),
            "Accessories": (10, 120),
        }[category]
        unit_price = round(random.uniform(*base_price), 2)
        rows.append(
            {
                "id": i,
                "name": f"{fake.word().capitalize()} {category[:-1] if category.endswith('s') else category} {i}",
                "category": category,
                "unit_price": unit_price,
            }
        )
    return pd.DataFrame(rows)


def build_sales_orders(products_df, regions_df, n_days=None):
    """
    Generates one or more orders per day per region, with:
      - Holiday-quarter (Q4) seasonality bump applied to every region.
      - A genuine, sustained volume/revenue dip for the West region during
        the configured dip quarters (SALES_DIP_PERIODS).
    """
    rows = []
    order_id = 1
    current = START_DATE
    region_ids = regions_df["id"].tolist()
    region_names = dict(zip(regions_df["id"], regions_df["name"]))
    product_ids = products_df["id"].tolist()
    product_prices = dict(zip(products_df["id"], products_df["unit_price"]))

    dip_region_id = int(regions_df[regions_df["name"] == SALES_DIP_REGION_NAME]["id"].iloc[0])

    while current <= END_DATE:
        yr, q = quarter_of(current)
        is_holiday_quarter = q == 4

        for region_id in region_ids:
            # Baseline orders per day per region
            base_orders_today = np.random.poisson(lam=3.2)

            # Seasonality: holiday quarter (Q4) bump, ~45% more volume.
            if is_holiday_quarter:
                base_orders_today = int(round(base_orders_today * 1.45))

            # Injected sales dip: West region during configured quarters
            # gets order volume scaled down materially (real reduction in
            # generated rows/quantities, not a cosmetic label).
            if region_id == dip_region_id and (yr, q) in SALES_DIP_PERIODS:
                base_orders_today = int(round(base_orders_today * 0.40))

            for _ in range(base_orders_today):
                product_id = random.choice(product_ids)
                unit_price = product_prices[product_id]
                quantity = np.random.randint(1, 12)

                revenue_multiplier = 1.0
                if region_id == dip_region_id and (yr, q) in SALES_DIP_PERIODS:
                    # Not just fewer orders, but smaller order sizes too.
                    quantity = max(1, int(round(quantity * 0.5)))

                revenue = round(unit_price * quantity * revenue_multiplier, 2)

                rows.append(
                    {
                        "id": order_id,
                        "product_id": product_id,
                        "region_id": region_id,
                        "order_date": current,
                        "quantity": quantity,
                        "revenue": revenue,
                    }
                )
                order_id += 1

        current += timedelta(days=1)

    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    regions_df = build_regions()
    departments_df = build_departments(regions_df)
    employees_df = build_employees(departments_df, regions_df)
    attrition_df = build_attrition_events(employees_df)
    requisitions_df = build_hiring_requisitions(departments_df)
    products_df = build_products()
    sales_df = build_sales_orders(products_df, regions_df)

    regions_df.to_csv(os.path.join(OUT_DIR, "regions.csv"), index=False)
    departments_df.to_csv(os.path.join(OUT_DIR, "departments.csv"), index=False)
    employees_df.to_csv(os.path.join(OUT_DIR, "employees.csv"), index=False)
    attrition_df.to_csv(os.path.join(OUT_DIR, "attrition_events.csv"), index=False)
    requisitions_df.to_csv(os.path.join(OUT_DIR, "hiring_requisitions.csv"), index=False)
    products_df.to_csv(os.path.join(OUT_DIR, "products.csv"), index=False)
    sales_df.to_csv(os.path.join(OUT_DIR, "sales_orders.csv"), index=False)

    print("Dataset generated:")
    print(f"  regions:              {len(regions_df):>6} rows")
    print(f"  departments:          {len(departments_df):>6} rows")
    print(f"  employees:            {len(employees_df):>6} rows")
    print(f"  attrition_events:     {len(attrition_df):>6} rows")
    print(f"  hiring_requisitions:  {len(requisitions_df):>6} rows")
    print(f"  products:             {len(products_df):>6} rows")
    print(f"  sales_orders:         {len(sales_df):>6} rows")
    print(f"\nCSV files written to {OUT_DIR}")
    print(
        f"\nInjected attrition spike: {ATTRITION_SPIKE_YEAR} Q{ATTRITION_SPIKE_QUARTER}"
    )
    print(
        f"Injected sales dip: {SALES_DIP_REGION_NAME} region during "
        f"{', '.join(f'{y} Q{q}' for y, q in SALES_DIP_PERIODS)}"
    )


if __name__ == "__main__":
    main()
