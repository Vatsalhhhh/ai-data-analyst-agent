"""
Sends (or drafts) an HTML email report containing an insight, suggested
action, and an embedded chart image.

If SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/REPORT_RECIPIENT are all
set, sends a real email via smtplib. Otherwise, writes a timestamped HTML
file to reports/ and logs its location -- so the feature is still
demonstrable without real mail credentials.
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("integrations.email_report")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


def _smtp_settings():
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": os.getenv("SMTP_PORT"),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "recipient": os.getenv("REPORT_RECIPIENT"),
    }


def _build_html_body(question: str, insight: str, suggested_action: str, chart_cid: str = None) -> str:
    chart_tag = f'<img src="cid:{chart_cid}" style="max-width:600px;" />' if chart_cid else ""
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1a202c;">
        <h2>Data Analyst Report</h2>
        <p><strong>Question:</strong> {question}</p>
        <p>{insight}</p>
        <p style="background:#ebf8ff; padding:10px; border-left:3px solid #2b6cb0;">
          <strong>Suggested action:</strong> {suggested_action}
        </p>
        {chart_tag}
        <p style="color:#718096; font-size:0.85em;">Generated {datetime.now().isoformat(timespec='seconds')}</p>
      </body>
    </html>
    """


def send_email_report(question: str, insight: str, suggested_action: str, chart_path: str = None) -> str:
    """
    Sends the report via SMTP if credentials are configured, otherwise
    writes it to reports/<timestamp>.html.

    Returns the destination: either "smtp:<recipient>" on a real send, or
    the filesystem path to the written HTML report.
    """
    settings = _smtp_settings()
    all_smtp_configured = all(
        [settings["host"], settings["port"], settings["user"], settings["password"], settings["recipient"]]
    )

    if all_smtp_configured:
        chart_cid = "report_chart" if chart_path else None
        html_body = _build_html_body(question, insight, suggested_action, chart_cid)

        msg = MIMEMultipart("related")
        msg["Subject"] = f"Data Analyst Report: {question}"
        msg["From"] = settings["user"]
        msg["To"] = settings["recipient"]
        msg.attach(MIMEText(html_body, "html"))

        if chart_path and os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                img = MIMEImage(f.read())
                img.add_header("Content-ID", f"<{chart_cid}>")
                msg.attach(img)

        try:
            with smtplib.SMTP(settings["host"], int(settings["port"])) as server:
                server.starttls()
                server.login(settings["user"], settings["password"])
                server.sendmail(settings["user"], settings["recipient"], msg.as_string())
            logger.info("Emailed report to %s", settings["recipient"])
            return f"smtp:{settings['recipient']}"
        except Exception as e:
            logger.error("Failed to send email via SMTP, falling back to file report: %s", e)
            # Fall through to file-based report below.

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{timestamp}.html"
    filepath = os.path.join(REPORTS_DIR, filename)

    chart_cid = None
    html_body = _build_html_body(question, insight, suggested_action, chart_cid)
    if chart_path and os.path.exists(chart_path):
        html_body = html_body.replace(
            "</body>", f'<img src="{os.path.abspath(chart_path)}" style="max-width:600px;" /></body>'
        )

    with open(filepath, "w") as f:
        f.write(html_body)

    logger.info(
        "SMTP not fully configured; wrote report to %s instead of sending email.", filepath
    )
    return filepath
