from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from flask import current_app


def send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """Send an email using SMTP settings from Flask config.

    Returns True if the message was handed off to SMTP, False if skipped.

    Safe-by-default: if SMTP is not configured, it will log and return False.
    """

    cfg = current_app.config
    if not cfg.get("REMINDERS_ENABLED", True):
        current_app.logger.info("Email skipped (REMINDERS_ENABLED=false)")
        return False

    smtp_host = cfg.get("SMTP_HOST")
    if not smtp_host:
        current_app.logger.warning("Email skipped (SMTP_HOST not configured)")
        return False

    smtp_port = int(cfg.get("SMTP_PORT") or 587)
    smtp_user = cfg.get("SMTP_USERNAME")
    smtp_pass = cfg.get("SMTP_PASSWORD")
    smtp_use_tls = bool(cfg.get("SMTP_USE_TLS", True))
    from_email = cfg.get("SMTP_FROM")

    if not from_email:
        current_app.logger.warning("Email skipped (SMTP_FROM not configured)")
        return False

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text or "")

    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            if smtp_use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception:
        current_app.logger.exception("Email send failed")
        return False
