"""
Generates a natural-language executive summary and a one-line suggested
action from a query result DataFrame plus its anomaly/trend analysis.

If OPENAI_API_KEY is set, ask an LLM to polish the summary. Otherwise use
a deterministic template that pulls real computed numbers (min/max/mean/
trend direction/anomaly count) out of the DataFrame -- not placeholder text.
"""

import os

from core.analysis import trend_direction


def _basic_stats(df, value_col):
    values = df[value_col].astype(float)
    return {
        "min": values.min(),
        "max": values.max(),
        "mean": values.mean(),
        "total": values.sum(),
        "count": len(values),
    }


def generate_insight_fallback(question: str, df, value_col: str, date_col: str = None, anomaly_df=None) -> tuple:
    """
    Returns (insight_text, suggested_action) built from real computed
    numbers in df. No LLM required.
    """
    stats = _basic_stats(df, value_col)
    anomaly_count = 0
    if anomaly_df is not None and "is_anomaly" in anomaly_df.columns:
        anomaly_count = int(anomaly_df["is_anomaly"].sum())

    direction = trend_direction(df, value_col) if len(df) >= 2 else "flat"

    value_label = value_col.replace("_", " ")

    summary_parts = [
        f"Across {stats['count']} data points, {value_label} ranged from "
        f"{stats['min']:,.2f} to {stats['max']:,.2f}, averaging {stats['mean']:,.2f} "
        f"(total: {stats['total']:,.2f})."
    ]

    if direction == "increasing":
        summary_parts.append(f"The overall trend is upward over the period analyzed.")
    elif direction == "decreasing":
        summary_parts.append(f"The overall trend is downward over the period analyzed.")
    else:
        summary_parts.append("The metric has stayed roughly flat over the period analyzed.")

    if anomaly_count > 0:
        summary_parts.append(
            f"{anomaly_count} data point(s) were flagged as statistical outliers "
            f"relative to the rest of the series, indicating a period that deviated "
            f"materially from the norm."
        )
    else:
        summary_parts.append("No statistically significant outliers were detected in this series.")

    insight_text = " ".join(summary_parts)

    if anomaly_count > 0 and direction == "decreasing":
        suggested_action = (
            f"Investigate the flagged outlier period(s) for {value_label} -- the "
            f"combination of a downward trend and detected anomalies suggests a "
            f"specific, addressable cause rather than normal variation."
        )
    elif anomaly_count > 0:
        suggested_action = (
            f"Review the flagged outlier period(s) for {value_label} to confirm "
            f"whether they reflect a one-off event or the start of a new pattern."
        )
    elif direction == "decreasing":
        suggested_action = f"Monitor {value_label} closely; the downward trend warrants a closer look next period."
    elif direction == "increasing":
        suggested_action = f"Continue current initiatives; {value_label} is trending favorably."
    else:
        suggested_action = f"No immediate action needed; {value_label} is stable."

    return insight_text, suggested_action


def generate_insight_llm(question: str, df, value_col: str, date_col: str = None, anomaly_df=None) -> tuple:
    """
    Uses langchain + openai to produce a polished executive summary and
    suggested action, grounded in the same computed stats as the fallback
    (so the model isn't just inventing numbers).
    """
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate

    stats = _basic_stats(df, value_col)
    direction = trend_direction(df, value_col) if len(df) >= 2 else "flat"
    anomaly_count = 0
    if anomaly_df is not None and "is_anomaly" in anomaly_df.columns:
        anomaly_count = int(anomaly_df["is_anomaly"].sum())

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a data analyst writing a short executive summary for "
                "a business stakeholder. Be concise, concrete, and reference the "
                "actual numbers given. Then give one specific, actionable "
                "recommendation as a single sentence. Respond with exactly two "
                "lines: the first line is the summary paragraph, the second "
                "line starts with 'ACTION:' followed by the recommendation.",
            ),
            (
                "human",
                "Question: {question}\n"
                "Metric: {value_col}\n"
                "Data points: {count}\n"
                "Min: {min:.2f}, Max: {max:.2f}, Mean: {mean:.2f}, Total: {total:.2f}\n"
                "Trend direction: {direction}\n"
                "Anomalies detected: {anomaly_count}",
            ),
        ]
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))
    chain = prompt | llm

    response = chain.invoke(
        {
            "question": question,
            "value_col": value_col,
            "count": stats["count"],
            "min": stats["min"],
            "max": stats["max"],
            "mean": stats["mean"],
            "total": stats["total"],
            "direction": direction,
            "anomaly_count": anomaly_count,
        }
    )

    text = response.content.strip()
    lines = text.split("\n")
    action_line = next((l for l in lines if l.strip().upper().startswith("ACTION:")), None)

    if action_line:
        suggested_action = action_line.split(":", 1)[1].strip()
        insight_text = "\n".join(l for l in lines if l is not action_line).strip()
    else:
        insight_text = text
        suggested_action = "Review the results above for next steps."

    return insight_text, suggested_action


def generate_insight(question: str, df, value_col: str, date_col: str = None, anomaly_df=None) -> tuple:
    """Main entry point. Uses the LLM path if OPENAI_API_KEY is set, else
    the deterministic fallback. Returns (insight_text, suggested_action)."""
    if df.empty:
        return "No data was returned for this question.", "Try rephrasing the question or check the date range."

    if os.getenv("OPENAI_API_KEY"):
        try:
            return generate_insight_llm(question, df, value_col, date_col, anomaly_df)
        except Exception:
            # Never let an LLM/network hiccup break the pipeline -- fall
            # back to the deterministic template if the API call fails.
            return generate_insight_fallback(question, df, value_col, date_col, anomaly_df)

    return generate_insight_fallback(question, df, value_col, date_col, anomaly_df)
