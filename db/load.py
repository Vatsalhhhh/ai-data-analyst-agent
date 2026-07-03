"""
Applies the schema and loads the generated CSVs into Postgres.

Usage:
    python db/load.py

Reads connection settings from .env (via python-dotenv). Expects the CSVs
in data/csv/ to already exist -- run data/generate_dataset.py first if not.

Steps:
    1. Connect as the admin user.
    2. Apply schema.sql (drops and recreates tables).
    3. Apply roles.sql, substituting the read-only password from the
       environment so no real credential is hardcoded in the SQL file.
    4. Truncate + COPY each CSV into its matching table, in FK-safe order.
    5. Print row counts per table as a sanity check.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(BASE_DIR, "data", "csv")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
ROLES_PATH = os.path.join(os.path.dirname(__file__), "roles.sql")

# Order matters: parents before children, to satisfy foreign keys.
TABLE_LOAD_ORDER = [
    "regions",
    "departments",
    "employees",
    "hiring_requisitions",
    "attrition_events",
    "products",
    "sales_orders",
]


def get_admin_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "analyst_db"),
        user=os.getenv("POSTGRES_USER", "analyst_admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme_local_only"),
    )


def apply_schema(conn):
    with open(SCHEMA_PATH) as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("Schema applied.")


def apply_roles(conn):
    with open(ROLES_PATH) as f:
        roles_sql = f.read()

    ro_password = os.getenv("POSTGRES_RO_PASSWORD", "changeme_readonly")
    db_name = os.getenv("POSTGRES_DB", "analyst_db")

    # Substitute the placeholder password/db name with the real values from
    # the environment so we don't hardcode a credential in the SQL file.
    roles_sql = roles_sql.replace("changeme_readonly", ro_password)
    roles_sql = roles_sql.replace("analyst_db", db_name)

    with conn.cursor() as cur:
        cur.execute(roles_sql)
    conn.commit()
    print("Read-only role (analyst_ro) created/updated.")


def load_csv_into_table(conn, table_name):
    csv_path = os.path.join(CSV_DIR, f"{table_name}.csv")
    if not os.path.exists(csv_path):
        print(f"  WARNING: {csv_path} not found, skipping {table_name}.")
        return 0

    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE;")
        with open(csv_path) as f:
            cur.copy_expert(
                f"COPY {table_name} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
                f,
            )
        cur.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cur.fetchone()[0]
    conn.commit()
    return count


def main():
    try:
        conn = get_admin_connection()
    except psycopg2.OperationalError as e:
        print(f"Could not connect to Postgres: {e}")
        print("Make sure `docker compose up -d` has been run and the DB is healthy.")
        sys.exit(1)

    apply_schema(conn)
    apply_roles(conn)

    print("\nLoading CSVs:")
    counts = {}
    for table in TABLE_LOAD_ORDER:
        count = load_csv_into_table(conn, table)
        counts[table] = count
        print(f"  {table:<22} {count:>8} rows")

    conn.close()

    print("\nDone. Row counts:")
    for table, count in counts.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
