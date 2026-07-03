# AI Data Analyst Agent

A general-purpose data analyst agent: ask a question in plain English about
a company's sales, HR, and operations data, and it generates SQL, runs it
against Postgres, builds a chart, checks for anomalies and trends, and
writes an executive-style insight with a suggested next action. Results
can be pushed to Slack, emailed, or exported into a Power BI-ready star
schema.

It's demoed against a synthetic dataset (sales, hiring, attrition,
regions, products) with genuine, seeded trends and anomalies baked into
the generation logic -- not just labeled after the fact.

## Architecture

```
                 ┌─────────────────────┐
  NL question -> │   SQL Generator     │  (LLM-based if OPENAI_API_KEY set,
                 │  (core/sql_generator)│  otherwise deterministic templates)
                 └──────────┬──────────┘
                            │  validated (read-only, single statement)
                            v
                 ┌─────────────────────┐
                 │      Postgres        │  (analyst_ro role, statement timeout,
                 │   (core/db.py)       │   row limit)
                 └──────────┬──────────┘
                            v
                 ┌─────────────────────┐
                 │   Analysis           │  anomaly detection (z-score)
                 │  (core/analysis.py)  │  trend forecast (linear projection)
                 └──────────┬──────────┘
                            v
              ┌─────────────┴─────────────┐
              v                            v
   ┌────────────────────┐       ┌─────────────────────┐
   │  Chart (matplotlib) │       │  Insight + action    │
   │  (core/charts.py)   │       │  (core/insights.py)  │
   └──────────┬──────────┘       └──────────┬──────────┘
              └─────────────┬───────────────┘
                            v
                 ┌─────────────────────┐
                 │   FastAPI /ask       │ -> frontend chat UI
                 └──────────┬──────────┘
                            v
       ┌────────────────────┼────────────────────┐
       v                    v                     v
   Slack webhook       Email (SMTP or        Power BI export
   (integrations/      file report)          (star-schema CSVs)
    slack.py)           (integrations/        (integrations/
                         email_report.py)      powerbi_export.py)
```

## Feature list

- Synthetic dataset generator (Faker + pandas + numpy, seeded) covering
  sales, hiring, attrition, regions, departments, employees, and products
  across ~3 years, with an injected attrition spike, an injected regional
  sales dip, and holiday-quarter seasonality.
- Postgres schema with proper foreign keys and indexes on date/FK columns,
  plus a dedicated read-only (`analyst_ro`) role used at query time.
- Natural-language to SQL generation: LLM-based (langchain + OpenAI) when
  an API key is configured, or five-plus deterministic keyword-matched
  templates otherwise.
- A reusable SQL safety guard (`validate_sql_safety`) that rejects
  anything other than a single read-only `SELECT`/`WITH...SELECT`
  statement -- blocking DDL/DML keywords, statement injection via
  semicolons, and comment-based smuggling.
- Time-series anomaly detection (z-score based) and trend forecasting
  (linear regression via `numpy.polyfit`).
- Chart generation (matplotlib, headless `Agg` backend) saved as PNGs.
- Executive-summary insight generation with a suggested action, either
  LLM-polished or template-based using real computed statistics.
- FastAPI backend (`POST /ask`, `GET /health`) with CORS enabled and
  static chart serving.
- A minimal no-build-step HTML/JS chat frontend.
- Slack, email (SMTP or local HTML report), and Power BI (star-schema CSV
  export) integrations.
- A pytest suite covering SQL safety, fallback query correctness against a
  live database, anomaly detection, and integration no-op behavior.

## What requires `OPENAI_API_KEY` vs. what works offline

| Feature | Without `OPENAI_API_KEY` | With `OPENAI_API_KEY` |
|---|---|---|
| SQL generation | Deterministic keyword-matched templates (hiring trends, attrition by quarter, sales by region, sales trend, headcount, salary by department, top products) | Schema-aware LLM generation via langchain + OpenAI |
| Insight writing | Template-based summary using real computed min/max/mean/trend/anomaly numbers | LLM-polished executive summary, still grounded in the same computed stats |
| Everything else (DB, analysis, charts, API, frontend, Slack/email/Power BI) | Fully functional | Fully functional |

The project is designed to be genuinely useful and demoable with zero
external API cost -- the fallback path is not a stub.

## Setup

### 1. Start Postgres

```
docker compose up -d
```

Wait for the container to report healthy (`docker compose ps`).

By default the compose file reads connection settings from `.env`. Copy
the example first:

```
cp .env.example .env
```

If port 5432 is already in use on your machine, set `POSTGRES_PORT` in
`.env` to a free port (e.g. `5433`) -- docker-compose and `db/load.py`
both read it from the environment.

### 2. Generate the synthetic dataset

```
python data/generate_dataset.py
```

This writes CSVs to `data/csv/` (gitignored -- regenerate locally rather
than pulling from source control; the seed is fixed so output is
reproducible).

### 3. Load the data into Postgres

```
python db/load.py
```

This applies `db/schema.sql`, creates the read-only `analyst_ro` role via
`db/roles.sql`, and loads each CSV, printing row counts.

### 4. Run the API

```
pip install -r requirements.txt
uvicorn api.main:app --port 8010
```

(Adjust the port if `8010` is already used by something else on your
machine.)

### 5. Run the frontend

```
cd frontend
python -m http.server 8020
```

Open `http://127.0.0.1:8020` in a browser. Update `API_BASE_URL` at the
top of `frontend/app.js` if your API is running on a different host/port.
The frontend can also just be opened directly as a file, since it only
makes cross-origin fetch calls to the API (CORS is enabled on the
backend).

### 6. Run the tests

```
pytest -v
```

The fallback SQL tests require Postgres to be up and loaded; they are
skipped automatically if the database isn't reachable.

### 7. Optional integrations

- **Slack**: set `SLACK_WEBHOOK_URL` in `.env` to enable posting insights
  to a channel. Without it, `integrations/slack.py` logs what would have
  been sent.
- **Email**: set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`,
  and `REPORT_RECIPIENT` to send real HTML emails with an embedded chart.
  Without them, `integrations/email_report.py` writes a timestamped HTML
  report to `reports/`.
- **Power BI**: run `python integrations/powerbi_export.py` to write a
  star schema (`fact_sales`, `fact_attrition`, `dim_employee`,
  `dim_department`, `dim_region`, `dim_product`, `dim_date`) to
  `exports/powerbi/` for import into Power BI or any BI tool.

## Example questions

- "Show hiring trends"
- "Why did attrition increase?"
- "Show sales by region"
- "Show sales trend"
- "What is the average salary by department?"

## Project layout

```
data/generate_dataset.py    synthetic dataset generator
db/schema.sql               table definitions, indexes, FKs
db/roles.sql                read-only role grants
db/load.py                  loads CSVs into Postgres
core/sql_generator.py       NL -> SQL (LLM + fallback), safety guard
core/db.py                  connection helper, schema introspection
core/analysis.py            anomaly detection, trend forecasting
core/charts.py              matplotlib chart generation
core/insights.py            executive summary + suggested action
core/pipeline.py            wires the above together for the API
api/main.py                 FastAPI app (/ask, /health)
frontend/                   static chat UI (no build step)
integrations/slack.py       Slack webhook posting
integrations/email_report.py  SMTP email or local HTML report
integrations/powerbi_export.py  star-schema CSV export
tests/                      pytest suite
```

## License

MIT. See `LICENSE`.
