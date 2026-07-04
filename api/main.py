"""
FastAPI application exposing the data analyst pipeline.

Endpoints:
  POST /ask     - runs the full pipeline for a natural-language question
  GET  /health  - reports service status, whether an OpenAI key is
                  configured, and whether the DB is reachable

Chart PNGs are served statically under /charts.
"""

import os
import sys

# Allow running with `uvicorn api.main:app` from the repo root without
# needing the package installed.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.db import check_db_connectivity
from core.pipeline import run_pipeline
from core.sql_generator import SQLSafetyViolation

CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

app = FastAPI(title="AI Data Analyst Agent", version="1.0.0")

# CORS is wide open here since this is a local demo project served next to
# a static frontend with no auth. Tighten this before deploying anywhere
# that isn't localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    sql: str
    results: list
    chart_url: str | None
    forecast: list | None
    insight: str
    suggested_action: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "db_connected": check_db_connectivity(),
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    try:
        result = run_pipeline(question)
    except SQLSafetyViolation as e:
        raise HTTPException(status_code=400, detail=f"Unsafe query rejected: {e}")
    except Exception as e:
        # Don't leak internals/stack traces to the client.
        raise HTTPException(status_code=500, detail="Something went wrong processing that question.") from e

    chart_url = None
    if result["chart_path"]:
        chart_filename = os.path.basename(result["chart_path"])
        chart_url = f"/charts/{chart_filename}"

    return AskResponse(
        sql=result["sql"],
        results=result["results"],
        chart_url=chart_url,
        forecast=result["forecast"],
        insight=result["insight"],
        suggested_action=result["suggested_action"],
    )
