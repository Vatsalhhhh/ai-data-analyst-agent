"""
Translates a natural-language question into a read-only SQL SELECT query.

Two paths:
  - If OPENAI_API_KEY is set, use langchain + openai with a schema-aware
    prompt built from the live Postgres schema (via core.db.introspect_schema).
  - Otherwise, fall back to a deterministic set of query templates matched
    against keywords in the question. This keeps the whole project usable
    with zero external API cost/dependency.

Both paths run their output through validate_sql_safety before anything
gets near the database.
"""

import os
import re

from core.db import introspect_schema

DEFAULT_ROW_LIMIT = 500


class SQLSafetyViolation(Exception):
    """Raised when generated or user-influenced SQL fails the safety guard."""


_FORBIDDEN_KEYWORDS = [
    "drop", "delete", "insert", "update", "alter", "truncate", "grant",
    "revoke", "create", "exec", "execute", "call", "copy", "vacuum",
    "attach", "detach", "reindex", "cluster", "listen", "notify",
    "do", "merge",
]

# Match forbidden keywords only as whole words (not substrings like
# "created_at" containing "create").
_FORBIDDEN_PATTERN = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE
)


def _strip_sql_comments(sql: str) -> str:
    """Removes -- line comments and /* */ block comments, since comments
    can be used to smuggle a second statement or hide forbidden keywords
    from a naive check."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def validate_sql_safety(sql: str) -> str:
    """
    Validates that `sql` is a single, read-only SELECT statement.

    Raises SQLSafetyViolation on any violation. Returns the (trimmed) SQL
    unchanged if it passes.
    """
    if not sql or not sql.strip():
        raise SQLSafetyViolation("Empty SQL query.")

    original = sql
    cleaned = _strip_sql_comments(sql).strip()

    if not cleaned:
        raise SQLSafetyViolation("Query contained only comments.")

    # Reject multiple statements. Allow a single trailing semicolon.
    body = cleaned[:-1] if cleaned.endswith(";") else cleaned
    if ";" in body:
        raise SQLSafetyViolation(
            "Multiple SQL statements are not allowed (statement injection detected)."
        )

    if not re.match(r"^\s*(with\b.*?\)\s*select\b|select\b)", body, re.IGNORECASE | re.DOTALL):
        raise SQLSafetyViolation("Only single SELECT (optionally with a leading WITH/CTE) statements are allowed.")

    match = _FORBIDDEN_PATTERN.search(body)
    if match:
        raise SQLSafetyViolation(f"Forbidden keyword detected: '{match.group(0)}'.")

    return original.strip()


def _ensure_row_limit(sql: str, limit: int = DEFAULT_ROW_LIMIT) -> str:
    """Appends a LIMIT clause if the query doesn't already have one."""
    stripped = sql.rstrip().rstrip(";")
    if re.search(r"\blimit\s+\d+\s*$", stripped, re.IGNORECASE):
        return stripped + ";"
    return f"{stripped}\nLIMIT {limit};"


# ---------------------------------------------------------------------------
# Fallback: deterministic keyword-matched templates
# ---------------------------------------------------------------------------

def _fallback_hiring_trend() -> str:
    return """
        SELECT date_trunc('month', opened_date) AS month,
               COUNT(*) AS requisitions_opened
        FROM hiring_requisitions
        GROUP BY month
        ORDER BY month
    """.strip()


def _fallback_attrition_by_quarter() -> str:
    return """
        SELECT date_trunc('quarter', event_date) AS quarter,
               COUNT(*) AS termination_count
        FROM attrition_events
        GROUP BY quarter
        ORDER BY quarter
    """.strip()


def _fallback_sales_by_region() -> str:
    return """
        SELECT r.name AS region,
               SUM(so.revenue) AS total_revenue,
               SUM(so.quantity) AS total_quantity
        FROM sales_orders so
        JOIN regions r ON so.region_id = r.id
        GROUP BY r.name
        ORDER BY total_revenue DESC
    """.strip()


def _fallback_sales_trend() -> str:
    return """
        SELECT date_trunc('month', order_date) AS month,
               SUM(revenue) AS monthly_revenue
        FROM sales_orders
        GROUP BY month
        ORDER BY month
    """.strip()


def _fallback_headcount_by_department() -> str:
    return """
        SELECT d.name AS department,
               COUNT(*) AS active_employees
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        WHERE e.termination_date IS NULL
        GROUP BY d.name
        ORDER BY active_employees DESC
    """.strip()


def _fallback_salary_by_department() -> str:
    return """
        SELECT d.name AS department,
               ROUND(AVG(e.salary), 2) AS avg_salary
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        GROUP BY d.name
        ORDER BY avg_salary DESC
    """.strip()


def _fallback_top_products() -> str:
    return """
        SELECT p.name AS product,
               p.category AS category,
               SUM(so.revenue) AS total_revenue
        FROM sales_orders so
        JOIN products p ON so.product_id = p.id
        GROUP BY p.name, p.category
        ORDER BY total_revenue DESC
    """.strip()


def generate_sql_fallback(question: str) -> str:
    """
    Deterministic, keyword-driven SQL generation. Real templates against the
    actual schema -- not stubs -- so this path is genuinely useful with zero
    external dependency.
    """
    q = question.lower()

    def has_all(*words):
        return all(w in q for w in words)

    def has_any(*words):
        return any(w in q for w in words)

    if has_any("hiring", "requisition", "open role", "open roles") and has_any("trend", "over time", "by month"):
        sql = _fallback_hiring_trend()
    elif has_all("hiring") or has_all("requisition"):
        sql = _fallback_hiring_trend()
    elif has_any("attrition", "termination", "turnover") and has_any("quarter", "increase", "trend", "why"):
        sql = _fallback_attrition_by_quarter()
    elif has_any("attrition", "termination", "turnover"):
        sql = _fallback_attrition_by_quarter()
    elif has_all("sales") and has_any("region", "by region"):
        sql = _fallback_sales_by_region()
    elif has_any("revenue over time", "sales trend", "monthly revenue", "revenue trend"):
        sql = _fallback_sales_trend()
    elif has_all("sales") and has_any("trend", "over time"):
        sql = _fallback_sales_trend()
    elif has_any("headcount", "how many employees", "active employees"):
        sql = _fallback_headcount_by_department()
    elif has_any("salary", "compensation", "pay") and has_any("department", "average", "avg"):
        sql = _fallback_salary_by_department()
    elif has_any("top product", "best selling", "best-selling", "product revenue"):
        sql = _fallback_top_products()
    else:
        # Generic default: overall monthly revenue trend, always answerable
        # against this schema regardless of phrasing.
        sql = _fallback_sales_trend()

    return _ensure_row_limit(sql)


# ---------------------------------------------------------------------------
# LLM path (used only if OPENAI_API_KEY is configured)
# ---------------------------------------------------------------------------

def _build_schema_prompt_text() -> str:
    schema = introspect_schema()
    lines = []
    for table, columns in schema.items():
        col_desc = ", ".join(f"{name} ({dtype})" for name, dtype in columns)
        lines.append(f"- {table}: {col_desc}")
    return "\n".join(lines)


def generate_sql_llm(question: str) -> str:
    """
    Uses langchain + openai to generate a single read-only SQL SELECT
    query, grounded in the live schema. Only called if OPENAI_API_KEY is
    present in the environment.
    """
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate

    schema_text = _build_schema_prompt_text()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a SQL analyst assistant for a Postgres database. "
                "You write a single read-only SELECT query (optionally with a "
                "leading WITH clause) that answers the user's question. "
                "Never write DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE, "
                "GRANT, or any statement other than SELECT. Never write more "
                "than one statement. Only use the tables and columns listed "
                "below. Return ONLY the SQL query, no explanation, no markdown "
                "fences.\n\nSchema:\n{schema}",
            ),
            ("human", "{question}"),
        ]
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=os.getenv("OPENAI_API_KEY"))
    chain = prompt | llm

    response = chain.invoke({"schema": schema_text, "question": question})
    sql = response.content.strip()

    # Strip markdown fences if the model added them anyway.
    sql = re.sub(r"^```(sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)

    return _ensure_row_limit(sql.strip())


def generate_sql(question: str) -> str:
    """
    Main entry point. Chooses the LLM path if OPENAI_API_KEY is set,
    otherwise falls back to templates. Always validates safety before
    returning.
    """
    if os.getenv("OPENAI_API_KEY"):
        sql = generate_sql_llm(question)
    else:
        sql = generate_sql_fallback(question)

    validate_sql_safety(sql)
    return sql
