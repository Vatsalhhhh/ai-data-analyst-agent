import glob
import os

from integrations.email_report import send_email_report
from integrations.slack import post_to_slack

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


def test_slack_noop_does_not_raise(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    result = post_to_slack("Test insight", chart_path=None, suggested_action="Do nothing.")
    assert result is False


def test_email_noop_writes_report_file(monkeypatch):
    for var in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "REPORT_RECIPIENT"]:
        monkeypatch.delenv(var, raising=False)

    before = set(glob.glob(os.path.join(REPORTS_DIR, "*.html")))

    result_path = send_email_report(
        question="Test question",
        insight="Test insight text.",
        suggested_action="Test action.",
        chart_path=None,
    )

    assert os.path.exists(result_path)
    assert result_path.endswith(".html")

    after = set(glob.glob(os.path.join(REPORTS_DIR, "*.html")))
    assert after - before  # a new report file was written

    # Clean up the file we just created.
    os.remove(result_path)
