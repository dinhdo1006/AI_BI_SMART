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

    if name.endswith(".pdf"):
        return _parse_pdf_bytes(content)

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


def _parse_pdf_bytes(content: bytes) -> list[dict[str, Any]]:
    """Trích bảng số liệu từ PDF — ưu tiên bảng, fallback text dạng table."""
    # Thử dùng pdfplumber (tốt nhất cho bảng)
    try:
        import pdfplumber  # type: ignore[import]
        rows: list[dict[str, Any]] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    if not table or len(table) < 2:
                        continue
                    headers = [str(h or f"col_{i}").strip() or f"col_{i}"
                               for i, h in enumerate(table[0])]
                    for row in table[1:]:
                        if len(rows) >= _MAX_ROWS:
                            break
                        cleaned: dict[str, Any] = {}
                        for j, v in enumerate(row[:_MAX_COLS]):
                            key = headers[j] if j < len(headers) else f"col_{j}"
                            cleaned[key] = _clean_cell(v)
                        if any(v is not None and v != "" for v in cleaned.values()):
                            rows.append(cleaned)
        if rows:
            return rows
    except ImportError:
        pass

    # Fallback: pypdf (text thuần)
    try:
        import pypdf  # type: ignore[import]
        reader = pypdf.PdfReader(io.BytesIO(content))
        lines: list[str] = []
        for page in reader.pages:
            lines.extend((page.extract_text() or "").splitlines())
        text = "\n".join(lines)
        result = parse_csv_text(text)
        if result:
            return result
    except ImportError:
        pass

    raise ValueError(
        "Không trích được dữ liệu từ PDF. "
        "Cài pdfplumber (khuyến nghị) hoặc pypdf: "
        "pip install pdfplumber"
    )


def analyze_uploaded_table(
    *,
    question: str,
    rows: list[dict[str, Any]],
    filename: str = "",
    db_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Phân tích bảng upload.
    db_context: dữ liệu DB bổ sung (từ fast-path / SQL) để LLM kết hợp phân tích.
    """
    if not rows:
        raise ValueError("File không có dữ liệu hợp lệ")

    q = (question or "").strip() or f"Phân tích dữ liệu từ file {filename or 'upload'}"

    # Merge db_context vào rows nếu có (enrich thêm cột từ DB)
    merged_rows = rows
    db_note = ""
    if db_context:
        merged_rows = _merge_upload_with_db(rows, db_context)
        db_note = f" (kết hợp {len(db_context)} dòng từ DB)"

    stats = compute_insight_stats(merged_rows)
    insight = generate_insight(q, merged_rows, precomputed_stats=stats)
    chart = resolve_chart_type(q, data=merged_rows)
    return {
        "status": "success",
        "query": q,
        "sql_query": f"(upload file: {filename or 'adhoc'}{db_note})",
        "data": merged_rows,
        "insight": insight,
        "row_count": len(merged_rows),
        "chart_type": chart,
        "sql_source": "upload",
        "stats": stats,
        "filename": filename,
    }


def _merge_upload_with_db(
    upload_rows: list[dict[str, Any]],
    db_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Cố gắng join upload với DB theo cột chung đầu tiên.
    Nếu không có cột chung → ghép nối tiếp (append).
    """
    if not db_rows:
        return upload_rows
    upload_keys = set(upload_rows[0].keys()) if upload_rows else set()
    db_keys = set(db_rows[0].keys()) if db_rows else set()
    common = upload_keys & db_keys
    if not common:
        # Không join được — ghép thêm DB rows vào dưới
        return upload_rows + db_rows
    join_key = next(iter(common))
    db_map: dict[Any, dict[str, Any]] = {}
    for row in db_rows:
        k = row.get(join_key)
        if k is not None:
            db_map[k] = row
    merged: list[dict[str, Any]] = []
    for row in upload_rows:
        k = row.get(join_key)
        extra = db_map.get(k, {})
        merged.append({**extra, **row})
    return merged
