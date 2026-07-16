"""Test làm sạch SQL + entity resolver (không hardcode fast-path Postgres)."""

from __future__ import annotations

import json
from pathlib import Path

from core.entity_resolver import (
    extract_ticker_candidates,
    format_entity_hint,
    resolve_tickers,
)
from core.llm_agent import _clean_sql_output
from core.sql_fast_path import try_fast_sql

_PG = "postgresql+psycopg2://u:p@127.0.0.1:5432/vnfdatadb"
_ROOT = Path(__file__).resolve().parents[1]


def test_clean_sql_strips_thong_bao_echo():
    raw = (
        "SELECT fs.net_revenue AS net_revenue FROM financial_statements fs LIMIT 5\n"
        "=== THÔNG BÁO LỖI ===\n"
        "Không thể thực thi truy vấn"
    )
    out = _clean_sql_output(raw)
    assert "THÔNG BÁO" not in out
    assert out.upper().startswith("SELECT")
    assert "LIMIT 5" in out


def test_clean_sql_strips_cau_hoi_echo():
    raw = (
        "SELECT c.ticker FROM companies c WHERE c.ticker = 'FPT'\n"
        "=== CÂU HỎI HIỆN TẠI ===\n"
        "FPT doanh thu"
    )
    out = _clean_sql_output(raw)
    assert "HỎI" not in out
    assert "FPT" in out


def test_clean_sql_extracts_from_markdown_and_prefix():
    raw = "SQL:\n```sql\nSELECT 1 AS x\n```\nExplanation: demo"
    out = _clean_sql_output(raw)
    assert out == "SELECT 1 AS x"


def test_pg_fast_path_disabled_no_hardcoded_sql():
    """Postgres không map câu hỏi → SQL cứng."""
    for q in (
        "Phân tích thị trường vốn hóa",
        "giá cổ phiếu ACB",
        "Diễn biến giá AIC 5 phiên gần nhất",
        "Danh sách công ty",
        "Thành phần chỉ số VN30",
    ):
        assert try_fast_sql("finance_vnfdata", q, db_url=_PG) is None


def test_config_index_constituents_matches_real_schema():
    cfg = json.loads(
        (_ROOT / "configs" / "finance_vnfdata.json").read_text(encoding="utf-8")
    )
    ic = cfg["data_dictionary"]["index_constituents"]
    assert "group_code" in ic
    assert "ticker" in ic
    assert "index_symbol" not in ic
    assert "weight" not in ic
    vn30 = next(
        ex for ex in cfg["few_shot_examples"] if "VN30" in ex["question"]
    )
    assert "group_code" in vn30["sql"]
    assert "index_symbol" not in vn30["sql"]


def test_extract_candidates_acb_aic_not_phien():
    assert "ACB" in extract_ticker_candidates("giá cổ phiếu ACB")
    assert "AIC" in extract_ticker_candidates("Diễn biến giá AIC 5 phiên gần nhất")
    assert "PHIEN" not in extract_ticker_candidates(
        "phân tích giá cổ phiếu phiên gần nhất"
    )


def test_resolve_tickers_filters_against_known_set(monkeypatch):
    monkeypatch.setattr(
        "core.entity_resolver.load_company_tickers",
        lambda _url: frozenset({"ACB", "FPT", "AIC"}),
    )
    got = resolve_tickers("Diễn biến giá AIC và XYZ", db_url=_PG)
    assert got == ["AIC"]


def test_entity_hint_format():
    hint = format_entity_hint(["ACB", "FPT"])
    assert "ACB" in hint
    assert "companies.ticker" in hint
    assert format_entity_hint([]) == ""
