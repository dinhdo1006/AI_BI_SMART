"""Test làm sạch SQL + fast-path Postgres finance."""

from __future__ import annotations

from core.llm_agent import _clean_sql_output
from core.sql_fast_path import try_fast_sql


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


def test_finance_pg_fast_path_revenue_fpt():
    sql = try_fast_sql(
        "finance_vnfdata",
        "Cho tôi biết doanh thu thuần và LN sau thuế của FPT qua các quý",
        db_url="postgresql+psycopg2://u:p@127.0.0.1:5432/vnfdatadb",
    )
    assert sql is not None
    assert "financial_statements" in sql
    assert "net_revenue" in sql
    assert "net_income" in sql
    assert "FPT" in sql
    assert "companies" in sql


def test_finance_pg_fast_path_top_market_cap():
    sql = try_fast_sql(
        "finance_vnfdata",
        "Top 10 mã cổ phiếu vốn hóa lớn nhất trên sàn HoSE",
        db_url="postgresql+psycopg2://u:p@127.0.0.1:5432/vnfdatadb",
    )
    assert sql is not None
    assert "market_cap" in sql
    assert "financial_indicators" in sql
