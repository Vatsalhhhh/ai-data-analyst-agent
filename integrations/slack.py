"""
Pushes an insight (plus chart reference and suggested action) to Slack via
an incoming webhook. If SLACK_WEBHOOK_URL isn't set, logs clearly what
would have been sent instead of silently doing nothing -- useful for local
development and for the test suite.
"""

import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("integrations.slack")


def post_to_slack(insight: str, chart_path: str = None, suggested_action: str = None) -> bool:
    """
    Posts a formatted message to the configured Slack webhook.

    Returns True if a real webhook post was attempted and succeeded, False
    if it ran in log-only mode (no webhook configured) or the request
    failed. Never raises for a missing webhook -- that's an expected,
    documented no-op path.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    text_lines = [f"*Data Analyst Insight*", insight]
    if suggested_action:
        text_lines.append(f"*Suggested action:* {suggested_action}")
    if chart_path:
        text_lines.append(f"Chart saved at: {chart_path}")
    message_text = "\n".join(text_lines)

    if not webhook_url:
        logger.info(
            "SLACK_WEBHOOK_URL not configured; would have posted the following "
            "message to Slack:\n%s",
            message_text,
        )
        return False

    try:
        response = requests.post(webhook_url, json={"text": message_text}, timeout=5)
        response.raise_for_status()
        logger.info("Posted insight to Slack successfully.")
        return True
    except requests.RequestException as e:
        logger.error("Failed to post to Slack: %s", e)
        return False
