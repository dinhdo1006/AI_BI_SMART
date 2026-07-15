"""Gửi bài auto ra ngoài — Email (SMTP) / Slack webhook / Telegram bot."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_MAX = 3900  # dưới giới hạn 4096 của Telegram


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def notify_enabled() -> bool:
    return _env_bool("ARTICLE_NOTIFY_ENABLED", default=False)


def configured_channels() -> list[str]:
    """Các kênh đã cấu hình đủ credential (không phụ thuộc enabled)."""
    channels: list[str] = []
    if _env("ARTICLE_NOTIFY_SMTP_HOST") and _env("ARTICLE_NOTIFY_EMAIL_TO"):
        channels.append("email")
    if _env("ARTICLE_NOTIFY_SLACK_WEBHOOK"):
        channels.append("slack")
    if _env("ARTICLE_NOTIFY_TELEGRAM_BOT_TOKEN") and _env(
        "ARTICLE_NOTIFY_TELEGRAM_CHAT_ID"
    ):
        channels.append("telegram")
    return channels


def get_notify_status() -> dict[str, Any]:
    return {
        "enabled": notify_enabled(),
        "channels": configured_channels(),
        "triggers": _notify_triggers(),
    }


def _notify_triggers() -> list[str] | None:
    """None = mọi trigger; list = chỉ các trigger trong list."""
    raw = _env("ARTICLE_NOTIFY_TRIGGERS")
    if not raw:
        return None
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items or None


def _should_notify(trigger: str) -> bool:
    if not notify_enabled():
        return False
    allowed = _notify_triggers()
    if allowed is None:
        return True
    return (trigger or "").strip() in allowed


def _article_title(article: dict[str, Any]) -> str:
    name = str(article.get("template_name") or article.get("template_id") or "Bài")
    dd = str(article.get("data_date") or "")
    return f"{name} — {dd}".strip(" —")


def _preview_markdown(md: str, max_chars: int = 1200) -> str:
    text = (md or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _format_message(article: dict[str, Any], *, telegram: bool = False) -> str:
    title = _article_title(article)
    trigger = str(article.get("trigger") or "")
    generated = str(article.get("generated_at") or "")
    words = article.get("word_count") or 0
    body = _preview_markdown(
        str(article.get("article_markdown") or ""),
        max_chars=_TELEGRAM_MAX - 200 if telegram else 4000,
    )
    header = (
        f"*{title}*\n"
        if telegram
        else f"{title}\n"
    )
    meta = f"Trigger: {trigger}\nThời gian: {generated}\nSố từ: {words}\n\n"
    return f"{header}{meta}{body}"


def send_email(article: dict[str, Any]) -> dict[str, Any]:
    host = _env("ARTICLE_NOTIFY_SMTP_HOST")
    to_raw = _env("ARTICLE_NOTIFY_EMAIL_TO")
    if not host or not to_raw:
        return {"channel": "email", "status": "skipped", "message": "Chưa cấu hình SMTP"}

    port = int(_env("ARTICLE_NOTIFY_SMTP_PORT", "587") or "587")
    user = _env("ARTICLE_NOTIFY_SMTP_USER")
    password = _env("ARTICLE_NOTIFY_SMTP_PASSWORD")
    use_tls = _env_bool("ARTICLE_NOTIFY_SMTP_TLS", default=True)
    from_addr = _env("ARTICLE_NOTIFY_EMAIL_FROM") or user or "noreply@localhost"
    recipients = [x.strip() for x in to_raw.split(",") if x.strip()]

    msg = EmailMessage()
    msg["Subject"] = f"[VNFDATA] {_article_title(article)}"
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.set_content(_format_message(article))

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
        return {"channel": "email", "status": "ok", "to": recipients}
    except Exception as exc:  # noqa: BLE001
        logger.warning("article notify email failed: %s", exc)
        return {"channel": "email", "status": "error", "message": str(exc)[:200]}


def send_slack(article: dict[str, Any]) -> dict[str, Any]:
    webhook = _env("ARTICLE_NOTIFY_SLACK_WEBHOOK")
    if not webhook:
        return {
            "channel": "slack",
            "status": "skipped",
            "message": "Chưa cấu hình webhook",
        }

    text = _format_message(article)
    # Slack text cứng ~40k; giữ vừa đủ
    if len(text) > 3500:
        text = text[:3499] + "…"
    payload = {
        "text": f"[VNFDATA] {_article_title(article)}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": _article_title(article)[:150],
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text[:2900]},
            },
        ],
    }
    try:
        resp = requests.post(webhook, json=payload, timeout=20)
        if resp.status_code >= 400:
            return {
                "channel": "slack",
                "status": "error",
                "message": f"HTTP {resp.status_code}: {resp.text[:160]}",
            }
        return {"channel": "slack", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("article notify slack failed: %s", exc)
        return {"channel": "slack", "status": "error", "message": str(exc)[:200]}


def send_telegram(article: dict[str, Any]) -> dict[str, Any]:
    token = _env("ARTICLE_NOTIFY_TELEGRAM_BOT_TOKEN")
    chat_id = _env("ARTICLE_NOTIFY_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {
            "channel": "telegram",
            "status": "skipped",
            "message": "Chưa cấu hình bot/chat",
        }

    text = _format_message(article, telegram=True)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400 or not data.get("ok"):
            desc = data.get("description") or resp.text[:160]
            return {
                "channel": "telegram",
                "status": "error",
                "message": str(desc)[:200],
            }
        return {"channel": "telegram", "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("article notify telegram failed: %s", exc)
        return {"channel": "telegram", "status": "error", "message": str(exc)[:200]}


_SENDERS = {
    "email": send_email,
    "slack": send_slack,
    "telegram": send_telegram,
}


def notify_article(article: dict[str, Any], *, trigger: str = "") -> dict[str, Any]:
    """
    Gửi bài tới các kênh đã cấu hình.
    Không raise — luôn trả summary để gắn vào kết quả job.
    """
    trig = (trigger or str(article.get("trigger") or "")).strip()
    if not _should_notify(trig):
        return {
            "enabled": notify_enabled(),
            "skipped": True,
            "reason": "disabled_or_trigger_filtered",
            "results": [],
        }

    channels = configured_channels()
    if not channels:
        return {
            "enabled": True,
            "skipped": True,
            "reason": "no_channels_configured",
            "results": [],
        }

    results = [_SENDERS[ch](article) for ch in channels]
    ok = sum(1 for r in results if r.get("status") == "ok")
    err = sum(1 for r in results if r.get("status") == "error")
    logger.info(
        "Article notify %s: channels=%s ok=%s err=%s",
        article.get("id"),
        channels,
        ok,
        err,
    )
    return {
        "enabled": True,
        "skipped": False,
        "ok_count": ok,
        "error_count": err,
        "results": results,
    }
