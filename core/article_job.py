"""Chạy job viết bài auto — SQL đã duyệt + Narrative Planner."""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Any

from core.article_store import has_article, save_article
from core.article_templates import get_template
from core.config_loader import load_domain_config
from core.db_executor import DbQueryError, execute_query
from core.insight_stats import compute_insight_stats
from core.narrative_planner import generate_article

logger = logging.getLogger(__name__)

DOMAIN_ID = "finance_vnfdata"


def _fingerprint(*parts: Any) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_intraday_data_date(trade_date: str, when: datetime | None = None) -> str:
    """Kỳ dữ liệu theo giờ cục bộ — VD 2026-07-14T15 khi DB cập nhật trong ngày."""
    n = when or datetime.now()
    base = (trade_date or "").strip()[:10] or n.strftime("%Y-%m-%d")
    return f"{base}T{n.strftime('%H')}"

# SQL đã duyệt theo loại template (PostgreSQL VNFDATA)
_SQL_BY_TEMPLATE: dict[str, str] = {
    "market_01": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (
    SELECT MAX(trade_date) FROM stock_prices
)
ORDER BY sp.value DESC NULLS LAST
LIMIT 80
""".strip(),
    "market_02": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
  AND sp.change_percent IS NOT NULL
ORDER BY sp.change_percent DESC
LIMIT 15
""".strip(),
    "market_03": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
  AND sp.change_percent IS NOT NULL
ORDER BY sp.change_percent ASC
LIMIT 15
""".strip(),
    "market_04": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date = (SELECT MAX(trade_date) FROM stock_prices)
ORDER BY sp.value DESC NULLS LAST
LIMIT 15
""".strip(),
    "market_05": """
SELECT fi.symbol AS ticker,
       fi.calc_date,
       fi.market_cap,
       fi.pe_ratio,
       fi.pb_ratio
FROM financial_indicators fi
WHERE fi.calc_date = (SELECT MAX(calc_date) FROM financial_indicators)
  AND fi.market_cap IS NOT NULL
ORDER BY fi.market_cap DESC
LIMIT 15
""".strip(),
    "market_09": """
SELECT c.ticker,
       ft.trade_date,
       ft.buy_volume,
       ft.sell_volume,
       ft.net_volume
FROM foreign_trades ft
JOIN companies c ON c.id = ft.company_id
WHERE ft.trade_date = (SELECT MAX(trade_date) FROM foreign_trades)
ORDER BY ABS(COALESCE(ft.net_volume, 0)) DESC
LIMIT 30
""".strip(),
    "market_14": """
SELECT c.ticker,
       sp.trade_date,
       sp.close_price,
       sp.change_percent,
       sp.volume,
       sp.value
FROM stock_prices sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.trade_date >= (
    SELECT MAX(trade_date) - INTERVAL '30 days' FROM stock_prices
)
ORDER BY sp.trade_date DESC, sp.value DESC NULLS LAST
LIMIT 120
""".strip(),
    "company_01": """
SELECT c.ticker,
       c.company_name,
       fs.fiscal_year,
       fs.fiscal_quarter,
       fs.report_type,
       fs.net_revenue,
       fs.net_income,
       fs.gross_profit,
       fs.total_assets,
       fs.equity,
       fs.operating_cash_flow
FROM financial_statements fs
JOIN companies c ON c.id = fs.company_id
WHERE fs.fiscal_year = (
    SELECT MAX(fiscal_year) FROM financial_statements
)
ORDER BY fs.net_income DESC NULLS LAST
LIMIT 40
""".strip(),
}

_FALLBACK_MARKET_SQL = _SQL_BY_TEMPLATE["market_01"]
_FALLBACK_COMPANY_SQL = _SQL_BY_TEMPLATE["company_01"]


def _db_url(domain_id: str) -> str:
    cfg = load_domain_config(domain_id)
    return str(cfg.get("db_url") or "").strip()


def _as_date_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, date):
        return val.isoformat()
    text = str(val).strip()
    return text[:10] if text else None


def fetch_max_trade_date(domain_id: str = DOMAIN_ID) -> str | None:
    wm = fetch_market_watermark(domain_id)
    return wm.get("trade_date") if wm else None


def fetch_market_watermark(domain_id: str = DOMAIN_ID) -> dict[str, Any] | None:
    """
    Watermark phiên mới nhất: ngày + số dòng + tổng GTGD/KL + MAX(id).
    Thay đổi bất kỳ → fingerprint đổi → có thể viết lại trong cùng ngày.
    """
    sql = """
SELECT
  MAX(trade_date) AS max_date,
  COUNT(*) AS cnt,
  COALESCE(SUM(value), 0) AS total_value,
  COALESCE(SUM(volume), 0) AS total_volume,
  COALESCE(MAX(id), 0) AS max_id
FROM stock_prices
WHERE trade_date = (SELECT MAX(trade_date) FROM stock_prices)
""".strip()
    try:
        rows = execute_query(_db_url(domain_id), sql)
    except (DbQueryError, Exception) as exc:  # noqa: BLE001
        logger.warning("fetch_market_watermark failed: %s", exc)
        return None
    if not rows:
        return None
    row = rows[0]
    trade_date = _as_date_str(row.get("max_date"))
    if not trade_date:
        return None
    cnt = int(row.get("cnt") or 0)
    total_value = float(row.get("total_value") or 0)
    total_volume = float(row.get("total_volume") or 0)
    max_id = int(row.get("max_id") or 0)
    fp = _fingerprint(trade_date, cnt, round(total_value, 2), round(total_volume, 2), max_id)
    return {
        "trade_date": trade_date,
        "row_count": cnt,
        "total_value": total_value,
        "total_volume": total_volume,
        "max_id": max_id,
        "fingerprint": fp,
    }


def fetch_max_fiscal_key(domain_id: str = DOMAIN_ID) -> str | None:
    wm = fetch_fiscal_watermark(domain_id)
    return wm.get("fiscal_key") if wm else None


def fetch_fiscal_watermark(domain_id: str = DOMAIN_ID) -> dict[str, Any] | None:
    """Watermark kỳ BCTC mới nhất + khối lượng số liệu trong kỳ."""
    sql = """
WITH latest AS (
  SELECT fiscal_year, fiscal_quarter
  FROM financial_statements
  ORDER BY fiscal_year DESC,
    CASE WHEN fiscal_quarter IS NULL THEN 5 ELSE fiscal_quarter END DESC
  LIMIT 1
)
SELECT
  l.fiscal_year,
  l.fiscal_quarter,
  COUNT(*) AS cnt,
  COALESCE(SUM(fs.net_income), 0) AS total_net_income,
  COALESCE(SUM(fs.net_revenue), 0) AS total_revenue,
  COALESCE(MAX(fs.id), 0) AS max_id
FROM financial_statements fs
JOIN latest l ON fs.fiscal_year = l.fiscal_year
  AND (
    (fs.fiscal_quarter IS NULL AND l.fiscal_quarter IS NULL)
    OR fs.fiscal_quarter = l.fiscal_quarter
  )
GROUP BY l.fiscal_year, l.fiscal_quarter
""".strip()
    try:
        rows = execute_query(_db_url(domain_id), sql)
    except (DbQueryError, Exception) as exc:  # noqa: BLE001
        logger.warning("fetch_fiscal_watermark failed: %s", exc)
        return None
    if not rows:
        return None
    row = rows[0]
    year = row.get("fiscal_year")
    if year is None:
        return None
    q = row.get("fiscal_quarter")
    fiscal_key = f"{int(year)}-Y" if q is None else f"{int(year)}-Q{int(q)}"
    cnt = int(row.get("cnt") or 0)
    total_ni = float(row.get("total_net_income") or 0)
    total_rev = float(row.get("total_revenue") or 0)
    max_id = int(row.get("max_id") or 0)
    fp = _fingerprint(fiscal_key, cnt, round(total_ni, 2), round(total_rev, 2), max_id)
    return {
        "fiscal_key": fiscal_key,
        "row_count": cnt,
        "total_net_income": total_ni,
        "total_revenue": total_rev,
        "max_id": max_id,
        "fingerprint": fp,
    }


def build_sql_for_template(template_id: str) -> str:
    tid = (template_id or "").strip()
    if tid in _SQL_BY_TEMPLATE:
        return _SQL_BY_TEMPLATE[tid]
    tpl = get_template(tid)
    if tpl and str(tpl.get("category") or "") == "company":
        return _FALLBACK_COMPANY_SQL
    return _FALLBACK_MARKET_SQL


def default_question(template: dict[str, Any], data_date: str) -> str:
    name = str(template.get("name") or template.get("id") or "Bài phân tích")
    return f"{name} — kỳ dữ liệu {data_date}"


def run_article_job(
    *,
    template_id: str,
    domain_id: str = DOMAIN_ID,
    data_date: str,
    trigger: str = "manual",
    force: bool = False,
    question: str | None = None,
) -> dict[str, Any]:
    """
    Chạy 1 job: query data → generate_article → lưu store.

    Returns dict status: skipped | ok | error
    """
    tid = (template_id or "").strip()
    dd = (data_date or "").strip()
    if not tid or not dd:
        return {"status": "error", "message": "Thiếu template_id hoặc data_date"}

    template = get_template(tid)
    if not template:
        return {"status": "error", "message": f"Template '{tid}' không tồn tại"}

    if not force and has_article(tid, dd):
        return {
            "status": "skipped",
            "message": f"Đã có bài {tid}:{dd}",
            "template_id": tid,
            "data_date": dd,
        }

    try:
        cfg = load_domain_config(domain_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}

    domain_name = str(cfg.get("domain_name") or domain_id)
    labels = cfg.get("column_labels", {}) or {}
    sql = build_sql_for_template(tid)

    try:
        rows = execute_query(str(cfg.get("db_url") or ""), sql)
    except DbQueryError as exc:
        logger.exception("article job SQL failed: %s", exc)
        return {"status": "error", "message": f"SQL lỗi: {exc}", "template_id": tid}

    if not rows:
        return {
            "status": "error",
            "message": "Không có dữ liệu để viết bài",
            "template_id": tid,
            "data_date": dd,
        }

    data_for_article = rows
    if labels:
        data_for_article = [
            {labels.get(k, k): v for k, v in row.items()} for row in rows
        ]

    q = (question or "").strip() or default_question(template, dd)
    try:
        result = generate_article(
            question=q,
            domain_name=domain_name,
            data=data_for_article,
            stats=compute_insight_stats(data_for_article),
            insight_summary="",
            domain_id=domain_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_article failed: %s", exc)
        return {
            "status": "error",
            "message": f"Narrative Planner lỗi: {exc}",
            "template_id": tid,
        }

    # Ép template meta nếu classifier không match đúng
    outline = dict(result.get("outline") or {})
    outline["template_id"] = tid
    outline["template_name"] = template.get("name")
    outline["style"] = "vietstock"

    saved = save_article(
        template_id=tid,
        template_name=str(template.get("name") or tid),
        data_date=dd,
        article_markdown=str(result.get("article_markdown") or ""),
        domain_id=domain_id,
        question=q,
        trigger=trigger,
        word_count=int(result.get("word_count") or 0),
        outline=outline,
        force=force,
    )
    if saved is None:
        return {
            "status": "skipped",
            "message": f"Đã có bài {tid}:{dd}",
            "template_id": tid,
            "data_date": dd,
        }

    return {
        "status": "ok",
        "article": saved,
        "template_id": tid,
        "data_date": dd,
        "word_count": saved.get("word_count"),
    }
