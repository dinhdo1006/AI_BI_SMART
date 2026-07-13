"""Chuẩn hóa SQL trước khi thực thi — LIMIT an toàn, trim thừa."""

from __future__ import annotations

import re

_DEFAULT_MAX_ROWS = 1000
_LIMIT_PATTERN: re.Pattern[str] = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)


def ensure_sql_limit(sql_query: str, max_rows: int = _DEFAULT_MAX_ROWS) -> str:
    """
    Thêm LIMIT nếu câu SQL chưa có — tránh trả về quá nhiều dòng cho chart.

    Không sửa nếu đã có LIMIT (kể cả subquery).
    """
    cleaned = sql_query.strip().rstrip(";")
    if not cleaned:
        return cleaned
    if _LIMIT_PATTERN.search(cleaned):
        return cleaned
    return f"{cleaned} LIMIT {max_rows}"


def normalize_sql(sql_query: str, *, max_rows: int = _DEFAULT_MAX_ROWS) -> str:
    """Pipeline chuẩn hóa SQL trước execute."""
    return ensure_sql_limit(sql_query.strip().rstrip(";"), max_rows=max_rows)
