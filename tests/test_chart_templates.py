"""Test chart templates + SQL shape validator (Tier 4)."""

from __future__ import annotations

from core.chart_templates import match_chart_template
from core.sql_shape_validator import (
    detect_shape_kind,
    normalize_rows_for_chart,
    validate_shape,
)
from core.viz_advisor import resolve_chart_type, suggest_chart_from_data


def test_match_valuation_template():
    tpl = match_chart_template(
        "So sánh P/E P/B ROE của FPT VCB HPG",
        domain_id="finance_vnfdata",
    )
    assert tpl is not None
    assert tpl.id == "valuation_snapshot"
    assert tpl.chart_type == "radar"


def test_match_price_line_template():
    tpl = match_chart_template(
        "Diễn biến giá đóng cửa FPT 20 phiên gần nhất",
        domain_id="finance_vnfdata",
    )
    assert tpl is not None
    assert tpl.id == "stock_price_line"


def test_match_candlestick_template():
    tpl = match_chart_template(
        "Vẽ biểu đồ nến HPG",
        domain_id="finance_vnfdata",
    )
    assert tpl is not None
    assert tpl.id == "candlestick_volume"


def test_no_template_other_domain():
    assert (
        match_chart_template("Top 10 vốn hóa", domain_id="mining") is None
    )


def test_dedupe_valuation_rows():
    rows = [
        {"ticker": "FPT", "pe_ratio": 10, "pb_ratio": 2, "roe": 0.2, "calc_date": "2026-01-01"},
        {"ticker": "FPT", "pe_ratio": 12, "pb_ratio": 2.1, "roe": 0.22, "calc_date": "2026-06-01"},
        {"ticker": "VCB", "pe_ratio": 8, "pb_ratio": 1.5, "roe": 0.18, "calc_date": "2026-06-01"},
    ]
    tpl = match_chart_template("So sánh P/E P/B ROE", domain_id="finance_vnfdata")
    notes = validate_shape(rows, tpl)
    assert any("Gom" in n or "kỳ" in n.lower() or "Nhiều kỳ" in n for n in notes)
    out, actions = normalize_rows_for_chart(rows, tpl)
    assert len(out) == 2
    fpt = next(r for r in out if r["ticker"] == "FPT")
    assert fpt["pe_ratio"] == 12
    assert actions


def test_detect_multi_ticker_price():
    rows = []
    for t in ("FPT", "VCB"):
        for i in range(1, 6):
            rows.append(
                {
                    "ticker": t,
                    "trade_date": f"2026-01-{i:02d}",
                    "close_price": 100 + i,
                }
            )
    assert detect_shape_kind(rows) == "multi_ticker_price"


def test_resolve_prefers_template_radar():
    data = [
        {"ticker": t, "pe_ratio": 10 + i, "pb_ratio": 1 + i * 0.1, "roe": 0.1 + i * 0.01}
        for i, t in enumerate(["FPT", "VCB", "HPG"])
    ]
    chart = resolve_chart_type(
        "xem dữ liệu",
        data=data,
        preferred="radar",
    )
    assert chart == "radar"


def test_suggest_many_metrics_radar():
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
    assert suggest_chart_from_data(data) == "radar"
