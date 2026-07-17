"""Phân tích file CSV/Excel upload ad-hoc (không qua Text-to-SQL)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from core.insight_stats import compute_insight_stats
from core.llm_agent import generate_insight
from core.viz_advisor import resolve_chart_type

_MAX_ROWS = 500
_MAX_COLS = 40


def _clean_cell(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # số VN/EN đơn giản
        raw = s.replace("%", "").strip()
        if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
            try:
                return float(raw.replace(".", "").replace(",", "."))
            except ValueError:
                return s
        if re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?", raw):
            try:
                return float(raw.replace(",", ""))
            except ValueError:
                return s
        if re.fullmatch(r"-?\d+[.,]\d+", raw):
            try:
                return float(raw.replace(",", "."))
            except ValueError:
                return s
        if re.fullmatch(r"-?\d+", raw):
            try:
                return int(raw)
            except ValueError:
                return s
        return s
    return v


def parse_csv_text(text: str) -> list[dict[str, Any]]:
    sample = (text or "")[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows: list[dict[str, Any]] = []
    for i, row in enumerate(reader):
        if i >= _MAX_ROWS:
            break
        cleaned: dict[str, Any] = {}
        for j, (k, v) in enumerate(row.items()):
            if j >= _MAX_COLS:
                break
            key = (k or f"col_{j}").strip() or f"col_{j}"
            cleaned[key] = _clean_cell(v)
        if any(v is not None and v != "" for v in cleaned.values()):
            rows.append(cleaned)
    return rows


def parse_upload_bytes(filename: str, content: bytes) -> list[dict[str, Any]]:
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        try:
            import pandas as pd
        except ImportError as exc:
            raise ValueError("Thiếu pandas để đọc Excel") from exc
        df = pd.read_excel(io.BytesIO(content))
        df = df.head(_MAX_ROWS).iloc[:, :_MAX_COLS]
        records = df.where(pd.notnull(df), None).to_dict(orient="records")
        return [{str(k): _clean_cell(v) for k, v in row.items()} for row in records]

    # CSV / TSV / TXT
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise ValueError("Không đọc được encoding của file")
    return parse_csv_text(text)


def analyze_uploaded_table(
    *,
    question: str,
    rows: list[dict[str, Any]],
    filename: str = "",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("File không có dữ liệu hợp lệ")

    q = (question or "").strip() or f"Phân tích dữ liệu từ file {filename or 'upload'}"
    stats = compute_insight_stats(rows)
    insight = generate_insight(q, rows, precomputed_stats=stats)
    chart = resolve_chart_type(q, data=rows)
    return {
        "status": "success",
        "query": q,
        "sql_query": f"(upload file: {filename or 'adhoc'})",
        "data": rows,
        "insight": insight,
        "row_count": len(rows),
        "chart_type": chart,
        "sql_source": "upload",
        "stats": stats,
        "filename": filename,
    }
