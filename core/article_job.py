"""Chạy job viết bài auto — SQL đã duyệt + Narrative Planner."""

from __future__ import annotations

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


def fetch_max_trade_date(domain_id: str = DOMAIN_ID) -> str | None:
    sql = "SELECT MAX(trade_date) AS max_date FROM stock_prices"
    try:
        rows = execute_query(_db_url(domain_id), sql)
    except (DbQueryError, Exception) as exc:  # noqa: BLE001
        logger.warning("fetch_max_trade_date failed: %s", exc)
        return None
    if not rows:
        return None
    val = rows[0].get("max_date")
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date().isoformat()
    if isinstance(val, date):
        return val.isoformat()
    return str(val)[:10]


def fetch_max_fiscal_key(domain_id: str = DOMAIN_ID) -> str | None:
    """Key dạng YYYY-Qn hoặc YYYY-Y (năm)."""
    sql = (
        "SELECT fiscal_year, fiscal_quarter "
        "FROM financial_statements "
        "ORDER BY fiscal_year DESC, "
        "CASE WHEN fiscal_quarter IS NULL THEN 5 ELSE fiscal_quarter END DESC "
        "LIMIT 1"
    )
    try:
        rows = execute_query(_db_url(domain_id), sql)
    except (DbQueryError, Exception) as exc:  # noqa: BLE001
        logger.warning("fetch_max_fiscal_key failed: %s", exc)
        return None
    if not rows:
        return None
    year = rows[0].get("fiscal_year")
    q = rows[0].get("fiscal_quarter")
    if year is None:
        return None
    if q is None:
        return f"{int(year)}-Y"
    return f"{int(year)}-Q{int(q)}"


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
