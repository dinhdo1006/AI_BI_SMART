"""Tests Auto Article store + scheduler helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import core.article_store as store
from core.article_job import build_sql_for_template, default_question
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
    store.update_last_seen(max_fiscal_key="2025-Q2")
    seen2 = store.get_last_seen()
    assert seen2["max_fiscal_key"] == "2025-Q2"
    assert seen2["max_trade_date"] == "2026-07-10"


def test_build_sql_known_templates() -> None:
    sql = build_sql_for_template("market_01")
    assert "stock_prices" in sql
    assert "SELECT" in sql.upper()
    sql2 = build_sql_for_template("company_01")
    assert "financial_statements" in sql2


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
