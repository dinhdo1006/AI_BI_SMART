"""Tests Vietstock outline detection + split article markdown."""

from __future__ import annotations

from core.narrative_planner import (
    _default_outline,
    is_finance_domain,
)
from utils.report_export import split_article_markdown


def test_is_finance_domain() -> None:
    assert is_finance_domain("VNFDATA — Tài chính") is True
    assert is_finance_domain("finance_vnfdata") is True
    assert is_finance_domain("IT Deployment & FSI") is False
    assert is_finance_domain("Mining & Geology") is False


def test_default_outline_vietstock_for_finance() -> None:
    # Câu hỏi generic → khung Vietstock chung (không match template cụ thể)
    outline = _default_outline(
        "Phân tích biến động dữ liệu theo yêu cầu", "VNFDATA — Tài chính"
    )
    assert outline["style"] == "vietstock"
    ids = [s["id"] for s in outline["sections"]]
    assert ids[0] == "thesis"
    assert "update" in ids


def test_default_outline_template_when_matched() -> None:
    outline = _default_outline("Top cổ phiếu tăng giá phiên nay", "VNFDATA — Tài chính")
    assert outline["style"] == "vietstock"
    assert outline.get("template_id") == "market_02"
    assert outline.get("template_name") == "Top cổ phiếu tăng giá"


def test_default_outline_bi_for_it() -> None:
    outline = _default_outline("Top dự án", "IT Deployment")
    assert outline["style"] == "bi"
    assert outline["sections"][0]["id"] == "lead"


def test_split_article_markdown() -> None:
    md = """# FPT: Diễn biến tích cực

Luận điểm: giá tăng nhẹ trong 10 phiên gần nhất.

## Cập nhật số liệu

Số liệu chi tiết ở đây.

## Kết luận

Theo dõi tiếp.
"""
    parts = split_article_markdown(md)
    assert parts["title"] == "FPT: Diễn biến tích cực"
    assert "Luận điểm" in parts["lead"]
    assert parts["body"].startswith("## Cập nhật")
    assert "Kết luận" in parts["body"]


if __name__ == "__main__":
    test_is_finance_domain()
    test_default_outline_vietstock_for_finance()
    test_default_outline_template_when_matched()
    test_default_outline_bi_for_it()
    test_split_article_markdown()
    print("ALL PASSED")
