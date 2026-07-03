import pytest

from core.sql_generator import SQLSafetyViolation, validate_sql_safety


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE employees;",
        "DELETE FROM employees WHERE id = 1;",
        "INSERT INTO employees (id, name) VALUES (1, 'x');",
        "UPDATE employees SET salary = 0;",
        "ALTER TABLE employees ADD COLUMN x TEXT;",
        "TRUNCATE TABLE employees;",
        "GRANT ALL ON employees TO public;",
        "CREATE TABLE evil (id INT);",
    ],
)
def test_rejects_mutating_statements(sql):
    with pytest.raises(SQLSafetyViolation):
        validate_sql_safety(sql)


def test_rejects_statement_injection():
    with pytest.raises(SQLSafetyViolation):
        validate_sql_safety("SELECT 1; DROP TABLE employees;")


def test_rejects_statement_injection_with_where_clause():
    with pytest.raises(SQLSafetyViolation):
        validate_sql_safety("SELECT * FROM employees WHERE id = 1; DELETE FROM employees;")


def test_accepts_legit_select():
    sql = "SELECT * FROM employees WHERE department_id = 1 LIMIT 10;"
    assert validate_sql_safety(sql) == sql


def test_accepts_select_with_cte():
    sql = """
        WITH recent AS (SELECT * FROM employees WHERE hire_date > '2024-01-01')
        SELECT * FROM recent LIMIT 10;
    """
    # Should not raise.
    validate_sql_safety(sql)


def test_rejects_empty_query():
    with pytest.raises(SQLSafetyViolation):
        validate_sql_safety("")


def test_rejects_comment_only_query():
    with pytest.raises(SQLSafetyViolation):
        validate_sql_safety("-- just a comment")
