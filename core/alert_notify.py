"""Gửi thông báo khi alert kích hoạt — Email / Slack / Telegram.

Tái sử dụng credential ARTICLE_NOTIFY_* (cùng kênh vận hành).
Bật riêng bằng ALERT_NOTIFY_ENABLED (mặc định = ARTICLE_NOTIFY_ENABLED).
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import requests

from core.article_notify import configured_channels

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def alert_notify_enabled() -> bool:
    if os.getenv("ALERT_NOTIFY_ENABLED") is not None:
        return _env_bool("ALERT_NOTIFY_ENABLED", default=False)
    return _env_bool("ARTICLE_NOTIFY_ENABLED", default=False)


def _format_alert_text(result: dict[str, Any]) -> str:
    name = str(result.get("rule_name") or result.get("rule_id") or "Alert")
    msg = str(result.get("message") or "")
    domain = str(result.get("domain_id") or "")
    target = result.get("target") or ""
    value = result.get("value")
    lines = [
        f"[AI BI Alert] {name}",
        f"Domain: {domain}",
        f"Message: {msg}",
    ]
    if target:
        lines.append(f"Target: {target}")
    if value is not None:
        lines.append(f"Value: {value}")
    lines.append("→ Mở app và bấm «Hỏi lại trong chat» trên event để phân tích tiếp.")
    return "\n".join(lines)


def notify_alert(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Gửi alert ra các kênh đã cấu hình. Trả list kết quả từng kênh."""
    if not alert_notify_enabled():
        return [{"status": "skipped", "message": "ALERT_NOTIFY disabled"}]
    if not result.get("new_event"):
        return [{"status": "skipped", "message": "not a new event"}]

    text = _format_alert_text(result)
    out: list[dict[str, Any]] = []
    channels = configured_channels()
    if not channels:
        return [{"status": "skipped", "message": "Chưa cấu hình kênh notify"}]

    if "email" in channels:
        out.append(_send_email(text, result))
    if "slack" in channels:
        out.append(_send_slack(text))
    if "telegram" in channels:
        out.append(_send_telegram(text))
    return out


def _send_email(text: str, result: dict[str, Any]) -> dict[str, Any]:
    host = _env("ARTICLE_NOTIFY_SMTP_HOST")
    to_raw = _env("ARTICLE_NOTIFY_EMAIL_TO")
    if not host or not to_raw:
        return {"channel": "email", "status": "skipped"}
    port = int(_env("ARTICLE_NOTIFY_SMTP_PORT", "587") or "587")
    user = _env("ARTICLE_NOTIFY_SMTP_USER")
    password = _env("ARTICLE_NOTIFY_SMTP_PASSWORD")
    use_tls = _env_bool("ARTICLE_NOTIFY_SMTP_TLS", default=True)
    from_addr = _env("ARTICLE_NOTIFY_EMAIL_FROM") or user or "noreply@localhost"
    recipients = [x.strip() for x in to_raw.split(",") if x.strip()]
    subject = f"[Alert] {result.get('rule_name') or 'BI'}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls(context=context)
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        return {"channel": "email", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("alert email failed: %s", exc)
        return {"channel": "email", "status": "error", "message": str(exc)[:200]}


def _send_slack(text: str) -> dict[str, Any]:
    webhook = _env("ARTICLE_NOTIFY_SLACK_WEBHOOK")
    if not webhook:
        return {"channel": "slack", "status": "skipped"}
    try:
        r = requests.post(webhook, json={"text": text}, timeout=15)
        r.raise_for_status()
        return {"channel": "slack", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("alert slack failed: %s", exc)
        return {"channel": "slack", "status": "error", "message": str(exc)[:200]}


def _send_telegram(text: str) -> dict[str, Any]:
    token = _env("ARTICLE_NOTIFY_TELEGRAM_BOT_TOKEN")
    chat_id = _env("ARTICLE_NOTIFY_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"channel": "telegram", "status": "skipped"}
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:3900]},
            timeout=15,
        )
        r.raise_for_status()
        return {"channel": "telegram", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("alert telegram failed: %s", exc)
        return {"channel": "telegram", "status": "error", "message": str(exc)[:200]}
