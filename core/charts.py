"""
Chart generation. Uses matplotlib's non-interactive Agg backend so this
works headless (no display needed), which matters since this runs inside
a FastAPI server process.
"""

import os
import re
import uuid

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

CHARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "charts")


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len] or "chart"


def generate_chart(df: pd.DataFrame, question: str, value_col: str, label_col: str, chart_type: str = "auto") -> str:
    """
    Builds a matplotlib chart from df and saves it as a PNG under charts/.

    - chart_type "line": time-series line chart (for trends).
    - chart_type "bar": categorical bar chart (for comparisons, e.g. by region).
    - chart_type "auto": picks "line" if label_col looks like a date/time
      column, otherwise "bar".

    Returns the path to the saved PNG file.
    """
    os.makedirs(CHARTS_DIR, exist_ok=True)

    plot_df = df.copy()

    if chart_type == "auto":
        is_datetime_like = pd.api.types.is_datetime64_any_dtype(plot_df[label_col])
        if not is_datetime_like:
            try:
                pd.to_datetime(plot_df[label_col])
                is_datetime_like = True
            except (ValueError, TypeError):
                is_datetime_like = False
        chart_type = "line" if is_datetime_like else "bar"

    fig, ax = plt.subplots(figsize=(9, 5))

    if chart_type == "line":
        plot_df[label_col] = pd.to_datetime(plot_df[label_col])
        plot_df = plot_df.sort_values(label_col)
        ax.plot(plot_df[label_col], plot_df[value_col], marker="o", linewidth=2, color="#2b6cb0")
        ax.set_xlabel(label_col.replace("_", " ").title())
        fig.autofmt_xdate()
    else:
        ax.bar(plot_df[label_col].astype(str), plot_df[value_col], color="#2b6cb0")
        ax.set_xlabel(label_col.replace("_", " ").title())
        plt.xticks(rotation=30, ha="right")

    ax.set_ylabel(value_col.replace("_", " ").title())
    ax.set_title(question[:80])
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    filename = f"{_slugify(question)}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(CHARTS_DIR, filename)
    fig.savefig(filepath, dpi=110)
    plt.close(fig)

    return filepath
