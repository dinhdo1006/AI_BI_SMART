"""Tests VNFDATA article template catalog + classification."""

from __future__ import annotations

from core.article_templates import (
    classify_article_template,
    list_templates,
    outline_from_template,
    parse_word_count_range,
)
from core.narrative_planner import (
    _default_outline,
    stamp_article_timestamp,
)


def test_catalog_has_35_templates() -> None:
    templates = list_templates()
    assert len(templates) == 35
    ids = {t["id"] for t in templates}
    assert "market_01" in ids
    assert "company_20" in ids


def test_classify_top_gainers() -> None:
    t = classify_article_template("Top 10 cổ phiếu tăng giá hôm nay")
    assert t is not None
    assert t["id"] == "market_02"


def test_classify_foreign_flow() -> None:
    t = classify_article_template("Khối ngoại mua ròng phiên này bao nhiêu?")
    assert t is not None
    assert t["id"] == "market_09"


def test_classify_top_revenue_beats_revenue() -> None:
    t = classify_article_template("Top doanh thu ngành thép quý vừa rồi")
    assert t is not None
    assert t["id"] == "company_07"


def test_classify_lnst() -> None:
    t = classify_article_template("Phân tích LNST của VNM quý gần nhất")
    assert t is not None
    assert t["id"] == "company_03"


def test_classify_no_match() -> None:
    assert classify_article_template("xyz abc không liên quan") is None


def test_parse_word_count_vietnamese_thousands() -> None:
    assert parse_word_count_range("600-800") == (600, 800)
    assert parse_word_count_range("800-1.000") == (800, 1000)
    assert parse_word_count_range("900-1.200") == (900, 1200)


def test_outline_from_template_has_ai_questions() -> None:
    t = classify_article_template("Độ rộng thị trường phiên hôm nay")
    assert t is not None
    outline = outline_from_template(
        t, question="Độ rộng thị trường phiên hôm nay", domain_name="VNFDATA"
    )
    assert outline["style"] == "vietstock"
    assert outline["template_id"] == "market_08"
    assert len(outline["ai_questions"]) >= 2
    assert len(outline["sections"]) >= 3
    assert outline["word_count_min"] == 500


def test_default_outline_picks_template_for_finance() -> None:
    outline = _default_outline(
        "Top vốn hóa HOSE tuần này", "VNFDATA — Tài chính", "finance_vnfdata"
    )
    assert outline["style"] == "vietstock"
    assert outline.get("template_id") == "market_05"


def test_stamp_article_timestamp() -> None:
    md = stamp_article_timestamp("# Tiêu đề\n\nLead đoạn.\n\n## Mục\n\nNội dung.")
    assert "Thời gian tạo báo cáo:" in md
    # Không stamp lần 2
    md2 = stamp_article_timestamp(md)
    assert md2.count("Thời gian tạo báo cáo:") == 1


if __name__ == "__main__":
    test_catalog_has_35_templates()
    test_classify_top_gainers()
    test_classify_foreign_flow()
    test_classify_top_revenue_beats_revenue()
    test_classify_lnst()
    test_classify_no_match()
    test_parse_word_count_vietnamese_thousands()
    test_outline_from_template_has_ai_questions()
    test_default_outline_picks_template_for_finance()
    test_stamp_article_timestamp()
    print("ALL PASSED")
