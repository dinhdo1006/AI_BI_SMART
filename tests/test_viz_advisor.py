"""Test gợi ý chart theo shape dữ liệu."""

from __future__ import annotations

from core.viz_advisor import compatible_charts, suggest_chart_from_data


def test_suggest_ohlc_to_candlestick():
    data = [
        {
            "trade_date": f"2026-01-{i:02d}",
            "open_price": 10 + i,
            "high_price": 12 + i,
            "low_price": 9 + i,
            "close_price": 11 + i,
            "volume": 1000 * i,
        }
        for i in range(1, 8)
    ]
    assert suggest_chart_from_data(data) == "candlestick"
    assert "candlestick" in compatible_charts(data)
    assert "combo" in compatible_charts(data)


def test_suggest_timeseries_line():
    data = [
        {"trade_date": f"2026-01-{i:02d}", "close_price": 100 + i}
        for i in range(1, 10)
    ]
    assert suggest_chart_from_data(data) == "line"


def test_suggest_many_metrics_radar_or_heatmap():
    data = [
        {
            "ticker": t,
            "pe_ratio": 10 + i,
            "pb_ratio": 1 + i * 0.1,
            "roe": 0.1 + i * 0.01,
            "roa": 0.05 + i * 0.005,
        }
        for i, t in enumerate(["FPT", "VCB", "HPG", "ACB"])
    ]
    chart = suggest_chart_from_data(data)
    assert chart == "radar"
    assert "radar" in compatible_charts(data)


def test_suggest_scatter_two_metrics():
    data = [
        {"ticker": f"T{i}", "pe_ratio": 5 + i, "pb_ratio": 1 + i * 0.2}
        for i in range(8)
    ]
    assert suggest_chart_from_data(data) == "scatter"


def test_suggest_many_categories_treemap():
    data = [{"ticker": f"T{i:02d}", "market_cap": 1000 - i * 10} for i in range(15)]
    assert suggest_chart_from_data(data) == "treemap"


def test_suggest_list_only_table():
    data = [{"ticker": "FPT", "company_name": "FPT Corp"}]
    assert suggest_chart_from_data(data, "Danh sách công ty") == "table"


def test_compatible_disables_candlestick_without_ohlc():
    data = [{"ticker": "FPT", "market_cap": 100}]
    assert "candlestick" not in compatible_charts(data)
    assert "bar" in compatible_charts(data)
