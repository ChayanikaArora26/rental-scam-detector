"""
email_service/service.py — Async SMTP sender via aiosmtplib.

Never crashes the caller — all errors are logged and swallowed.
Configure via SMTP_* env vars.
"""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from config import get_settings
from email_service.templates import (
    login_alert_email,
    password_reset_email,
    verification_email,
)

log = logging.getLogger(__name__)
settings = get_settings()


async def _send(to: str, subject: str, html: str) -> None:
    """Low-level sender. Logs and swallows errors — never raises."""
    if not settings.SMTP_USER or not settings.SMTP_PASS:
        log.warning("SMTP not configured — email to %s skipped: %s", to, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASS,
            start_tls=True,
        )
        log.info("Email sent to %s: %s", to, subject)
    except Exception as exc:
        log.error("Failed to send email to %s: %s", to, exc)


async def send_verification_email(to: str, token: str) -> None:
    subject, html = verification_email(token)
    await _send(to, subject, html)


async def send_password_reset_email(to: str, token: str) -> None:
    subject, html = password_reset_email(token)
    await _send(to, subject, html)


async def send_login_alert(to: str, ip: str) -> None:
    subject, html = login_alert_email(ip)
    await _send(to, subject, html)
