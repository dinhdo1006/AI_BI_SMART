"""Tests fact-check số liệu trong bài viết."""

from __future__ import annotations

from core.article_fact_check import (
    collect_source_numbers,
    extract_claim_numbers,
    fact_check_article,
)


def test_extract_vn_and_percent_numbers() -> None:
    md = "# Tiêu đề\n\nP/E đạt 15,2 và vốn hóa 1.250 tỷ. ROE 18%.\n"
    claims = extract_claim_numbers(md)
    raws = {c["raw"] for c in claims}
    assert any("15,2" in r for r in raws)
    assert any("1.250" in r for r in raws)
    assert any("18%" in r.replace(" ", "") for r in raws)


def test_skip_timestamp_line() -> None:
    md = (
        "# Báo cáo\n\n"
        "*Thời gian tạo báo cáo: 17/07/2026 13:30*\n\n"
        "Giá đóng cửa 62.5.\n"
    )
    claims = extract_claim_numbers(md)
    assert len(claims) == 1
    assert claims[0]["value"] == 62.5


def test_fact_check_matches_source() -> None:
    data = [{"ticker": "VNM", "pe_ratio": 15.2, "roe": 18.0}]
    md = "# VNM\n\nP/E khoảng 15,2 và ROE 18%.\n"
    result = fact_check_article(md, data=data)
    assert result["checked"] >= 2
    assert result["ok"] is True
    assert result["unmatched"] == []


def test_fact_check_flags_hallucinated_number() -> None:
    data = [{"ticker": "VNM", "pe_ratio": 15.2}]
    md = "# VNM\n\nP/E 15,2 nhưng giá mục tiêu 999.000 đồng.\n"
    result = fact_check_article(md, data=data)
    assert result["ok"] is False
    assert result["warnings"]
    assert any("999" in u["raw"] for u in result["unmatched"])


def test_collect_source_includes_row_count() -> None:
    data = [{"a": 1}, {"a": 2}, {"a": 3}]
    nums = collect_source_numbers(data, stats={"row_count": 3})
    assert 3.0 in nums


if __name__ == "__main__":
    test_extract_vn_and_percent_numbers()
    test_skip_timestamp_line()
    test_fact_check_matches_source()
    test_fact_check_flags_hallucinated_number()
    test_collect_source_includes_row_count()
    print("ALL PASSED")
