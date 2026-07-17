"""Tests upload CSV parse + cross-domain guard."""

from __future__ import annotations

from core.cross_domain import detect_cross_domain_request
from core.upload_analyzer import parse_csv_text


def test_parse_csv_basic() -> None:
    text = "ticker,pe_ratio,roe\nVNM,15.2,18\nFPT,20.1,22\n"
    rows = parse_csv_text(text)
    assert len(rows) == 2
    assert rows[0]["ticker"] == "VNM"
    assert rows[0]["pe_ratio"] == 15.2


def test_cross_domain_message_when_missing_domains() -> None:
    hit = detect_cross_domain_request(
        "Chi phí IT deployment tháng này so với doanh thu tài chính?",
        available_domains=["finance_vnfdata"],
    )
    assert hit is not None
    assert "liên domain" in hit["message"].lower() or "domain" in hit["message"].lower()


def test_cross_domain_allows_pure_finance() -> None:
    assert (
        detect_cross_domain_request(
            "P/E của VNM hôm nay",
            available_domains=["finance_vnfdata"],
        )
        is None
    )
