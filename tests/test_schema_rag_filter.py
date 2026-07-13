"""Tests Schema RAG filter cho VNFDATA (sp_y*, backup, etl)."""

from __future__ import annotations

from core.schema_rag import is_noise_table, _hint_boost, _normalize


def test_noise_partition_and_backup() -> None:
    assert is_noise_table("sp_y2024m01") is True
    assert is_noise_table("sp_y2026m07") is True
    assert is_noise_table("exchanges_backup_007") is True
    assert is_noise_table("etl_logs") is True
    assert is_noise_table("schema_migrations") is True
    assert is_noise_table("stock_prices") is False
    assert is_noise_table("companies") is False
    assert is_noise_table("financial_indicators") is False


def test_vi_hint_boost() -> None:
    q = _normalize("Top 10 vốn hóa HoSE")
    assert _hint_boost("financial_indicators", q) > 0
    assert _hint_boost("stock_prices", _normalize("giá đóng cửa FPT 20 phiên")) > 0


if __name__ == "__main__":
    test_noise_partition_and_backup()
    test_vi_hint_boost()
    print("ALL PASSED")
