"""
Chuẩn hóa / kiểm tra shape kết quả SQL trước khi chọn chart.

Không rewrite SQL nguy hiểm — chỉ:
- Dedupe 1 dòng/mã (kỳ mới nhất) khi so sánh định giá
- Gắn ghi chú shape để FE/insight hiểu
- Báo thiếu cột kỳ vọng theo template
"""

from __future__ import annotations

import re
from typing import Any

from core.chart_templates import ChartTemplate, ShapeKind

_COMPANY_NAME_RE = re.compile(r"company_name|short_name|ten_cong_ty", re.I)


def _cols(rows: list[dict[str, Any]]) -> list[str]:
    return list(rows[0].keys()) if rows else []


def _find_col(cols: list[str], *patterns: str) -> str | None:
    for pat in patterns:
        re_pat = re.compile(pat, re.I)
        for c in cols:
            if re_pat.search(c):
                return c
    return None


def _unique_count(rows: list[dict[str, Any]], col: str) -> int:
    return len({str(r.get(col) or "") for r in rows if r.get(col) is not None})


def dedupe_latest_per_entity(
    rows: list[dict[str, Any]],
    entity_col: str,
    date_col: str | None,
) -> list[dict[str, Any]]:
    """Giữ 1 dòng / entity — ưu tiên ngày mới nhất."""
    if not rows or not entity_col:
        return rows
    by_ent: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(entity_col) or "")
        if not key:
            continue
        prev = by_ent.get(key)
        if prev is None:
            by_ent[key] = row
            continue
        if date_col and str(row.get(date_col) or "") > str(prev.get(date_col) or ""):
            by_ent[key] = row
    if len(by_ent) >= len(rows):
        return rows
    return list(by_ent.values())


def detect_shape_kind(rows: list[dict[str, Any]]) -> ShapeKind:
    """Suy shape từ cột kết quả (không cần template)."""
    if not rows:
        return "generic"
    cols = _cols(rows)
    entity = _find_col(cols, r"^(ticker|symbol|ma_cp)$")
    date_col = _find_col(cols, r"trade_date|calc_date|date|ngay")
    open_c = _find_col(cols, r"^open(_price)?$|open_price")
    high_c = _find_col(cols, r"^high(_price)?$|high_price")
    low_c = _find_col(cols, r"^low(_price)?$|low_price")
    close_c = _find_col(cols, r"^close(_price)?$|close_price|adjusted_price")
    pe = _find_col(cols, r"pe_ratio|^pe$")
    pb = _find_col(cols, r"pb_ratio|^pb$")
    roe = _find_col(cols, r"^roe$")

    if open_c and high_c and low_c and close_c:
        return "price_ohlc"

    if entity and date_col and close_c:
        n_ent = _unique_count(rows, entity)
        n_date = _unique_count(rows, date_col)
        if n_ent >= 2 and n_date >= 2 and len(rows) / max(n_ent, 1) >= 1.5:
            return "multi_ticker_price"
        return "price_timeseries"

    if entity and pe and (pb or roe):
        return "valuation_snapshot"

    if entity and _find_col(cols, r"market_cap|volume|von_hoa"):
        return "ranking"

    return "generic"


def validate_shape(
    rows: list[dict[str, Any]],
    template: ChartTemplate | None = None,
) -> list[str]:
    """Danh sách cảnh báo shape (tiếng Việt, ngắn)."""
    notes: list[str] = []
    if not rows:
        return ["Không có dòng dữ liệu"]

    cols_lower = {c.lower(): c for c in _cols(rows)}
    kind = template.shape if template else detect_shape_kind(rows)

    if template and template.required_cols:
        missing = [c for c in template.required_cols if c.lower() not in cols_lower]
        if missing:
            notes.append(f"Thiếu cột kỳ vọng: {', '.join(missing)}")

    entity = _find_col(_cols(rows), r"^(ticker|symbol|ma_cp)$")
    date_col = _find_col(_cols(rows), r"trade_date|calc_date|date|ngay")
    name_col = _find_col(_cols(rows), r"company_name|short_name")

    if entity and name_col and not date_col:
        n_ent = _unique_count(rows, entity)
        n_name = _unique_count(rows, name_col)
        if n_ent == n_name == len(rows) and n_ent >= 2:
            notes.append(
                "Có cả mã và tên công ty (1:1) — tránh pivot heatmap mã×tên"
            )

    if kind == "valuation_snapshot" and entity and date_col:
        if len(rows) > _unique_count(rows, entity):
            notes.append("Nhiều kỳ/mã — sẽ gom 1 dòng/mã (kỳ mới nhất)")

    if kind in ("price_timeseries", "multi_ticker_price", "price_ohlc"):
        if not date_col:
            notes.append("Chuỗi giá thiếu cột ngày")
        if not _find_col(_cols(rows), r"close_price|adjusted_price|gia"):
            notes.append("Chuỗi giá thiếu cột giá đóng cửa")

    return notes


def normalize_rows_for_chart(
    rows: list[dict[str, Any]],
    template: ChartTemplate | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Chuẩn hóa rows cho chart.

    Returns: (normalized_rows, actions_taken)
    """
    if not rows:
        return rows, []

    actions: list[str] = []
    out = list(rows)
    cols = _cols(out)
    entity = _find_col(cols, r"^(ticker|symbol|ma_cp)$")
    date_col = _find_col(cols, r"trade_date|calc_date|date|ngay")
    kind = template.shape if template else detect_shape_kind(out)

    if kind in ("valuation_snapshot", "ranking") and entity:
        before = len(out)
        out = dedupe_latest_per_entity(out, entity, date_col)
        if len(out) < before:
            actions.append(f"Gom {before}→{len(out)} dòng (1 mã / kỳ mới nhất)")

    drop = list(template.drop_cols_for_chart) if template else []
    if entity and date_col:
        for c in cols:
            if _COMPANY_NAME_RE.search(c) and c not in drop:
                drop.append(c)
    if drop:
        present = [c for c in drop if c in cols]
        if present and entity:
            actions.append(f"Gợi ý bỏ cột thừa khi vẽ: {', '.join(present)}")

    return out, actions


def build_trust_meta(
    rows: list[dict[str, Any]],
    *,
    sql_source: str | None = None,
    template: ChartTemplate | None = None,
    shape_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Metadata tin cậy gắn vào ChatResponse."""
    cols = _cols(rows) if rows else []
    source_col = _find_col(cols, r"^source$|data_source|nguon")
    sources: list[str] = []
    if source_col and rows:
        sources = sorted(
            {
                str(r.get(source_col)).strip()
                for r in rows
                if r.get(source_col) is not None and str(r.get(source_col)).strip()
            }
        )[:5]

    return {
        "sql_source": sql_source,
        "chart_template": template.id if template else None,
        "chart_template_name": template.name if template else None,
        "shape_kind": (template.shape if template else detect_shape_kind(rows)),
        "shape_notes": shape_notes or [],
        "price_sources": sources,
        "has_price_source": bool(sources),
    }
