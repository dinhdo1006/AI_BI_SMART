"""Thực thi SQL an toàn với guardrail chỉ cho phép SELECT."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.db_engine import get_engine
from core.sql_sanitizer import normalize_sql


class DbQueryError(Exception):
    """Lỗi guardrail hoặc thực thi SQL — dùng cho graceful handling phía API."""

# Từ khóa nguy hiểm — tuyệt đối không được xuất hiện trong câu SQL
_FORBIDDEN_KEYWORDS: re.Pattern[str] = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|REPLACE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)

# SQL phải bắt đầu bằng SELECT (cho phép khoảng trắng / comment đơn giản phía trước)
_SELECT_START: re.Pattern[str] = re.compile(
    r"^\s*(?:--[^\n]*\n\s*)*SELECT\b",
    re.IGNORECASE,
)


def _json_safe_value(value: Any) -> Any:
    """Postgres trả Decimal/date — chuyển sang kiểu JSON-safe (tránh HTTP 500 khi cache)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).hex()
    return value


def _json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _json_safe_value(v) for k, v in row.items()}


def _validate_sql(sql_query: str) -> None:
    """
    Guardrail bảo mật: chỉ cho phép câu SELECT thuần túy.

    Raises:
        DbQueryError: Nếu SQL không bắt đầu bằng SELECT hoặc chứa từ khóa nguy hiểm.
    """
    cleaned = sql_query.strip()

    if not cleaned:
        raise DbQueryError("Câu SQL rỗng — không thể thực thi.")

    # Bắt buộc bắt đầu bằng SELECT
    if not _SELECT_START.match(cleaned):
        raise DbQueryError(
            "Chỉ cho phép câu lệnh SELECT. "
            f"SQL nhận được không hợp lệ: {cleaned[:80]!r}"
        )

    # Từ chối mọi từ khóa ghi/sửa/xóa schema hoặc dữ liệu
    match = _FORBIDDEN_KEYWORDS.search(cleaned)
    if match:
        raise DbQueryError(
            f"Phát hiện từ khóa bị cấm '{match.group(1).upper()}' trong SQL. "
            "Chỉ cho phép truy vấn đọc (SELECT)."
        )


def execute_query(db_url: str, sql_query: str) -> list[dict[str, Any]]:
    """
    Kiểm tra guardrail rồi thực thi SQL, trả về list[dict] (JSON-friendly).

    Args:
        db_url: Chuỗi kết nối SQLAlchemy
            (vd: sqlite:///mock_database.db hoặc
             postgresql+psycopg2://user:pass@host:5432/vnfdatadb).
        sql_query: Câu SQL do LLM sinh ra — phải là SELECT thuần.

    Returns:
        Danh sách các hàng dưới dạng dict (tên cột → giá trị).

    Raises:
        DbQueryError: Guardrail từ chối hoặc lỗi thực thi từ cơ sở dữ liệu.
    """
    # Bước 1: Validate + chuẩn hóa (LIMIT mặc định nếu thiếu)
    _validate_sql(sql_query)
    sql_to_run = normalize_sql(sql_query)

    # Bước 2: Kết nối và thực thi (connection pool dùng chung)
    engine = get_engine(db_url)
    try:
        with engine.connect() as conn:
            try:
                result = conn.execute(text(sql_to_run))
                rows: list[dict[str, Any]] = [
                    _json_safe_row(dict(row)) for row in result.mappings().all()
                ]
                return rows
            except SQLAlchemyError as exc:
                # Giữ thông điệp DB gốc (UndefinedColumn…) để debug/repair
                detail = str(exc.__cause__ or exc).split("\n")[0][:300]
                raise DbQueryError(
                    "Không thể thực thi truy vấn — có thể sai tên cột, cú pháp "
                    f"hoặc cấu trúc dữ liệu không khớp. Chi tiết: {detail}"
                ) from exc
    except SQLAlchemyError as exc:
        detail = str(exc.__cause__ or exc).split("\n")[0][:300]
        raise DbQueryError(
            f"Không thể kết nối hoặc thực thi truy vấn. Chi tiết: {detail}"
        ) from exc
