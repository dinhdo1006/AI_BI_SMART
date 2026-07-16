"""Test few-shot retrieval theo độ giống câu hỏi."""

from __future__ import annotations

from core.few_shot_retriever import best_few_shot_sql, rank_few_shots, score_few_shot

_EXAMPLES = [
    {
        "question": "Top 10 mã cổ phiếu vốn hóa lớn nhất",
        "sql": "SELECT fi.market_cap FROM financial_indicators fi ORDER BY fi.market_cap DESC LIMIT 10",
    },
    {
        "question": "Diễn biến giá FPT 20 phiên",
        "sql": "SELECT close_price FROM stock_prices WHERE ticker = 'FPT'",
    },
    {
        "question": "Thành phần chỉ số VN30",
        "sql": "SELECT ticker FROM index_constituents WHERE group_code LIKE '%VN30%'",
    },
]


def test_rank_puts_market_cap_first():
    ranked = rank_few_shots("Phân tích thị trường vốn hóa", _EXAMPLES)
    assert "vốn hóa" in ranked[0]["question"].lower() or "von" in ranked[0]["question"].lower() or "market_cap" in ranked[0]["sql"]


def test_best_few_shot_for_von_hoa():
    sql = best_few_shot_sql("Phân tích thị trường vốn hóa", _EXAMPLES)
    assert sql is not None
    assert "market_cap" in sql


def test_best_few_shot_rejects_unrelated():
    sql = best_few_shot_sql("thời tiết hôm nay thế nào", _EXAMPLES, min_score=0.25)
    assert sql is None


def test_score_positive_for_overlap():
    assert score_few_shot("vốn hóa top 10", _EXAMPLES[0]) > score_few_shot(
        "vốn hóa top 10", _EXAMPLES[2]
    )
