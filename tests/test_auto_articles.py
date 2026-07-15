"""Tests Auto Article store + scheduler helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import core.article_store as store
from core.article_job import (
    _fingerprint,
    build_sql_for_template,
    default_question,
    make_intraday_data_date,
)
from core.article_scheduler import (
    _in_time_window,
    _parse_hhmm,
    get_scheduler_status,
    start_scheduler,
    stop_scheduler,
)
from core.article_templates import get_template


def test_dedup_and_save(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "auto_articles.json"
    monkeypatch.setattr(store, "_STORE_PATH", path)

    assert store.has_article("market_01", "2026-07-14") is False
    a1 = store.save_article(
        template_id="market_01",
        template_name="Tổng kết thị trường",
        data_date="2026-07-14",
        article_markdown="# Test\n\nNội dung",
        domain_id="finance_vnfdata",
        question="Tổng kết",
        trigger="manual",
        word_count=10,
    )
    assert a1 is not None
    assert a1["id"]
    assert a1["generated_at"]
    assert store.has_article("market_01", "2026-07-14") is True

    a2 = store.save_article(
        template_id="market_01",
        template_name="Tổng kết thị trường",
        data_date="2026-07-14",
        article_markdown="# Dup",
        domain_id="finance_vnfdata",
        question="Tổng kết",
        trigger="manual",
        word_count=1,
    )
    assert a2 is None

    a3 = store.save_article(
        template_id="market_01",
        template_name="Tổng kết thị trường",
        data_date="2026-07-14",
        article_markdown="# Force",
        domain_id="finance_vnfdata",
        question="Tổng kết",
        trigger="manual",
        word_count=2,
        force=True,
    )
    assert a3 is not None
    assert a3["article_markdown"].startswith("# Force")
    listed = store.list_articles(domain_id="finance_vnfdata")
    assert len(listed) == 1


def test_last_seen(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "auto_articles.json"
    monkeypatch.setattr(store, "_STORE_PATH", path)
    store.update_last_seen(max_trade_date="2026-07-10")
    seen = store.get_last_seen()
    assert seen["max_trade_date"] == "2026-07-10"
    store.update_last_seen(
        max_fiscal_key="2025-Q2",
        market_fingerprint="abc123",
        fiscal_fingerprint="def456",
    )
    seen2 = store.get_last_seen()
    assert seen2["max_fiscal_key"] == "2025-Q2"
    assert seen2["max_trade_date"] == "2026-07-10"
    assert seen2["market_fingerprint"] == "abc123"
    assert seen2["fiscal_fingerprint"] == "def456"


def test_intraday_data_date_and_fingerprint() -> None:
    when = datetime(2026, 7, 14, 15, 42, 0)
    assert make_intraday_data_date("2026-07-14", when) == "2026-07-14T15"
    fp1 = _fingerprint("2026-07-14", 100, 1.0, 2.0, 9)
    fp2 = _fingerprint("2026-07-14", 101, 1.0, 2.0, 9)
    assert fp1 != fp2
    assert len(fp1) == 16


def test_build_sql_known_templates() -> None:
    sql = build_sql_for_template("market_01")
    assert "index_snapshots" in sql or "stock_prices" in sql
    assert "SELECT" in sql.upper()
    sql2 = build_sql_for_template("company_01")
    assert "financial_statements" in sql2


def test_sql_catalog_covers_all_templates() -> None:
    from core.article_sql import sql_catalog_ids
    from core.article_templates import list_templates

    tpl_ids = {t["id"] for t in list_templates()}
    sql_ids = set(sql_catalog_ids())
    assert len(sql_ids) == 35
    assert tpl_ids == sql_ids
    # vài template đặc thù phải trỏ đúng bảng
    assert "proprietary_trades" in build_sql_for_template("market_10")
    assert "sector_performance" in build_sql_for_template("market_13")
    assert "cash_and_cash_equivalents" in build_sql_for_template("company_14")
    assert "inventory" in build_sql_for_template("company_15")


def test_default_question() -> None:
    tpl = get_template("market_01")
    assert tpl is not None
    q = default_question(tpl, "2026-07-14")
    assert "Tổng kết" in q
    assert "2026-07-14" in q


def test_parse_hhmm_and_window() -> None:
    assert _parse_hhmm("15:20", "15:20") == (15, 20)
    assert _parse_hhmm("bad", "08:30") == (8, 30)
    now = datetime(2026, 7, 14, 15, 25, 0)
    assert _in_time_window(now, 15, 20, 20) is True
    assert _in_time_window(now, 15, 20, 5) is False
    assert _in_time_window(now, 16, 0, 20) is False


def test_article_scheduler_disabled_by_default(monkeypatch) -> None:
    stop_scheduler()
    monkeypatch.delenv("ARTICLE_SCHEDULE_ENABLED", raising=False)
    monkeypatch.setenv("ARTICLE_POLL_MINUTES", "10")
    status = start_scheduler()
    assert status["enabled"] is False
    assert get_scheduler_status()["enabled"] is False
    stop_scheduler()


def test_notify_disabled_skips(monkeypatch) -> None:
    from core.article_notify import notify_article

    monkeypatch.delenv("ARTICLE_NOTIFY_ENABLED", raising=False)
    out = notify_article(
        {
            "id": "x",
            "template_name": "Test",
            "data_date": "2026-07-14",
            "trigger": "manual",
            "article_markdown": "# Hi",
            "word_count": 1,
            "generated_at": "2026-07-14 15:00",
        },
        trigger="manual",
    )
    assert out["skipped"] is True


def test_notify_slack_when_enabled(monkeypatch) -> None:
    from core import article_notify as notify

    monkeypatch.setenv("ARTICLE_NOTIFY_ENABLED", "true")
    monkeypatch.setenv(
        "ARTICLE_NOTIFY_SLACK_WEBHOOK", "https://hooks.slack.test/abc"
    )
    monkeypatch.delenv("ARTICLE_NOTIFY_SMTP_HOST", raising=False)
    monkeypatch.delenv("ARTICLE_NOTIFY_TELEGRAM_BOT_TOKEN", raising=False)

    class _Resp:
        status_code = 200
        text = "ok"

    calls: list[dict] = []

    def fake_post(url, json=None, timeout=20):  # noqa: A002
        calls.append({"url": url, "json": json})
        return _Resp()

    monkeypatch.setattr(notify.requests, "post", fake_post)
    out = notify.notify_article(
        {
            "id": "a1",
            "template_name": "Tổng kết thị trường",
            "data_date": "2026-07-14",
            "trigger": "schedule_daily",
            "article_markdown": "## Báo cáo\n\nVN-Index tăng.",
            "word_count": 12,
            "generated_at": "14/07/2026 15:20",
        },
        trigger="schedule_daily",
    )
    assert out["skipped"] is False
    assert out["ok_count"] == 1
    assert calls and "hooks.slack.test" in calls[0]["url"]


def test_notify_trigger_filter(monkeypatch) -> None:
    from core.article_notify import notify_article

    monkeypatch.setenv("ARTICLE_NOTIFY_ENABLED", "true")
    monkeypatch.setenv("ARTICLE_NOTIFY_TRIGGERS", "schedule_daily,schedule_weekly")
    monkeypatch.setenv(
        "ARTICLE_NOTIFY_SLACK_WEBHOOK", "https://hooks.slack.test/abc"
    )
    out = notify_article(
        {
            "id": "a1",
            "template_name": "Test",
            "data_date": "2026-07-14",
            "trigger": "manual",
            "article_markdown": "x",
            "word_count": 1,
            "generated_at": "t",
        },
        trigger="manual",
    )
    assert out["skipped"] is True
    assert out["reason"] == "disabled_or_trigger_filtered"
