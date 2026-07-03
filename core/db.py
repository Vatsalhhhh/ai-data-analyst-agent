"""
Database connection helpers. All application queries go through the
read-only role (analyst_ro) with a statement timeout, so a bad or
adversarial query can't run away or mutate data.
"""

import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DEFAULT_STATEMENT_TIMEOUT_MS = 8000
DEFAULT_ROW_LIMIT = 500


def get_connection_params():
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "dbname": os.getenv("POSTGRES_DB", "analyst_db"),
        "user": os.getenv("POSTGRES_RO_USER", "analyst_ro"),
        "password": os.getenv("POSTGRES_RO_PASSWORD", "changeme_readonly"),
    }


def get_readonly_connection():
    return psycopg2.connect(**get_connection_params())


def check_db_connectivity() -> bool:
    """Used by the /health endpoint. Returns True if a connection + trivial
    query succeeds, False otherwise (never raises)."""
    try:
        conn = get_readonly_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        conn.close()
        return True
    except Exception:
        return False


def run_query(sql: str, statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS) -> pd.DataFrame:
    """
    Executes a SQL query using the read-only role and returns the results
    as a DataFrame. Caller is responsible for having already validated the
    SQL with core.sql_generator.validate_sql_safety.
    """
    conn = get_readonly_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("BEGIN;")
            cur.execute(f"SET LOCAL statement_timeout = {int(statement_timeout_ms)};")
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
            cur.execute("COMMIT;")
        return pd.DataFrame(rows, columns=columns)
    finally:
        conn.close()


def introspect_schema() -> dict:
    """
    Returns a dict of {table_name: [(column_name, data_type), ...]} for all
    tables in the public schema, used to build a schema-aware prompt for
    the LLM SQL generation path.
    """
    conn = get_readonly_connection()
    schema = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
                """
            )
            for table_name, column_name, data_type in cur.fetchall():
                schema.setdefault(table_name, []).append((column_name, data_type))
    finally:
        conn.close()
    return schema
