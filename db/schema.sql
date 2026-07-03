-- Schema for the AI Data Analyst Agent demo dataset.
-- Sales, HR, and operations tables for a fictional mid-size company.

DROP TABLE IF EXISTS sales_orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS attrition_events CASCADE;
DROP TABLE IF EXISTS hiring_requisitions CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS regions CASCADE;

CREATE TABLE regions (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL
);

CREATE TABLE departments (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    cost_center TEXT NOT NULL,
    region_id   INTEGER NOT NULL REFERENCES regions(id)
);

CREATE TABLE employees (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    department_id       INTEGER NOT NULL REFERENCES departments(id),
    hire_date           DATE NOT NULL,
    termination_date    DATE,
    salary              NUMERIC(12, 2) NOT NULL,
    job_title           TEXT NOT NULL,
    region_id           INTEGER NOT NULL REFERENCES regions(id)
);

CREATE TABLE hiring_requisitions (
    id              INTEGER PRIMARY KEY,
    department_id   INTEGER NOT NULL REFERENCES departments(id),
    opened_date     DATE NOT NULL,
    filled_date     DATE,
    role_title      TEXT NOT NULL,
    status          TEXT NOT NULL
);

CREATE TABLE attrition_events (
    id              INTEGER PRIMARY KEY,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    event_date      DATE NOT NULL,
    reason          TEXT NOT NULL
);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit_price  NUMERIC(12, 2) NOT NULL
);

CREATE TABLE sales_orders (
    id          INTEGER PRIMARY KEY,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    region_id   INTEGER NOT NULL REFERENCES regions(id),
    order_date  DATE NOT NULL,
    quantity    INTEGER NOT NULL,
    revenue     NUMERIC(14, 2) NOT NULL
);

-- Indexes on date columns and foreign keys for the query patterns the
-- SQL generator produces (time series grouping, joins on region/department).
CREATE INDEX idx_employees_department_id ON employees(department_id);
CREATE INDEX idx_employees_region_id ON employees(region_id);
CREATE INDEX idx_employees_hire_date ON employees(hire_date);
CREATE INDEX idx_employees_termination_date ON employees(termination_date);

CREATE INDEX idx_hiring_req_department_id ON hiring_requisitions(department_id);
CREATE INDEX idx_hiring_req_opened_date ON hiring_requisitions(opened_date);

CREATE INDEX idx_attrition_employee_id ON attrition_events(employee_id);
CREATE INDEX idx_attrition_event_date ON attrition_events(event_date);

CREATE INDEX idx_sales_orders_product_id ON sales_orders(product_id);
CREATE INDEX idx_sales_orders_region_id ON sales_orders(region_id);
CREATE INDEX idx_sales_orders_order_date ON sales_orders(order_date);

CREATE INDEX idx_departments_region_id ON departments(region_id);
