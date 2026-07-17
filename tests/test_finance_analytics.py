"""Tests peer-group + technical analysis analytics SQL."""

from __future__ import annotations

from core.finance_analytics import (
    build_peer_group_sql,
    build_technical_analysis_sql,
    is_peer_group_query,
    is_technical_analysis_query,
    try_finance_analytics_sql,
)


def test_detect_peer_group_query() -> None:
    assert is_peer_group_query("VNM so sánh cùng ngành về P/E")
    assert is_peer_group_query("Peer group của FPT")
    assert not is_peer_group_query("Giá FPT 10 phiên gần nhất")


def test_detect_ta_query() -> None:
    assert is_technical_analysis_query("RSI và MACD của HPG")
    assert is_technical_analysis_query("Chỉ báo kỹ thuật FPT 60 phiên")
    assert not is_technical_analysis_query("P/E FPT hiện tại")


def test_build_peer_sql_contains_sector_join() -> None:
    sql = build_peer_group_sql("VNM")
    assert "sector_id" in sql
    assert "financial_indicators" in sql
    assert "'VNM'" in sql
    assert "is_anchor" in sql


def test_build_ta_sql_contains_indicators() -> None:
    sql = build_technical_analysis_sql("FPT", days=40)
    assert "technical_indicators" in sql
    assert "rsi" in sql.lower()
    assert "macd" in sql.lower()
    assert "'FPT'" in sql


def test_try_analytics_needs_ticker(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.finance_analytics.resolve_tickers",
        lambda *_a, **_k: [],
    )
    assert try_finance_analytics_sql("RSI hôm nay") is None


def test_try_analytics_peer_with_ticker(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.finance_analytics.resolve_tickers",
        lambda *_a, **_k: ["VNM"],
    )
    hit = try_finance_analytics_sql("So sánh VNM cùng ngành")
    assert hit is not None
    assert hit["kind"] == "peer_group"
    assert hit["ticker"] == "VNM"
    assert "companies" in hit["sql"]


def test_try_analytics_ta_with_ticker(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.finance_analytics.resolve_tickers",
        lambda *_a, **_k: ["HPG"],
    )
    hit = try_finance_analytics_sql("MACD HPG 30 phiên")
    assert hit is not None
    assert hit["kind"] == "technical_analysis"
    assert "LIMIT 30" in hit["sql"] or "LIMIT 30" in hit["sql"].upper()
